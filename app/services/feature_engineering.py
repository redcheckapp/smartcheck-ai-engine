from datetime import datetime
from typing import Any, Optional

# Days-until-due thresholds for urgency buckets. Keep in sync with the
# PRECOMPUTED SIGNALS section of prompts/smartcheck.txt.
CRITICAL_DAYS_THRESHOLD = 2
UPCOMING_DAYS_THRESHOLD = 6


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _clasificar_urgencia(dias_para_vencer: Optional[int], overdue: Optional[bool] = None) -> str:
    if dias_para_vencer is None:
        # No `fechaLimite` to compute from — fall back to an `overdue` flag,
        # if the caller ever sends one (SmartCheckAIService.simplifiedTasks
        # does not today, so this branch is currently always None/False).
        return "atrasada" if overdue else "sin_fecha"
    if dias_para_vencer <= CRITICAL_DAYS_THRESHOLD:
        return "atrasada" if dias_para_vencer < 0 else "critica"
    if dias_para_vencer <= UPCOMING_DAYS_THRESHOLD:
        return "proxima"
    return "normal"


def enrich_tasks(tasks: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """Adds deterministic urgency, same-day density, and dependency fields to each task.

    Expects the shape RedCheck's `SmartCheckAIService.runDailySmartAnalysis`
    actually sends (`simplifiedTasks`): `id`, `titulo`, `descripcion`,
    `fechaLimite` (ISO date/datetime string or null), `asignatura` (subject
    name, already resolved server-side — passed through untouched here).
    `dependeDe` (list of other tasks' `id`s in this batch that must be
    resolved first) is NOT part of that payload yet, so it always degrades to
    "no dependencies" today; kept for forward compatibility. `tasks` is
    assumed to be the user's full set of *pending* tasks, so a `dependeDe` id
    absent from this batch is treated as already resolved.
    """
    dias_por_tarea: dict[Any, Optional[int]] = {}
    fecha_por_tarea: dict[Any, Optional[str]] = {}
    titulo_por_id: dict[Any, str] = {}

    for tarea in tasks:
        task_id = tarea.get("id")
        fecha_limite = _parse_date(tarea.get("fechaLimite"))
        dias_por_tarea[task_id] = (fecha_limite.date() - now.date()).days if fecha_limite else None
        fecha_por_tarea[task_id] = fecha_limite.date().isoformat() if fecha_limite else None
        titulo_por_id[task_id] = tarea.get("titulo", "")

    conteo_por_fecha: dict[str, int] = {}
    for fecha in fecha_por_tarea.values():
        if fecha:
            conteo_por_fecha[fecha] = conteo_por_fecha.get(fecha, 0) + 1

    enriched = []
    for tarea in tasks:
        task_id = tarea.get("id")
        fecha = fecha_por_tarea[task_id]

        dependencias_pendientes = [
            titulo_por_id.get(dep_id, str(dep_id))
            for dep_id in (tarea.get("dependeDe") or [])
            if dep_id in titulo_por_id
        ]

        enriched.append({
            **tarea,
            "diasParaVencer": dias_por_tarea[task_id],
            "urgencia": _clasificar_urgencia(dias_por_tarea[task_id], tarea.get("overdue")),
            "tareasMismoDia": max(conteo_por_fecha.get(fecha, 1) - 1, 0) if fecha else 0,
            "dependenciasPendientes": dependencias_pendientes,
            "estaBloqueada": len(dependencias_pendientes) > 0,
        })

    return enriched
