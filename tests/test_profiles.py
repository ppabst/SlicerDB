"""End-to-end tests for PrintProfile + ProfileVersion lifecycle."""

import io
import re

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
