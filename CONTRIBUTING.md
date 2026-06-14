# Contributing

Thanks for helping improve the project. Keep changes focused, minimal, and easy to review.

## Setup

1. Create and activate a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set your API key.
4. Start the app with `uvicorn app:app --reload`.

## Guidelines

- Keep repository structure predictable and documented.
- Update `requirements.txt` when adding new Python imports.
- Prefer small, isolated changes over broad rewrites.
- Avoid committing secrets, generated data, or local environments.

## Pull Requests

- Describe what changed and why.
- Include verification steps for the affected area.
- Add or update documentation when behavior changes.