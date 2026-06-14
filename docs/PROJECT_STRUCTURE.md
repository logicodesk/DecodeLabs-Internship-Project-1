# Project Structure

This repository is organized to keep the FastAPI backend, frontend assets, and AI utilities separated by responsibility.

## Top-Level Files

- `app.py` - FastAPI application entry point and HTTP routes.
- `auth.py` - Password hashing and JWT token helpers.
- `chatbot.py` - Core chat orchestration, memory handling, and tool usage.
- `database.py` - SQLAlchemy engine and session setup.
- `models.py` - Database models for users, sessions, and messages.
- `rag.py` - File ingestion, chunking, and FAISS index utilities.
- `requirements.txt` - Python dependencies for the application.
- `start.bat` - Windows startup helper.

## Application Assets

- `static/` - Frontend JavaScript and CSS.
- `templates/` - Jinja2 HTML templates.
- `uploads/` - Uploaded source files used for retrieval.
- `faiss_indexes/` - Session-specific vector indexes and chunk metadata.

## Repository Hygiene

- `.env.example` - Environment variable template.
- `.gitignore` - Excludes secrets, caches, virtual environments, and local artifacts.
- `.editorconfig` - Shared formatting rules.
- `.github/workflows/ci.yml` - Continuous integration workflow.

## Notes

The project is designed around a single FastAPI service with authenticated chat, session memory, and optional document retrieval. Keep additions aligned with those responsibilities so the codebase stays easy to maintain.