# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SmartCheck AI Engine is a standalone FastAPI microservice for the **RedCheck** productivity platform (whose main backend is Spring Boot/Java, a separate repo). It takes a user's pending tasks + analytics, retrieves relevant history from a local ChromaDB vector store, and calls Google Gemini 2.5 Flash to return a strict-schema JSON daily execution plan (task priority order, risk level, and a support message).

## Commands

```bash
# Setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run locally (requires .env with GEMINI_API_KEY)
uvicorn app.main:app --reload
# -> http://localhost:8000/docs for Swagger UI

# Docker
docker build -t smartcheck-ai-engine .
docker run -d -p 8000:8000 --env-file .env -v chroma_data:/app/chroma_data smartcheck-ai-engine
```

There is no test suite, linter, or formatter configured in this repo yet. If you add tests, use **pytest** (the de facto standard for FastAPI) — no tests exist to mirror conventions from, so use FastAPI's `TestClient`/`httpx` for endpoint tests.

CI/CD (`.github/workflows/deploy.yml`) on every push to `main`: installs `requirements.txt` as a sanity check (no tests run), builds and pushes the Docker image to Docker Hub, then SSHes into the production server and runs `docker compose pull/up` for the `smartcheck-ai-engine` service — **this deploys straight to production with no test gate and no staging step.** Be conservative editing this workflow, and flag to the user any change to `app/`, `Dockerfile`, or `requirements.txt` on `main` as something that ships to prod on merge.

## Architecture

Request flow for `POST /api/v1/prioritize` (`app/main.py`):

1. Task titles are extracted from the incoming payload and used to build a RAG query; the distinct `asignatura` values across today's tasks are also collected.
2. `app/services/vector_store.py` (`build_rag_context`) embeds the query with Gemini (`models/gemini-embedding-001`) and synthesizes context from **two** ChromaDB collections, always **filtered by `userId`** (`where={"userId": user_id}` — this is the per-user data isolation boundary; don't remove it from either collection):
   - `task_outcomes_collection` (`query_task_outcomes`): **hybrid retrieval** — fetches `CANDIDATE_POOL_SIZE` (8) candidates by cosine similarity, then re-ranks combining semantic similarity + a recency decay (`_recency_score`, half-life `RECENCY_HALF_LIFE_DAYS`=30 days off `fechaCompletado`/`fechaLimite`) + a subject-match boost (1.0 if the doc's `asignatura` is among today's tasks' subjects, else 0.0), weighted `WEIGHT_SEMANTIC`=0.6 / `WEIGHT_RECENCY`=0.25 / `WEIGHT_SUBJECT_MATCH`=0.15, before returning the final top `n_results`. Don't shortcut back to trusting Chroma's raw top-k order — that was the whole point of this pass.
   - `user_patterns_collection` (`query_user_patterns`): **exact** metadata lookup (`$and`/`$in`, not semantic) of the one aggregated doc per (`userId`, `asignatura`) for each subject appearing in today's tasks — there's only one doc per subject, so ranking by similarity would be meaningless; ChromaDB requires an explicit `$and` to combine `where` filters on more than one key (a flat multi-key dict raises).
   - **Both collections are created with `metadata={"hnsw:space": "cosine"}` (the `_COSINE_SPACE` constant) — required explicitly, since ChromaDB defaults to squared L2 distance otherwise, silently, with no error.** This was wrong for a while (every collection in this repo's history, including the very first `user_tasks_history`, was created without it) despite every diagram in the README claiming cosine similarity. `get_or_create_collection` **ignores** the `metadata` argument for a collection that already exists — it only takes effect on first creation — so fixing this in code does nothing for a collection already on disk; if you ever need to change `hnsw:space` again, you must explicitly `delete_collection` first (safe only if it's empty — check `.count()`).
3. `app/services/feature_engineering.py` (`enrich_tasks`) adds deterministic fields to every task before it reaches the prompt: `diasParaVencer`/`urgencia` (from `fechaLimite`), `tareasMismoDia` (how many other tasks share that due date), and `dependenciasPendientes`/`estaBloqueada` (resolved from each task's `dependeDe` list — not sent by Java today, see below, so currently always empty/inert; kept for forward compatibility). All fields degrade gracefully when source fields are absent.
4. `app/services/llm_engine.py` (`generate_prioritized_plan`) loads `prompts/smartcheck.txt`, fills it via `str.format()` with the current timestamp, language, user analytics, RAG context, and the enriched tasks, and sends it to `models/gemini-2.5-flash`.
5. Gemini is configured with `response_schema=PrioritizationResponse` (`app/schemas.py`) and `response_mime_type="application/json"`, so the model is constrained to return structured JSON — but this is a hint to Gemini, not a guarantee, so the response is **validated on our side too**: up to `MAX_ATTEMPTS` (3) tries, each parsed with `json.loads` and then `PrioritizationResponse.model_validate(...)` (Pydantic v2 — raises on missing/wrong-typed fields, silently drops unexpected extra ones), with a `RETRY_DELAY_SECONDS` pause between attempts. The `except Exception` in that loop is deliberately broad — it needs to catch JSON parse errors, Pydantic `ValidationError`, and whatever `google-generativeai` raises for a blocked/empty response (e.g. accessing `response.text` on a safety-filtered result), all the same way: log and retry. If every attempt fails, it raises `PrioritizationGenerationError`, which `app/main.py` turns into an HTTP `502` (not an unhandled 500) — this is the `Schema Error → Retry / Fallback` branch the README's flowchart always showed but that didn't exist until now.

**Ground truth, confirmed against RedCheck's actual `SmartCheckAIService.runDailySmartAnalysis` (Java):** this service builds a *separate, hand-rolled, Spanish-keyed* task map (`simplifiedTasks`) specifically for calling this Python engine — it is **not** the same shape as the frontend-facing `TaskResponse`/`TaskRequestDTO` (English keys), which is a different, unrelated contract used for task CRUD/display only. `simplifiedTasks` sends: `id` (number), `titulo` (← `task.getTitle()`), `descripcion`, `fechaLimite` (← `task.getDeadline()`, ISO `LocalDateTime` string or null), and `asignatura` (← `task.getSubject().getName()` — **already resolved to the subject name, not an id**). `userAnalytics` is `Map<String subjectName, Integer completionRatio>` — also keyed by name, from a raw SQL aggregation. The Java call only queries **pending** tasks (`completedDateIsNullAndDeletedFalse`) and sends no `overdue`/`completed` flags and no dependency field.

**Lesson learned the hard way:** an earlier pass "fixed" `t.get("titulo", ...)` → `t.get("title", ...)` based on the frontend's `TaskResponse` DTO, which looked authoritative but described a *different* contract than the one this service actually receives. That change was reverted. **When in doubt about what this service actually receives, `SmartCheckAIService.runDailySmartAnalysis` is the one source of truth — not the frontend's `types.ts`.**

**Still unused:** `TaskPayload.userProfile` (`app/main.py`) is never populated by Java — `EngineRequestDTO` only carries `userId`, `lang`, `userAnalytics`, `tasks` — so it always falls back to its Pydantic default. The user-profile personalization the field was meant for isn't wired up on the Java side.

Ingestion flow for `POST /api/v1/tasks/outcome` (`app/main.py` → `app/services/outcome_service.py`):

1. `register_task_outcome` takes a `TaskOutcomePayload` (`app/schemas.py`) — deliberately shaped to match `simplifiedTasks`' Spanish-keyed convention (`id`, `titulo`, `asignatura`, `fechaLimite`) plus the fields needed to record an outcome (`completada`, `fechaCompletado`, `ordenSugeridoIA`, `ordenReal`) — since that's the established convention for anything this Java service sends here, not the frontend's English `TaskResponse` convention.
2. It derives `diasRetraso`/`cumplioPlazo` (from the two dates) and `siguioOrdenIA` (from the two order fields) in Python — don't push this date/order math into the prompt or LLM.
3. It builds a natural-language Spanish summary (`_build_context_text`) — this is the text that gets embedded, so it needs to read like a real sentence for semantic retrieval to work, not a field dump.
4. It calls `upsert_task_outcome` (`vector_store.py`, `task_id=str(payload.id)`) with that text plus a metadata dict (`taskId`, `asignatura`, `completada`, `diasRetraso`, `cumplioPlazo`, `siguioOrdenIA`) — `userId` is injected inside `upsert_task_outcome` itself.
5. It then calls `app/services/pattern_service.py`'s `update_subject_pattern(userId, asignatura)`, which **rereads every `task_outcomes` doc for that user+subject** (`vector_store.get_task_outcomes`, an exact `get()`, not a top-k search) and recomputes the aggregate from scratch — completion rate, average delay over completed tasks, AI-order-adherence rate — then re-embeds it into `user_patterns_collection` under a **deterministic id** (`f"{userId}:{asignatura}"`), so it overwrites in place rather than accumulating one row per outcome. This is a full recompute, not an incremental update — intentional, since per-user-per-subject volume is small and an incremental accumulator would be premature complexity here.

This endpoint (plus the pattern recompute it triggers) is this repo's only ingestion path — nothing else writes to ChromaDB. **RedCheck's Java backend has no existing caller for it** (unlike `/prioritize`, which `SmartCheckAIService` already calls) — a new call needs to be built there, most naturally from wherever task completion/deadline changes are already handled, for the vector store to actually accumulate history. Until that's built, both `task_outcomes` and `user_patterns` stay empty and the RAG context in `/prioritize` responses stays effectively empty.

**Deferred from the original 3-collection plan:** a `plan_feedback` collection (whether a whole day's AI-generated plan/risk-level prediction was accurate) was scoped out — nothing currently tracks which AI-generated plan a given task outcome belongs to, so per-plan adherence can't be computed yet. Revisit if/when a plan identifier gets threaded through.

**Deferred from the "agentic pipeline" phase:** letting Gemini request more specific historical context itself via function calling (instead of `main.py` deciding up front what to retrieve and hand it everything) was scoped out — it needs a real multi-turn tool-use loop against the Gemini function-calling API, which is a materially bigger change than retry/validation, and the current single-shot retrieval already covers the common case. Revisit only if retrieval quality genuinely becomes the bottleneck.

**Dropped from the "hybrid retrieval" phase:** filtering by "task type" (from the original roadmap wording) isn't implemented — there's no such field anywhere in the data model (`simplifiedTasks`, `TaskResponse`, `TaskOutcomePayload`), so there's nothing to filter on. Not a gap to fill later unless such a field gets added upstream.

Key points to keep in mind when editing this flow:

- **The prompt is the product.** `prompts/smartcheck.txt` encodes the actual prioritization logic — the "6-dimension matrix" (urgency, AI-delegation potential, cognitive effort, implicit dependencies, Eisenhower impact, subject/project balance) and the risk-level rules (ALTO/MEDIO/BAJO) all live in that text file, not in Python. Changes to prioritization behavior almost always mean editing the prompt template, not the FastAPI/service code.
- The prompt template uses `{lang}`, `{current_date}`, `{user_analytics}`, `{rag_context}`, `{tasks}` placeholders filled via Python `.format()` — the JSON example block in the prompt therefore uses doubled `{{` `}}` braces to escape them.
- Output field names are Spanish (`nivelRiesgo`, `mensajeApoyo`, `planDeHoy`, `ordenDefinido`, `razonPrioridad`) regardless of the `lang` request field — only the free-text *content* of `mensajeApoyo`/`razonPrioridad` is translated. `lang` only controls language of generated prose (`es`/`en`), not field names or schema.
- `PrioritizationResponse` / `TaskPlan` in `app/schemas.py` are the source of truth for the response shape — passed directly into Gemini's `generation_config.response_schema`.
- ChromaDB is a **local, persistent** vector store (`./chroma_data`, gitignored) — not shared across instances. In Docker it must be mounted as a volume (see Dockerfile/README) or history is lost on container restart. Two collections live there: `task_outcomes` and `user_patterns` (see Architecture above) — there used to be a single `user_tasks_history` collection; it's gone, don't recreate it.
- `vector_store.py` catches embedding/query failures and degrades gracefully (returns `[]`, logs to stdout) so RAG unavailability never breaks `/api/v1/prioritize`; keep that fallback behavior when touching this file.
- `Dockerfile` builds as non-root (`redcheckuser`) via a multi-stage build — preserve that when changing it.

## Language convention

Default to **English** for everything you write or edit: Python identifiers, code comments, docstrings, and the text sent to Gemini in `prompts/smartcheck.txt`. The exception is the AI-engine-facing HTTP contract: **every field this service sends or receives is Spanish** (`titulo`, `fechaLimite`, `asignatura`, `nivelRiesgo`, `mensajeApoyo`, `planDeHoy`, `ordenDefinido`, `razonPrioridad`, etc.) — confirmed in `SmartCheckAIService.runDailySmartAnalysis` (Java), which deliberately re-maps its own English `Task` entity into Spanish keys specifically for calling this service. **Don't "fix" these to English by analogy with the frontend's `TaskResponse`/`TaskRequestDTO` types** — those describe a different, unrelated contract (task CRUD/display), not what this service talks to; doing so once already introduced a real bug (see Architecture). When adding fields to any endpoint here, follow the Spanish convention. Note the prompt template currently mixes Spanish (most of the body) with English (the `CRITICAL LANGUAGE INSTRUCTION` and `PRECOMPUTED SIGNALS` blocks) — new prompt edits should lean English per this convention, but a full-file rewrite isn't necessary just to comply.
