"""End-to-end tests for PrintProfile + ProfileVersion lifecycle."""

import io
import json
import re
import zipfile

from fastapi.testclient import TestClient


def _seed(client: TestClient) -> dict[str, int]:
    """Create one of each prerequisite and return their ids."""

    def _id_from(html: str, pattern: str) -> int:
        m = re.search(pattern, html)
        assert m, f"could not match {pattern} in response"
        return int(m.group(1))

    p_html = client.post(
        "/printers",
        data={"name": "P1", "manufacturer": "Acme", "model": "M1"},
    ).text
    printer_id = _id_from(p_html, r'hx-delete="/printers/(\d+)"')

    n_html = client.post(
        "/nozzles",
        data={"printer_id": printer_id, "diameter_mm": 0.4, "material": "brass"},
    ).text
    nozzle_id = _id_from(n_html, r'hx-delete="/nozzles/(\d+)"')

    f_html = client.post(
        "/filaments",
        data={"name": "F1", "manufacturer": "FAB", "material": "PLA"},
    ).text
    filament_id = _id_from(f_html, r'hx-delete="/filaments/(\d+)"')

    s_html = client.post(
        "/slicers", data={"name": "OrcaSlicer", "profile_format": "orca-json"}
    ).text
    slicer_id = _id_from(s_html, r'hx-delete="/slicers/(\d+)"')

    return {
        "printer": printer_id,
        "nozzle": nozzle_id,
        "filament": filament_id,
        "slicer": slicer_id,
    }


def test_profile_version_full_lifecycle(
    client: TestClient, sample_orca_profile: bytes
) -> None:
    seed = _seed(client)

    # Create profile.
    response = client.post(
        "/profiles",
        data={
            "name": "0.20 Standard PLA",
            "printer_id": seed["printer"],
            "nozzle_id": seed["nozzle"],
            "filament_id": seed["filament"],
            "slicer_id": seed["slicer"],
            "layer_height_mm": 0.2,
            "quality_label": "Standard",
        },
    )
    assert response.status_code == 200, response.text
    assert "0.20 Standard PLA" in response.text
    profile_id = int(re.search(r'/profiles/(\d+)"', response.text).group(1))

    # Detail page renders.
    response = client.get(f"/profiles/{profile_id}")
    assert response.status_code == 200
    assert "Noch keine Version" in response.text

    # Upload v1 — should auto-activate.
    response = client.post(
        f"/profiles/{profile_id}/versions",
        files={"file": ("0.2_standard.json", io.BytesIO(sample_orca_profile), "application/json")},
        data={"change_note": "Erste Variante", "rating": "untested"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/profiles/{profile_id}"

    # Detail shows v1, badge "aktiv".
    response = client.get(f"/profiles/{profile_id}")
    assert "v1" in response.text
    assert "aktiv" in response.text
    assert "Erste Variante" in response.text

    # Upload v2 — should NOT auto-activate (v1 stays active).
    response = client.post(
        f"/profiles/{profile_id}/versions",
        files={"file": ("0.2_v2.json", io.BytesIO(b"{}"), "application/json")},
        data={"change_note": "Retraction angepasst"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    response = client.get(f"/profiles/{profile_id}")
    assert "v2" in response.text
    # Active still v1: there should be exactly one "aktiv" badge.
    assert response.text.count(">aktiv<") == 1

    # Find v2 id and activate it.
    v2_match = re.findall(
        r"/profiles/\d+/versions/(\d+)/download", response.text
    )
    assert len(v2_match) == 2
    v2_id = max(int(x) for x in v2_match)

    response = client.post(
        f"/profiles/{profile_id}/versions/{v2_id}/activate", follow_redirects=False
    )
    assert response.status_code == 303

    # Download v2 file.
    response = client.get(f"/profiles/{profile_id}/versions/{v2_id}/download")
    assert response.status_code == 200
    assert response.content == b"{}"

    # Rate v2.
    response = client.post(
        f"/profiles/{profile_id}/versions/{v2_id}/rate",
        data={"rating": "good", "rating_note": "Top Druck"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    response = client.get(f"/profiles/{profile_id}")
    assert "Top Druck" in response.text


def test_upload_auto_parses_orca_json(client: TestClient) -> None:
    seed = _seed(client)
    response = client.post(
        "/profiles",
        data={
            "name": "0.16 Fine PLA",
            "printer_id": seed["printer"],
            "nozzle_id": seed["nozzle"],
            "filament_id": seed["filament"],
            "slicer_id": seed["slicer"],
            "layer_height_mm": 0.16,
        },
    )
    profile_id = int(re.search(r'/profiles/(\d+)"', response.text).group(1))

    payload = json.dumps(
        {
            "name": "0.16 Fine - v1",
            "inherits": "base",
            "layer_height": "0.16",
            "outer_wall_speed": "80",
        }
    ).encode()

    client.post(
        f"/profiles/{profile_id}/versions",
        files={"file": ("fine.json", io.BytesIO(payload), "application/json")},
        data={"settings_text": "outer_wall_speed = 70  # user override"},
        follow_redirects=False,
    )

    response = client.get(f"/profiles/{profile_id}")
    # File-extracted setting visible.
    assert "layer_height" in response.text
    assert ">0.16<" in response.text
    # User override won over the parsed value.
    assert ">70<" in response.text
    # Noise key was dropped.
    assert "inherits" not in response.text


def test_upload_auto_parses_anycubic_bundle(client: TestClient) -> None:
    seed_ids = _seed(client)
    # Override the slicer's format to anycubic-bundle.
    client.post(
        "/slicers", data={"name": "Anycubic Slicer Next", "profile_format": "anycubic-bundle"}
    )
    response = client.get("/slicers")
    anycubic_id = max(int(x) for x in re.findall(r'/slicers/(\d+)"', response.text))

    response = client.post(
        "/profiles",
        data={
            "name": "Bundle Test",
            "printer_id": seed_ids["printer"],
            "nozzle_id": seed_ids["nozzle"],
            "filament_id": seed_ids["filament"],
            "slicer_id": anycubic_id,
            "layer_height_mm": 0.2,
        },
    )
    profile_id = int(re.search(r'/profiles/(\d+)"', response.text).group(1))

    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "bundle_structure.json",
            json.dumps(
                {
                    "process_config": ["process/p.json"],
                    "printer_config": [],
                    "filament_config": [],
                }
            ),
        )
        zf.writestr(
            "process/p.json",
            json.dumps({"name": "p", "layer_height": "0.2", "outer_wall_speed": "80"}),
        )
    bundle.seek(0)

    client.post(
        f"/profiles/{profile_id}/versions",
        files={"file": ("k.anycubic_printer", bundle, "application/zip")},
        data={},
        follow_redirects=False,
    )

    response = client.get(f"/profiles/{profile_id}")
    assert "process.layer_height" in response.text
    assert "process.outer_wall_speed" in response.text


def test_settings_update_replaces_dict(client: TestClient) -> None:
    seed = _seed(client)
    response = client.post(
        "/profiles",
        data={
            "name": "Edit Test",
            "printer_id": seed["printer"],
            "nozzle_id": seed["nozzle"],
            "filament_id": seed["filament"],
            "slicer_id": seed["slicer"],
            "layer_height_mm": 0.2,
        },
    )
    profile_id = int(re.search(r'/profiles/(\d+)"', response.text).group(1))

    client.post(
        f"/profiles/{profile_id}/versions",
        files={"file": ("x.bin", io.BytesIO(b"raw"), "application/octet-stream")},
        data={"settings_text": "a = 1\nb = 2"},
        follow_redirects=False,
    )

    response = client.get(f"/profiles/{profile_id}")
    version_id = int(
        re.search(r"/profiles/\d+/versions/(\d+)/download", response.text).group(1)
    )

    # Update with a different key set.
    response = client.post(
        f"/profiles/{profile_id}/versions/{version_id}/settings",
        data={"settings_text": "c = 3\nd = 4"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    response = client.get(f"/profiles/{profile_id}")
    assert ">3<" in response.text and ">4<" in response.text
    # Old keys are gone — settings were replaced, not merged.
    assert "<td class=\"px-3 py-1.5 text-slate-700\">a</td>" not in response.text


def test_profile_create_validates_fk(client: TestClient) -> None:
    response = client.post(
        "/profiles",
        data={
            "name": "x",
            "printer_id": 999,
            "nozzle_id": 999,
            "filament_id": 999,
            "slicer_id": 999,
            "layer_height_mm": 0.2,
        },
    )
    assert response.status_code == 400
