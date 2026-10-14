# Recipe Book Backend

FastAPI backend with MongoDB, managed with `uv`.

## Features
- Async MongoDB integration using `motor`
- Pydantic v2 schemas and validation
- Cloud-native health probes (`/health/live`, `/health/ready`, `/health/startup`)
- Recipe scaling engine
- Flexible search and filtering (tags, cuisines, categories, cooking time)
- 12-Factor app configuration with environment variables

## Local Development
```bash
# Sync dependencies
uv sync --extra dev

# Run FastAPI dev server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
