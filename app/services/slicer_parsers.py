# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
"""Best-effort parsers that pull a flat ``key → value`` map out of a slicer
profile file.

Phase 1.5 scope: only the formats we can read with the standard library.
Anything we can't parse returns an empty dict — the user can still type the
settings manually.

Supported now:
- ``orca-json``: a single JSON object with string-encoded values, as exported
  by OrcaSlicer's "Export" → "Export preset bundle" → "Process JSON".
- ``anycubic-bundle``: a ZIP archive (``.anycubic_printer`` / ``.anycubic_3mf``)
  containing ``bundle_structure.json`` and one or more JSONs in
  ``printer/``, ``filament/``, ``process/`` subfolders. Anycubic Slicer Next
  is an OrcaSlicer fork; the JSON schema matches.

Not parsed yet (Phase 4): ``cura-profile`` (.curaprofile, ZIP+INI) and
``prusa-ini``.
"""

from __future__ import annotations

import json
import logging
import zipfile
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Keys that don't describe printable settings; we drop them to keep the
# settings table focused on what actually matters for reproducing a print.
_NOISE_KEYS = frozenset(
    {
        "name",
        "from",
        "inherits",
        "version",
        "is_custom_defined",
        "print_settings_id",
        "filament_settings_id",
        "printer_settings_id",
        "type",
        "instantiation",
        "setting_id",
        "user_id",
    }
)


def parse_settings(raw_format: str | None, file_path: Path) -> dict[str, Any]:
    """Dispatch to the right parser based on the slicer's declared format.

    Failures are swallowed and logged — we never break the upload path because
    of a parse error.
    """
    if not file_path.exists():
        return {}
    try:
        if raw_format == "orca-json":
            return _parse_orca_json(file_path)
        if raw_format == "anycubic-bundle":
            return _parse_anycubic_bundle(file_path)
    except Exception:  # pragma: no cover — defensive
        log.exception("Failed to parse %s as %s", file_path.name, raw_format)
    return {}


# ---------- Orca JSON ----------


def _parse_orca_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_bytes())
    if not isinstance(data, dict):
        return {}
    return _clean(data)


# ---------- Anycubic bundle (ZIP of Orca-style JSONs) ----------


def _parse_anycubic_bundle(path: Path) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    with zipfile.ZipFile(path) as zf:
        # If a bundle manifest exists we use it to drive the order; otherwise
        # we just read every JSON we find.
        names = zf.namelist()
        ordered: list[str] = []
        if "bundle_structure.json" in names:
            try:
                manifest = json.loads(zf.read("bundle_structure.json"))
            except Exception:  # pragma: no cover
                manifest = {}
            for key in ("printer_config", "filament_config", "process_config"):
                ordered.extend(
                    name
                    for name in manifest.get(key, [])
                    if isinstance(name, str) and name in names
                )

        if not ordered:
            ordered = [n for n in names if n.endswith(".json") and n != "bundle_structure.json"]

        for name in ordered:
            try:
                section = _section_from_path(name)
                obj = json.loads(zf.read(name))
            except Exception:  # pragma: no cover
                continue
            if not isinstance(obj, dict):
                continue
            for key, value in _clean(obj).items():
                # Prefix the key with the section so we don't collide between
                # printer/filament/process settings of the same name.
                merged[f"{section}.{key}" if section else key] = value
    return merged


def _section_from_path(zip_path: str) -> str:
    head = zip_path.split("/", 1)[0]
    if head in {"printer", "filament", "process"}:
        return head
    return ""


# ---------- shared cleanup ----------


def _clean(obj: dict[str, Any]) -> dict[str, Any]:
    """Drop noisy/identifier keys, stringify scalars, keep lists/dicts as-is."""
    cleaned: dict[str, Any] = {}
    for key, value in obj.items():
        if key in _NOISE_KEYS:
            continue
        if value is None or value == "":
            continue
        cleaned[key] = value
    return cleaned


# ---------- user-supplied key=value text ----------


def parse_user_settings(text: str | None) -> dict[str, str]:
    """Convert a textarea into a dict.

    Lines look like ``key = value`` or ``key: value``. Blank lines and lines
    starting with ``#`` are ignored.
    """
    if not text:
        return {}
    out: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        for sep in ("=", ":"):
            if sep in line:
                key, _, value = line.partition(sep)
                key = key.strip()
                # Trim trailing inline comments ("  # foo") off the value but
                # leave hex codes like "#1a1a1a" alone (they have no leading
                # whitespace separator).
                comment = value.find(" #")
                if comment != -1:
                    value = value[:comment]
                value = value.strip()
                if key:
                    out[key] = value
                break
    return out
