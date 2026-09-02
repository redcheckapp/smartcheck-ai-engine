# Contributing to SmartCheck AI Engine

Thank you for your interest in contributing to the **SmartCheck AI Engine**! We welcome contributions that improve performance, expand RAG capabilities, or refine code quality under the terms of the GNU Affero General Public License v3.0 (AGPLv3).

## Development Standards

To maintain code consistency and reliability across the platform, please adhere to the following standards:

* **Language:** All source code, comments, docstrings, and commit messages must be written in professional English.
* **Docstrings:** Follow PEP 257 standards for all module, class, and function docstrings.
* **Commit Messages:** Follow the **Conventional Commits** specification (e.g., `feat(rag): add similarity threshold filtering`, `fix(api): handle missing user analytics`).
* **Dependencies:** Keep `requirements.txt` strictly version-pinned. Do not introduce unpinned packages.

## Getting Started

1. **Fork and Clone** the repository to your local machine.
2. **Set up the Python Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
  Create a `.env` file in the root directory and add your API key:
  ```env
  GEMINI_API_KEY=your_google_ai_studio_key_here
  ```

4. **Run Locally**:
  ```bash
  uvicorn app.main:app --reload
  ```

## Pull Request Workflow

1. Create a descriptive feature branch from `main` (e.g., `feature/optimize-vector-search` or `fix/json-parsing`).
2. Verify that your code is clean, well-documented, and free of hardcoded secrets or credentials.
3. Submit a Pull Request targeting the `main` branch with a concise description of the changes introduced.
