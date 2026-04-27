<p align="left">
  <img src="app/static/img/logo.svg" width="120" alt="Slicekeeper">
</p>

# Slicekeeper

**Die Datenbank für deine Slicer Profile.** Versioniere und vergleiche deine 3D-Drucker-Slicer-Settings pro Drucker × Düse × Bauplatte × Filament × Qualitätsstufe — mit Auto-Parser für OrcaSlicer-JSON und Anycubic/Elegoo-Bundles, Original-Datei-Backup, Inheritance-Erkennung und Spoolman-Anbindung.

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL_3.0-blue.svg)](LICENSE) ![Status: 1.0](https://img.shields.io/badge/Status-1.0.0-success) ![Python: 3.13](https://img.shields.io/badge/Python-3.13-blue) ![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)

---

## Was es kann

- **Hardware-Inventar** — Drucker, Düsen, Bauplatten (mit Katalog der gängigen Bambu / Anycubic / Prusa / generischen Oberflächen)
- **Profile** als Drucker × Düse × Filament × Slicer × Bauplatte × Layer × Qualität
- **Versionsverwaltung** — jede Profil-Datei hochgeladen wird zu einer immutable Version mit Datei-Backup, Bewertung (gut/schlecht/ungetestet) und freier Notiz
- **Auto-Parser** für OrcaSlicer-JSON, `.anycubic_printer`, `.elegoo_printer` (Orca-Forks teilen Format) — extrahiert Settings, erkennt Delta-Profile mit `inherits`, markiert Abweichungen vom Eltern-Profil
- **Spoolman-Sync** — read-only-Mirror der Filament-Liste; synchronisierte Rollen zeigen `↻ Spoolman`-Badge und springen per Link in Spoolman
- **Inline-Edit** und **Cross-Check beim Löschen** (verhindert das Wegnehmen von etwas, das ein Profil noch verwendet)
- **GUI für Spoolman-Settings** — kein Container-Neustart bei Konfigänderung nötig
- **HTMX-UI**, server-rendered, kein Node-Build-Schritt

## Schnellstart

Voraussetzung: Linux-Host mit Docker + Compose.

```bash
mkdir -p slicekeeper/data
cd slicekeeper

# Compose-Datei holen
curl -fsSLO https://raw.githubusercontent.com/ppabst/SlicerDB/main/docker-compose.example.yml

# Starten
docker compose -f docker-compose.example.yml up -d
```

UI öffnet sich auf **http://localhost:8080**.

Die Daten landen in `./data/db.sqlite` und `./data/files/` (deine hochgeladenen Slicer-Profile). Beides bleibt erhalten zwischen Neustarts und Updates.

### Mit Spoolman koppeln

1. Browser auf http://localhost:8080/settings
2. **Spoolman-URL (für API)** auf die Adresse, unter der dein Container Spoolman erreicht — z.B. `http://192.168.1.100:7912` oder, wenn beide auf demselben Host und du `network_mode: host` benutzt, `http://localhost:7912`
3. **Öffentliche URL (für Browser-Links)** optional — die LAN-IP / der Hostname, mit dem dein Browser Spoolman aufrufen kann. Macht den `→ Spoolman`-Knopf in der Filament-Liste klickbar
4. **Verbindung testen** drücken, dann **Speichern**

Auto-Sync läuft im Default alle 6 Stunden, manueller Sync per Button auf der Filament-Seite.

### Update auf eine neuere Version

```bash
docker compose -f docker-compose.example.yml pull
docker compose -f docker-compose.example.yml up -d
```

DB-Migrationen laufen automatisch beim Start.

## Konfiguration

Die meiste Konfiguration findest du in der GUI unter **Einstellungen**. Folgende Env-Variablen werden beim **ersten** Start als Initialwerte übernommen, danach hat die DB-Konfig Vorrang:

| Variable | Default | Zweck |
|---|---|---|
| `SLICERDB_DATA_DIR` | `/data` | Volume-Mount für SQLite + Profil-Dateien |
| `SLICERDB_BIND_HOST` | `0.0.0.0` | Bind-Adresse |
| `SLICERDB_BIND_PORT` | `8080` | HTTP-Port im Container |
| `SLICERDB_SPOOLMAN_URL` | _(leer)_ | initial-URL für die Spoolman-API (ohne Trailing-Slash) |
| `SLICERDB_SPOOLMAN_PUBLIC_URL` | _(leer)_ | initial-URL für Browser-Links |
| `SLICERDB_SPOOLMAN_AUTO_SYNC` | `true` | Hintergrund-Sync aktiv? |
| `SLICERDB_SPOOLMAN_SYNC_INTERVAL_SECONDS` | `21600` | Intervall in Sekunden |

## Deployment-Hinweise

- **Hinter einem Reverse Proxy** (Caddy/Traefik/nginx) für TLS und ggf. Auth — Slicekeeper bringt selbst keine Authentifizierung mit. Designed für LAN.
- **`network_mode: host`** ist die einfachste Konfig wenn Spoolman auf dem gleichen Host läuft (LXC-typisch). Sonst Bridge-Netzwerk + Spoolman-URL = LAN-IP.
- **Backup**: das gesamte `./data/`-Verzeichnis sichern. SQLite-WAL-Dateien (`db.sqlite-wal`, `db.sqlite-shm`) müssen mitgesichert werden, oder vor dem Backup `docker compose stop` ausführen.

## Architektur

```
┌─────────────────────────────────────┐
│ Docker Container (Slicekeeper)      │
│                                     │
│  FastAPI + HTMX + Jinja2            │
│        │                            │
│        ↓                            │
│  SQLModel / SQLAlchemy 2.0          │
│        │                            │
│        ↓                            │
│  SQLite (WAL) + Files-Volume        │
│                                     │
│  Background async task ↻ Spoolman   │
└────────────┬────────────────────────┘
             │
             │ HTTP /api/v1/filament
             ↓
        Spoolman (separat)
```

Eine Datei-Hierarchie:

```
data/
├── db.sqlite              # alles strukturierte
├── db.sqlite-wal
├── db.sqlite-shm
└── files/
    └── profile-123/
        ├── v0001-...json
        ├── v0002-....anycubic_printer
        └── ...
```

## Slicer-Format-Support

| Slicer | Format | Status |
|---|---|---|
| OrcaSlicer | `.json` (Process / Filament / Printer) | ✅ Auto-Parse |
| Anycubic Slicer Next | `.anycubic_printer` (ZIP-Bundle) | ✅ Auto-Parse |
| Elegoo Slicer | `.elegoo_printer` (ZIP-Bundle) | ✅ Auto-Parse |
| Cura / `.curaprofile` | ZIP mit INI | ⏳ geplant |
| PrusaSlicer / `.ini` | INI | ⏳ geplant |

Nicht unterstützte Formate werden als opaker Blob gespeichert (Download funktioniert), Settings können manuell pro Version eingetragen werden.

## Development

```bash
git clone https://github.com/ppabst/SlicerDB.git
cd SlicerDB

uv sync                       # deps installieren
./scripts/build_css.sh        # Tailwind one-shot
./scripts/dev.sh              # Dev-Server mit Auto-Reload + Tailwind --watch

uv run pytest                 # Tests
uv run ruff check .           # Lint
```

Image lokal bauen:
```bash
docker compose -f docker/compose.yml up --build
```

## Author / Lizenz

Slicekeeper ist von **LennyK** entwickelt und unter der **GPL-3.0-or-later** veröffentlicht.

```
Copyright (C) 2026 LennyK
Source: https://github.com/ppabst/SlicerDB
```

Jede Quelldatei trägt SPDX-Header. Siehe [`NOTICE`](NOTICE) und [`LICENSE`](LICENSE).

**Kommerzieller Wiederverkauf** dieser Software — ganz oder in Teilen — ohne Einhaltung der GPL-3.0-Bedingungen (insbesondere die Verpflichtung, Quelltext bei Verteilung beizufügen) verletzt das Urheberrecht. Forks und Modifikationen sind willkommen, müssen aber selbst unter GPL-3.0 stehen und die Autorenangaben erhalten.

Bug-Reports + Feature-Requests: [GitHub Issues](https://github.com/ppabst/SlicerDB/issues)
