"""
lake_victoria.py
================

Lake Victoria basin definition — the CENTRE of this study.

Why this module exists
----------------------
The original project treated all 47 Kenyan counties equally. This workshop
version makes the Lake Victoria basin the primary study area, with the
surrounding Nyanza/Western counties providing administrative boundaries.

It also solves a real scientific problem specific to this region:

    Lake Victoria is PERMANENT open water. The Sentinel-1 flood signal works by
    detecting low radar backscatter, which is exactly what open water looks
    like. Without masking, every lakeside county would score maximum "flood"
    simply because the lake is in it — not because anything flooded.

So this module provides a permanent-water mask (JRC Global Surface Water) so
the flood signal measures NEW/seasonal water — actual flooding — rather than
the lake itself. This is the single most important correction for a Lake
Victoria study area.

Public API
----------
- BASIN_COUNTIES              : the five lakeside counties (study scope)
- LAKE_VICTORIA_BBOX          : bounding box of the Kenyan portion of the lake
- lake_victoria_geometry()    : ee.Geometry of the study area
- permanent_water_mask()      : ee.Image mask excluding permanent water
- is_basin_county(name)       : membership test
- basin_scope()               : the default county list for this project
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    import ee  # type: ignore

    _EE_AVAILABLE = True
except ImportError:  # pragma: no cover
    ee = None  # type: ignore
    _EE_AVAILABLE = False


# ---------------------------------------------------------------------------
# Study area definition
# ---------------------------------------------------------------------------
# The five Kenyan counties bordering / draining into Lake Victoria. These are
# the administrative units the agent ranks. The lake is the physical centre;
# these counties are how results are reported to decision-makers.
BASIN_COUNTIES: list[str] = [
    "Kisumu",
    "Homa Bay",
    "Siaya",
    "Busia",
    "Migori",
]

# Bounding box of the Kenyan portion of Lake Victoria and its shoreline
# (minLon, minLat, maxLon, maxLat). Covers the Winam Gulf, the Kano plains,
# the Nyando/Nzoia outlets and the Budalangi area.
LAKE_VICTORIA_BBOX: tuple[float, float, float, float] = (33.90, -1.20, 35.10, 0.60)

# JRC Global Surface Water — used to identify PERMANENT water (the lake) so it
# can be excluded from the flood signal.
JRC_SURFACE_WATER = "JRC/GSW1_4/GlobalSurfaceWater"

# Pixels with >= this occurrence percentage are treated as permanent water.
PERMANENT_WATER_THRESHOLD = 80


def basin_scope() -> list[str]:
    """Return the default county scope for this project (the basin counties)."""
    return list(BASIN_COUNTIES)


def is_basin_county(name: str) -> bool:
    """True if a county name is part of the Lake Victoria basin study area."""
    if not isinstance(name, str):
        return False
    return name.strip().lower() in {c.lower() for c in BASIN_COUNTIES}


def lake_victoria_geometry() -> Any:
    """
    Return an ee.Geometry covering the Kenyan Lake Victoria study area.

    Raises RuntimeError if Earth Engine is unavailable.
    """
    if not _EE_AVAILABLE:
        raise RuntimeError("Earth Engine is not available.")
    min_lon, min_lat, max_lon, max_lat = LAKE_VICTORIA_BBOX
    return ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])


def permanent_water_mask() -> Any:
    """
    Build a mask that EXCLUDES permanent water bodies (i.e. Lake Victoria).

    Returns an ee.Image mask where 1 = land / seasonal water (keep) and
    0 = permanent water (exclude). Apply with ``image.updateMask(mask)``.

    This is what stops the lake itself from being counted as a flood.
    Returns None if Earth Engine is unavailable or the dataset cannot be read,
    in which case callers should proceed unmasked and note the limitation.
    """
    if not _EE_AVAILABLE:
        return None
    try:
        gsw = ee.Image(JRC_SURFACE_WATER).select("occurrence")
        # occurrence >= threshold  =>  permanent water  =>  mask OUT.
        permanent = gsw.gte(PERMANENT_WATER_THRESHOLD)
        # unmask(0) so areas with no GSW data are treated as land, not dropped.
        return permanent.unmask(0).Not()
    except Exception as exc:
        logger.warning("Could not build permanent-water mask (%s).", exc)
        return None


def describe_study_area() -> str:
    """One-line human description used in prompts and the UI."""
    return (
        "the Kenyan Lake Victoria basin — Kisumu, Homa Bay, Siaya, Busia and "
        "Migori counties, including the Winam Gulf, the Kano plains, and the "
        "Nyando and Nzoia river outlets"
    )


# ---------------------------------------------------------------------------
# Basin membership / scope guardrail
# ---------------------------------------------------------------------------
# WHY THIS EXISTS
# ---------------
# The agent was asked to compare Nakuru with Siaya and ranked NAKURU as higher
# flood risk. That is wrong in a way the scoring model could not see: Nakuru is
# in the Rift Valley, ~173 km away, and drains to Lake Nakuru — a completely
# different basin. It scored high only because it has ~2 million people, and
# the model treats population as exposure without asking whether a Lake
# Victoria flood could ever reach those people.
#
# Two failure modes this guards against:
#   1. Out-of-basin counties being ranked as if they were lakeside.
#   2. Radar flood signal picking up OTHER permanent water bodies (Lake Nakuru,
#      Lake Naivasha, Lake Baringo) and reporting them as flooding.
#
# Distances are computed from the Winam Gulf centre, the hydrological heart of
# the Kenyan Lake Victoria basin.

# Approximate distance (km) beyond which a county cannot plausibly be affected
# by Lake Victoria flooding. Basin counties sit at ~35-82 km.
BASIN_DISTANCE_LIMIT_KM: float = 120.0

# Counties in the wider Lake Victoria catchment: not lakeside, but their rivers
# (Nzoia, Yala, Nyando, Sondu-Miriu) drain INTO the lake, so they have a real
# hydrological connection worth acknowledging.
CATCHMENT_COUNTIES: list[str] = [
    "Kakamega", "Vihiga", "Bungoma", "Kisii", "Nyamira", "Kericho", "Bomet",
    "Nandi", "Trans Nzoia", "Narok",
]


def distance_to_lake_km(county: str) -> float | None:
    """
    Great-circle-ish distance (km) from a county centroid to the Winam Gulf.

    Returns None if the county centroid is unknown.
    """
    import math

    from . import geo

    centre = geo.county_centroid(county)
    if centre is None:
        return None
    lon, lat = centre
    gulf_lon, gulf_lat = LAKE_VICTORIA_CENTER_LON, LAKE_VICTORIA_CENTER_LAT
    dx = (lon - gulf_lon) * 111.0 * math.cos(math.radians((lat + gulf_lat) / 2))
    dy = (lat - gulf_lat) * 111.0
    return round(math.sqrt(dx * dx + dy * dy), 1)


# Winam Gulf centre (exact, GeoNames ID 178104) used for distance measurement.
LAKE_VICTORIA_CENTER_LAT: float = -0.26721
LAKE_VICTORIA_CENTER_LON: float = 34.5336


def basin_membership(county: str) -> dict[str, Any]:
    """
    Classify a county's relationship to the Lake Victoria basin.

    Returns a dict with:
        membership : "basin" | "catchment" | "outside"
        distance_km: distance from the Winam Gulf
        in_scope   : True only for basin counties
        note       : a sentence the agent should surface to the user

    This is the guardrail that stops the agent silently ranking a Rift Valley
    county as a Lake Victoria flood risk.
    """
    name = (county or "").strip()
    distance = distance_to_lake_km(name)

    def _n(x: str) -> str:
        return x.lower().replace(" ", "").replace("-", "")

    if any(_n(name) == _n(c) for c in BASIN_COUNTIES):
        return {
            "county": name,
            "membership": "basin",
            "in_scope": True,
            "distance_km": distance,
            "note": f"{name} is a Lake Victoria basin county.",
        }

    if any(_n(name) == _n(c) for c in CATCHMENT_COUNTIES):
        return {
            "county": name,
            "membership": "catchment",
            "in_scope": False,
            "distance_km": distance,
            "note": (
                f"{name} is NOT a lakeside county, but it lies in the wider "
                f"Lake Victoria catchment — its rivers drain into the lake. "
                f"Flood risk there is riverine/upstream, not lake-driven, and "
                f"is not directly comparable to lakeside flood risk."
            ),
        }

    far = distance is not None and distance > BASIN_DISTANCE_LIMIT_KM
    return {
        "county": name,
        "membership": "outside",
        "in_scope": False,
        "distance_km": distance,
        "note": (
            f"{name} is OUTSIDE the Lake Victoria basin"
            + (f" (~{distance:.0f} km from the Winam Gulf)" if distance else "")
            + ". It is in a different drainage basin, so it cannot be affected "
            "by Lake Victoria flooding. Any flood risk there has different "
            "causes (local rivers, urban drainage, or other lakes) and this "
            "tool is not calibrated for it. Do not present its score as "
            "comparable to lakeside counties."
            if far
            else (
                f"{name} is not one of the five Lake Victoria basin counties. "
                "Its score is not calibrated for lake-driven flooding."
            )
        ),
    }


def classify_scope(counties: list[str]) -> dict[str, Any]:
    """
    Classify a list of counties and summarise scope warnings for the agent.

    Used by the risk tools so that any out-of-basin county is flagged in the
    output metadata and cannot be silently ranked as a lakeside flood risk.
    """
    results = [basin_membership(c) for c in counties or []]
    out_of_scope = [r for r in results if not r["in_scope"]]
    return {
        "counties": results,
        "all_in_basin": not out_of_scope,
        "out_of_scope": [r["county"] for r in out_of_scope],
        "warnings": [r["note"] for r in out_of_scope],
    }
