# SlicerDB

Versionierte Verwaltung von 3D-Drucker-Slicer-Profilen — pro Drucker × Düse × Qualitätsstufe × Filament × Slicer, mit Original-Datei-Backup und Spoolman-Anbindung.

> **Status:** Phase 0 (Setup). Siehe [PLAN.md](PLAN.md) für die Roadmap.

## Stack

- **Backend:** FastAPI + SQLModel (auf SQLAlchemy 2.0 + Pydantic v2)
- **DB:** SQLite (WAL-Mode) mit Alembic-Migrationen
- **Frontend:** HTMX + Tailwind CSS v4 (Standalone, kein Node) + Jinja2
- **Container:** Multi-stage Docker, Python 3.13-slim, `uv` für Deps
- **Lizenz:** GPL-3.0-or-later

## Schnellstart (Docker)

```bash
docker compose -f docker/compose.yml up --build
# UI: http://localhost:8080
# Health: http://localhost:8080/healthz
```

Daten liegen im Mount `./data/` (DB + hochgeladene Profil-Dateien).

## Entwicklung lokal (ohne Docker)

```bash
# uv installieren falls noch nicht da
curl -LsSf https://astral.sh/uv/install.sh | sh

# Deps installieren + venv erstellen
uv sync

# Tailwind output bauen (one-shot)
./scripts/build_css.sh

# Dev-Server (Auto-Reload + Tailwind --watch parallel)
./scripts/dev.sh
```

## Konfiguration

ENV-Variablen (alle mit Prefix `SLICERDB_`):

| Variable | Default | Zweck |
|---|---|---|
| `SLICERDB_DATA_DIR` | `./data` | DB- und File-Verzeichnis |
| `SLICERDB_SPOOLMAN_URL` | _(leer)_ | z.B. `http://192.168.x.x:7912` |
| `SLICERDB_BIND_HOST` | `0.0.0.0` | |
| `SLICERDB_BIND_PORT` | `8080` | |
| `SLICERDB_DEBUG` | `false` | |

## Tests

```bash
uv run pytest
uv run ruff check .
uv run mypy app
```
