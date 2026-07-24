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
