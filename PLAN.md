# SlicerDB — Implementierungsplan

**Stand:** 2026-04-25
**Status:** Planungsentwurf, wartet auf Freigabe

## 1. Ziel

Selbst gehostete Web-App im Docker-Container, die Slicer-Einstellungen pro
Drucker × Nozzle × Qualitätsstufe × Filament × Slicer **versioniert** verwaltet.
Original-Slicer-Dateien als Anhang, perspektivisch Round-Trip-Export.
Single-User, LAN-only, später Open Source.

## 2. Tech-Stack (recherchiert, Stand 04/2026)

| Schicht | Wahl | Warum |
|---|---|---|
| Sprache | Python 3.14 | lokal vorhanden, in der Linux-Welt verbreitet |
| Web-Framework | **FastAPI 0.136.x** | aktuelle stabile Linie, async, OpenAPI |
| ORM | **SQLModel** (auf SQLAlchemy 2.0 + Pydantic v2) | von FastAPI-Autor; ein Modell für DB + API |
| Migrations | **Alembic** | Standard für SQLAlchemy |
| DB | **SQLite** (WAL-Mode) | 1 Nutzer, einfach zu sichern, Volume-Mount |
| Templates | **Jinja2** | mit FastAPI nativ |
| Frontend | **HTMX + Tailwind CSS (Standalone CLI)** | keine Node-Toolchain, server-rendered, ideal für Admin-Apps |
| HTTP-Client (Spoolman) | **httpx** (async) | Standard im FastAPI-Ökosystem |
| Tests | **pytest + httpx test client** | |
| Code-Qualität | **ruff** (Lint+Format) + **mypy** | aktuelle Defaults 2026 |
| Container | **multi-stage Dockerfile**, `python:3.14-slim` | klein, reproducible |

**Bewusst NICHT gewählt:**
- SvelteKit/React → Node-Toolchain unnötig für CRUD-Admin-UI bei einem Nutzer
- Postgres → Overkill für Single-User
- Auth-Framework → LAN-only, später ggf. Reverse-Proxy-Auth davorschalten

## 3. Domänenmodell

```
Printer
  └─ id, name, manufacturer, model, build_volume, notes, created_at

Nozzle
  └─ id, printer_id (FK), diameter_mm, material (brass/hardened/...), notes

Slicer
  └─ id, name, version, profile_format (orca-json | prusa-ini | cura-profile)

Filament
  └─ id, name, manufacturer, material (PLA/PETG/...), color_hex,
     hotend_temp_min, hotend_temp_max, bed_temp,
     spoolman_filament_id (nullable),
     synced_at (nullable, wenn aus Spoolman)

PrintProfile (= ein "Setup")
  └─ id, name, printer_id, nozzle_id, filament_id,
     slicer_id, layer_height_mm, quality_label (Draft/Standard/Fine/Custom),
     active_version_id (FK nullable), notes, created_at, updated_at

ProfileVersion (immutable)
  └─ id, profile_id, version_no (auto-increment pro profile),
     created_at, change_note (text),
     settings_json (JSON, ab Phase 3 strukturiert),
     raw_filename, raw_format, raw_blob_path,
     rating (nullable: gut/schlecht/ungetestet),
     rating_note (nullable text)
```

**Index/Constraints:**
- Unique (profile_id, version_no)
- FK-Cascade auf delete für ProfileVersion
- Filament.spoolman_filament_id unique (nullable)

## 4. Slicer-Formate (recherchiert)

| Slicer | Format | Notiz |
|---|---|---|
| OrcaSlicer | JSON (.json) | Typen: machine_model, machine, filament, process; Inheritance über `inherits` |
| Anycubic Slicer Next | JSON (.json) | OrcaSlicer-Fork → identisches Format |
| Elegoo Slicer | .curaprofile (zip mit INI/JSON intern) | Cura-Engine — anders als Orca |

**Konsequenz für den Plan:**
- Phase 1 speichert alle Formate opak (Datei rein, Datei raus)
- Phase 3 priorisiert Orca-JSON-Parser (deckt Orca + Anycubic ab — 2 von 3 Slicern)
- Phase 3+ Cura-Parser folgt

## 5. Container-Layout

```
slicerdb/
├── app/
│   ├── main.py              # FastAPI app, mount static, include routers
│   ├── config.py            # Pydantic Settings (ENV-Variablen)
│   ├── db.py                # Engine, Session, init
│   ├── models/              # SQLModel Klassen
│   ├── routers/             # api/ und ui/ getrennt
│   ├── services/            # spoolman_client, file_storage, parsers/
│   ├── parsers/             # orca_json.py, cura_profile.py (Phase 3+)
│   ├── templates/           # Jinja2 (HTMX-Fragmente + ganze Seiten)
│   └── static/              # Tailwind output, htmx.min.js
├── alembic/                 # Migrations
├── tests/
├── docker/
│   ├── Dockerfile           # multi-stage
│   └── compose.yml
├── scripts/
│   ├── dev.sh               # tailwind --watch + uvicorn --reload
│   └── build_css.sh         # Tailwind one-shot
├── .github/workflows/ci.yml # ruff + mypy + pytest + docker build
├── pyproject.toml           # uv/poetry, ruff, mypy config
├── README.md
└── PLAN.md (dieses Dokument)
```

**Docker-Volumes (compose):**
- `./data/db.sqlite` → `/app/data/db.sqlite`
- `./data/files/` → `/app/data/files/` (Profil-Blobs)

**ENV-Variablen:**
- `SPOOLMAN_URL` (optional, z.B. `http://192.168.x.x:7912`)
- `SLICERDB_DATA_DIR=/app/data`
- `SLICERDB_BIND=0.0.0.0:8080`

## 6. Roadmap (Phasen mit Akzeptanzkriterien)

### Phase 0 — Setup
- GitHub-Repo `ppabst/SlicerDB` privat anlegen
- Lokales Repo, `.gitignore`, README, LICENSE-Platzhalter
- pyproject.toml mit ruff+mypy+pytest
- Dockerfile + compose.yml, „Hello SlicerDB" lauffähig auf `:8080`
- CI: ruff + mypy + pytest + docker build green

**Done wenn:** `docker compose up` zeigt Welcome-Page im Browser.

### Phase 1 — MVP CRUD
- Schema + Alembic-Init
- CRUD für: Printer, Nozzle, Slicer, Filament (manuell), PrintProfile
- File-Upload für ProfileVersion mit Notiz, automatisches version_no++
- Datei-Download je Version
- HTMX-UI: Listen + Detail + Inline-Edit, Tailwind-Styling
- Aktive Version markieren, Versionshistorie pro Profil

**Done wenn:** Du legst einen Drucker, Nozzle, Filament, Profil und 2 Versionen an, lädst die Datei wieder runter — alles funktioniert.

### Phase 2 — Spoolman-Sync
- httpx-Client, Endpunkte `/api/v1/filament`, `/api/v1/vendor`
- Sync-Button in UI (lazy) + Hintergrund-Cron alle 6h (FastAPI BackgroundTasks)
- Filament-Auswahl im Profil bevorzugt Spoolman-Einträge
- Konflikt-Strategie: lokal nur read-only von Spoolman-Quelldaten

**Done wenn:** Spoolman-Filamente erscheinen, sind in Profilen wählbar, werden bei Änderung in Spoolman aktualisiert.

### Phase 3 — Parser für OrcaSlicer-JSON
- Parser für Orca-JSON (Process + Filament + Printer)
- Strukturierte Anzeige neben Datei (Layer Height, Speeds, Temps, Retraction…)
- Diff-Ansicht zwischen 2 Versionen (key-by-key)
- Anycubic Next teilt Format → automatisch unterstützt

**Done wenn:** Du lädst Orca-Profil, siehst die Settings tabellarisch, vergleichst v1 vs v2.

### Phase 4 — Cura-/Elegoo-Parser
- .curaprofile entzippen, INI/JSON parsen
- Strukturierte Anzeige analog zu Phase 3

### Phase 5 — Round-Trip-Export
- Settings im UI editieren → neue Version generiert valide Slicer-Datei
- Beginn mit OrcaSlicer (höchste Coverage)

### Phase 6 — Druck-Logging
- „Ich habe mit Version X gedruckt, Ergebnis: gut/schlecht + Notiz"
- Surface: bestbewertete Version pro Profil

### Phase 7 — Public Release
- Repo auf public, Docs, Beispiele, Compose für Endnutzer

## 7. Dev-Umgebung

**Option A (Vorschlag):** Lokal (Mac) entwickeln + Docker-Image am Ende einer Phase auf die Spoolman-VM deployen, dort echt testen.

**Option B:** Direkt auf der Spoolman-VM entwickeln (SSH + VS Code Remote / oder lokal-edit + sync).

→ Empfehlung: **Hybrid** — lokal coden, aber bei Phase 2 (Spoolman-Sync) direkt gegen die VM-Spoolman-Instanz testen. Die VM bekommt SlicerDB als zweiten Container neben Spoolman.

## 8. Entscheidungen (2026-04-25)

- **Repo:** `gh` wird installiert, Repo `ppabst/SlicerDB` privat via gh CLI angelegt
- **Deploy-Ziel:** Spoolman-VM, SlicerDB als zweiter Container neben Spoolman
- **Lizenz:** **GPL-3.0** — Copyleft, Forks müssen open source bleiben

## 9. Noch offen

1. **Spoolman-VM:**
   - IP/Hostname?
   - SSH-Zugang (User, Key vorhanden)?
   - OS und Docker-Version?
2. **Spoolman-URL** (Port — Standard 7912 oder anders konfiguriert)?
3. **Beispiel-Profildateien** in `samples/` — relevant für Phase 3+

## 9. Quellen (recherchiert 2026-04-25)

- [FastAPI Releases](https://github.com/fastapi/fastapi/releases) — 0.136.1 vom 23.04.2026
- [SQLModel](https://sqlmodel.tiangolo.com/) — auf SQLAlchemy 2.0 + Pydantic v2
- [Spoolman REST API v1](https://donkie.github.io/Spoolman/)
- [OrcaSlicer Wiki — Profile-Format](https://github.com/OrcaSlicer/OrcaSlicer/wiki/How-to-create-profiles)
- [Anycubic Slicer Next Wiki](https://wiki.anycubic.com/en/software-and-app/new-page-anycubic-slicer-beta(orca-version)) — OrcaSlicer-basiert
- [Elegoo Slicer / Cura .curaprofile](https://community.ultimaker.com/topic/26662-cura-profile-location/) — zip mit INI/JSON
- [FastAPI + HTMX + Tailwind Beispiel](https://github.com/volfpeter/fastapi-htmx-tailwind-example)
- [HTMX vs SvelteKit für Admin-Apps](https://medium.com/django-journal/htmx-vs-sveltekit-for-django-frontends-2026-migration-benchmarks-from-20-projects-3e55afc1e64e)
