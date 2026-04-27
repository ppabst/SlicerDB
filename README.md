<p align="left">
  <img src="app/static/img/logo.svg" width="120" alt="Slicekeeper">
</p>

# Slicekeeper

**Die Datenbank für deine Slicer Profile.**

Versionierte Verwaltung von 3D-Drucker-Slicer-Profilen pro Drucker × Düse × Bauplatte × Qualität × Filament × Slicer — mit Auto-Parser für OrcaSlicer-JSON und Anycubic-Bundles, Original-Datei-Backup und Spoolman-Anbindung.

> **Status:** Phase 1.6 läuft. Siehe [PLAN.md](PLAN.md) für die Roadmap.
> Repository und Docker-Image heißen aus historischen Gründen weiterhin `SlicerDB`/`slicerdb` — die Marke ist Slicekeeper.

---

## Author / Lizenz

Slicekeeper ist von **LennyK** entwickelt und veröffentlicht.

```
Copyright (C) 2026 LennyK
Quelle:  https://github.com/ppabst/SlicerDB
Lizenz:  GPL-3.0-or-later
```

Jede Quelldatei trägt SPDX-Header (`SPDX-FileCopyrightText: 2026 LennyK` und `SPDX-License-Identifier: GPL-3.0-or-later`). Siehe [`NOTICE`](NOTICE) und [`LICENSE`](LICENSE).

**Kommerzieller Wiederverkauf** dieser Software — ganz oder in Teilen — ohne Einhaltung der GPL-3.0-Bedingungen ist unzulässig und verletzt das Urheberrecht. Forks und Modifikationen sind willkommen, müssen aber selbst unter GPL-3.0 stehen und die Autorenangaben erhalten.

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
