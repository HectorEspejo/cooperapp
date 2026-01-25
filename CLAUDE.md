# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CooperApp is a web application for managing international cooperation projects for Spanish NGOs. Built with FastAPI backend and htmx-powered frontend using Jinja2 templates.

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (auto-reload enabled)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Health check
curl http://localhost:8000/health
```

## Architecture

### Backend Stack
- **FastAPI** with Pydantic schemas for validation
- **SQLAlchemy 2.0** ORM with SQLite (file: `cooperapp.db`)
- **Jinja2** for server-side templating

### Frontend Stack
- **htmx** for dynamic updates without full page reloads
- Vanilla HTML/CSS/JS
- Theme color: `#8B1E3F` (Prodiversa brand)

### Key Directories
```
app/
├── main.py              # FastAPI app entry, lifespan events, router mounts
├── config.py            # Pydantic settings (loads from .env)
├── database.py          # SQLAlchemy engine, session, Base class
├── models/              # SQLAlchemy ORM models
├── schemas/             # Pydantic request/response schemas
├── services/            # Business logic (CRUD operations)
├── routers/api/         # REST API endpoints (/api/*)
├── views/               # HTML view endpoints (returns TemplateResponse)
├── templates/           # Jinja2 templates
│   ├── base.html        # Main layout
│   ├── components/      # Reusable UI components
│   ├── pages/           # Full page templates
│   └── partials/        # htmx partial templates for dynamic updates
└── static/              # CSS, JS (htmx.min.js)
```

### Data Model

**Project** is the central entity with:
- Enums: `EstadoProyecto`, `TipoProyecto`, `Financiador`
- One-to-many: `Plazo` (deadlines with title, date, completion status)
- Many-to-many: `ODSObjetivo` (UN Sustainable Development Goals)

ODS data is seeded on app startup via `ProjectService.seed_ods()`.

### Routing Pattern

- `/api/projects/*` - REST API (JSON responses)
- `/projects/*` - HTML views (htmx-compatible)
- Partials in `/projects/partials/*` return HTML fragments for htmx swaps

### Form Handling

Forms use standard POST with `python-multipart`. Multi-value fields (ODS checkboxes, plazos) use array notation: `name="ods_ids[]"`, `name="plazo_titulo[]"`.

## Language

UI text and field names are in Spanish (this is for Spanish NGOs). Code comments and variable names use English.
