# Changelog

All notable changes to Slicekeeper.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-04-27

First public release.

### Added
- **Hardware inventory** — printers, nozzles (per printer, per diameter / material), build plates with a seeded catalogue of common surfaces (Bambu Cool/Smooth/Textured/Engineering/HighTemp, Anycubic Smooth/Textured PEI, Prusa Smooth/Textured/Satin, plus generic Glass / Garolite / Carborundum).
- **Slicer registry** — OrcaSlicer, Anycubic Slicer Next, Elegoo Slicer (latter two are Orca forks), with a profile-format hint per slicer.
- **Print profiles** as the central entity — composed of printer × nozzle × filament × slicer × build plate × layer height × quality label. Versioned: every upload of a slicer file produces a new immutable `ProfileVersion` with the original blob preserved.
- **Auto-detection** of the uploaded file format by sniffing magic bytes — ZIP bundles get unpacked, plain JSON gets parsed, regardless of what the slicer entry claims.
- **Two parsers built in:**
  - `orca-json` — single-file Orca/Anycubic/Elegoo process or filament JSON
  - `anycubic-bundle` — ZIP archive of Orca-style JSONs (`.anycubic_printer`, `.elegoo_printer`, OrcaSlicer config bundles)
- **Inheritance awareness** — when a user-saved profile carries an `inherits` reference, every key in that section is a delta from the parent. The detail page surfaces a yellow banner naming the parent and marks each delta row with ⚠ + amber tinting. Sections without `inherits` are clearly marked as "eigenständig — N Werte explizit".
- **Manual settings editor** per version — a textarea (`key = value` per line, with `#` comments and inline `  # ...` trailing comments) merges with auto-extracted values; user input wins on conflict. Saves replace the JSON; re-parse re-extracts from the original blob.
- **Inline edit** on every list row (printer, nozzle, slicer, filament, build plate, profile) via HTMX `outerHTML` swaps. Click the entity name or a Bearbeiten button — the row turns into a form spanning all columns; Save or Cancel swings back.
- **Referential integrity on delete** — a leaf entity (printer, nozzle, filament, slicer, build plate) cannot be deleted while a profile points at it. The blocked delete returns the same list with a rose-coloured banner listing the call sites with clickable links to the offending profiles or nozzles.
- **Spoolman read-only sync** — pulls filaments + vendor info from a self-hosted Spoolman over its REST API. Synced rows show a `↻ Spoolman` badge and a `→ Spoolman` link button (opens the Spoolman page for that filament in a new tab when a browser-reachable URL is configured). Locally created filaments stay editable.
- **Settings page in the GUI** — Spoolman API URL, browser-public URL, auto-sync toggle, sync interval (0.05–24 h). Connection-test button hits Spoolman's `/api/v1/info` without saving. Background sync loop reads the DB on every iteration so config changes take effect within a minute, no container restart needed. Bootstrap from `SLICERDB_SPOOLMAN_*` env vars on first start; DB is canonical thereafter.
- **Filament UX** — native colour picker coupled to a hex text input, compact temperature inputs (Hotend min/max, Bett °C) with right-aligned tabular numerals.
- **GPL-3.0** license. Every Python file and Jinja template carries an SPDX header (`SPDX-FileCopyrightText: 2026 LennyK`, `SPDX-License-Identifier: GPL-3.0-or-later`). `NOTICE` and `LICENSE` at the repo root.

### Tech
- Python 3.13 + FastAPI + SQLModel (SQLAlchemy 2.0 + Pydantic v2) + Alembic.
- HTMX + Tailwind CSS v4 standalone (no Node.js toolchain).
- Jinja2 templates, server-rendered.
- SQLite with WAL mode, FK enforcement on, journal at `synchronous=NORMAL`.
- Multi-stage Docker image based on `python:3.13-slim-bookworm`, built with `uv` for fast deterministic installs.
- 53 tests covering CRUD lifecycles, integrity blocks, parser edge cases, Spoolman sync, settings persistence, inline edit cycles. Ruff clean.

### Known limits
- Cura `.curaprofile` parser not yet implemented — files of that format upload but won't auto-extract settings (manual textarea works).
- No round-trip export — Slicekeeper stores and shows settings, but doesn't generate slicer-importable files. Re-upload the original blob via download for that.
- Single-user; no auth. Designed for LAN deployment behind a reverse proxy if you need access control.
- amd64-only Docker image at this release (arm64 will follow).
