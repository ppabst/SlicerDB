# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for the slicer-file parsers."""

import json
import zipfile
from pathlib import Path

from app.services.slicer_parsers import (
    parse_settings,
    parse_user_settings,
)


def test_parse_user_settings_handles_separators_and_comments() -> None:
    text = """
        # comment is dropped
        layer_height = 0.16
        outer_wall_speed: 80

        sparse_infill_density=15%
    """
    out = parse_user_settings(text)
    assert out == {
        "layer_height": "0.16",
        "outer_wall_speed": "80",
        "sparse_infill_density": "15%",
    }


def test_parse_user_settings_empty_inputs() -> None:
    assert parse_user_settings(None) == {}
    assert parse_user_settings("") == {}
    assert parse_user_settings("\n  \n# only comment\n") == {}


def test_parse_orca_json_drops_noise_keys(tmp_path: Path) -> None:
    payload = {
        "name": "0.20mm Standard",
        "from": "User",
        "inherits": "base",
        "version": "1.2.3",
        "layer_height": "0.2",
        "outer_wall_speed": "120",
        "support_threshold_angle": "50",
    }
    path = tmp_path / "process.json"
    path.write_text(json.dumps(payload))
    settings = parse_settings("orca-json", path)
    assert "name" not in settings
    assert "from" not in settings
    assert "inherits" not in settings
    assert "version" not in settings
    assert settings["layer_height"] == "0.2"
    assert settings["outer_wall_speed"] == "120"
    assert settings["support_threshold_angle"] == "50"


def test_parse_anycubic_bundle_merges_sections(tmp_path: Path) -> None:
    bundle_path = tmp_path / "demo.anycubic_printer"
    process_payload = {
        "name": "0.20mm Standard - v1",
        "inherits": "base",
        "support_threshold_angle": "50",
        "layer_height": "0.2",
    }
    printer_payload = {
        "name": "Anycubic Kobra 2",
        "nozzle_diameter": "0.4",
        "version": "1",
    }
    manifest = {
        "bundle_id": "test",
        "bundle_type": "printer config bundle",
        "filament_config": [],
        "printer_config": ["printer/kobra.json"],
        "process_config": ["process/standard.json"],
    }
    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bundle_structure.json", json.dumps(manifest))
        zf.writestr("printer/kobra.json", json.dumps(printer_payload))
        zf.writestr("process/standard.json", json.dumps(process_payload))

    settings = parse_settings("anycubic-bundle", bundle_path)
    # Section-prefixed keys avoid collisions between printer + process.
    assert settings["printer.nozzle_diameter"] == "0.4"
    assert settings["process.layer_height"] == "0.2"
    assert settings["process.support_threshold_angle"] == "50"
    # Noise (name, version, inherits) was filtered out.
    assert not any(key.endswith(".name") for key in settings)
    assert not any(key.endswith(".version") for key in settings)
    assert not any(key.endswith(".inherits") for key in settings)


def test_parse_settings_returns_empty_for_unknown_format(tmp_path: Path) -> None:
    path = tmp_path / "x.bin"
    path.write_bytes(b"\x00\x01\x02")
    assert parse_settings("cura-profile", path) == {}
    assert parse_settings(None, path) == {}


def test_parse_settings_swallows_corrupt_files(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not valid json")
    assert parse_settings("orca-json", path) == {}

    bundle = tmp_path / "broken.anycubic_printer"
    bundle.write_bytes(b"not a zip")
    assert parse_settings("anycubic-bundle", bundle) == {}
