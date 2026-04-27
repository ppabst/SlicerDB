# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for the slicer-file parsers."""

import json
import zipfile
from pathlib import Path

from app.services.slicer_parsers import (
    detect_format,
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


def test_parse_orca_json_drops_noise_keys_but_keeps_inheritance(tmp_path: Path) -> None:
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
    # Pure noise keys are dropped.
    assert "name" not in settings
    assert "from" not in settings
    assert "version" not in settings
    # Raw `inherits` key is gone, but the parent name is preserved as metadata
    # so the UI can warn the user about the delta-profile situation.
    assert "inherits" not in settings
    assert settings["__inherits__"] == "base"
    # Real settings come through unchanged.
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
    # Pure noise (name, version) was filtered out.
    assert not any(key.endswith(".name") for key in settings)
    assert not any(key.endswith(".version") for key in settings)
    # Inheritance is preserved per section.
    assert settings["process.__inherits__"] == "base"


def test_detect_format_sniffs_zip_and_json(tmp_path: Path) -> None:
    zip_path = tmp_path / "x.anycubic_printer"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("a.json", "{}")
    assert detect_format(zip_path) == "anycubic-bundle"

    json_path = tmp_path / "x.json"
    json_path.write_text('  {"layer_height": "0.2"}')
    assert detect_format(json_path) == "orca-json"

    unknown = tmp_path / "x.bin"
    unknown.write_bytes(b"\x00\x01\x02\x03")
    assert detect_format(unknown) is None


def test_parse_settings_overrides_wrong_format_via_sniffing(tmp_path: Path) -> None:
    """A ZIP bundle uploaded under a slicer that claims orca-json should still parse."""
    bundle_path = tmp_path / "wrong-claim.anycubic_printer"
    with zipfile.ZipFile(bundle_path, "w") as zf:
        zf.writestr(
            "bundle_structure.json",
            json.dumps({"process_config": ["process/p.json"]}),
        )
        zf.writestr(
            "process/p.json",
            json.dumps({"name": "p", "layer_height": "0.16"}),
        )
    # Caller incorrectly says orca-json — parser sniffs the bytes and uses anycubic-bundle.
    settings = parse_settings("orca-json", bundle_path)
    assert settings["process.layer_height"] == "0.16"


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
