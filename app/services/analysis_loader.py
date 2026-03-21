from __future__ import annotations

from typing import Any


def load_latest_analysis_snapshot() -> dict[str, Any]:
    """Placeholder for the future serving-database-backed analysis snapshot loader.

    The first standalone backend version serves payloads from cached JSON files and
    sample payloads. This function reserves the service boundary for the later
    capture -> serving transformation pipeline inside the new repository.
    """

    raise NotImplementedError("Serving database analysis snapshot loading is not wired yet.")
