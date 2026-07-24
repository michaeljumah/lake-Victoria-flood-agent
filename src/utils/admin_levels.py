"""
admin_levels.py
===============

Administrative-level awareness for the Lake Victoria Flood Risk agent.

Why this module exists
----------------------
The agent previously answered questions like *"which SUB-COUNTIES face the
highest flood risk?"* with a list of COUNTIES (Kisumu, Busia, Migori...). That
is factually wrong: those are counties, not sub-counties. The cause was simple —
the project only had county boundaries, so counties were the only thing it could
see, and nothing told the user that.

This module fixes that by:

1. Loading real sub-county boundaries (GADM level 2, `NAME_2`) so sub-county
   questions can be answered at the correct resolution.
2. Detecting which administrative level a question is asking about.
3. Reporting the resolution actually available, so the agent can say
   "I only have county-level data for X" instead of silently substituting.

Administrative hierarchy in Kenya (coarse -> fine):

    Country  >  County (47)  >  Sub-county / Constituency (~300)  >  Ward  >  Village

This project has data at **county** and **sub-county** level. It does NOT have
ward or village boundaries — questions at those levels must be answered
honestly at the finest level available (sub-county) with that stated.

Public API
----------
- detect_admin_level(question)      -> "county" | "subcounty" | "ward" | "village" | "settlement"
- available_resolution(level)       -> dict describing what data exists
- subcounties_for_county(name)      -> list[str]
- basin_subcounties()               -> list[str]  (all sub-counties in the 5 basin counties)
- get_subcounty_geometry(name)      -> shapely geometry | None
- prettify(name)                    -> "KisumuEast" -> "Kisumu East"
- resolution_note(level)            -> a sentence the agent can put in its answer
"""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

try:
    import geopandas as gpd  # type: ignore

    _GPD_AVAILABLE = True
except ImportError:  # pragma: no cover
    gpd = None  # type: ignore
    _GPD_AVAILABLE = False


# ---------------------------------------------------------------------------
# Administrative levels this project understands
# ---------------------------------------------------------------------------
LEVEL_COUNTY = "county"
LEVEL_SUBCOUNTY = "subcounty"
LEVEL_WARD = "ward"
LEVEL_VILLAGE = "village"
LEVEL_SETTLEMENT = "settlement"
LEVEL_FEATURE = "feature"  # wetlands, floodplains, basins, beaches

# What data the project actually holds, per level.
DATA_AVAILABILITY: dict[str, dict[str, Any]] = {
    LEVEL_COUNTY: {
        "available": True,
        "source": "GADM level 1 (NAME_1) — 47 Kenyan counties",
        "count": 47,
    },
    LEVEL_SUBCOUNTY: {
        "available": True,
        "source": "GADM level 2 (NAME_2) — ~300 sub-counties / constituencies",
        "count": 300,
    },
    LEVEL_WARD: {
        "available": False,
        "source": None,
        "fallback": LEVEL_SUBCOUNTY,
    },
    LEVEL_VILLAGE: {
        "available": False,
        "source": None,
        "fallback": LEVEL_SUBCOUNTY,
    },
    LEVEL_SETTLEMENT: {
        "available": True,
        "source": "settlements.geojson — major towns only (not exhaustive)",
        "partial": True,
    },
    LEVEL_FEATURE: {
        "available": True,
        "source": "named flood features (Kano plains, Nyando basin, Budalangi, "
                  "Yala swamp) mapped to their sub-counties",
        "partial": True,
    },
}

# Keyword triggers for detecting the level a question is asking about.
_LEVEL_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (LEVEL_WARD, ("ward", "wards")),
    (LEVEL_VILLAGE, ("village", "villages", "hamlet")),
    (LEVEL_SUBCOUNTY, (
        "sub-county", "sub county", "subcounty", "sub-counties", "sub counties",
        "subcounties", "constituency", "constituencies", "division", "divisions",
    )),
    (LEVEL_SETTLEMENT, (
        "town", "towns", "trading centre", "trading center", "settlement",
        "settlements", "beach", "beaches", "market",
    )),
    (LEVEL_FEATURE, (
        "wetland", "wetlands", "floodplain", "floodplains", "swamp", "basin",
        "plains", "shoreline", "delta",
    )),
    (LEVEL_COUNTY, ("county", "counties")),
]


def detect_admin_level(question: str) -> str:
    """
    Detect which administrative level a question is asking about.

    Returns the FINEST level mentioned, because a question like "which
    sub-counties in Kisumu county" is asking for sub-counties. Defaults to
    county when nothing more specific is mentioned.
    """
    if not isinstance(question, str) or not question.strip():
        return LEVEL_COUNTY
    q = question.lower()
    for level, keywords in _LEVEL_KEYWORDS:
        if any(k in q for k in keywords):
            return level
    return LEVEL_COUNTY


def available_resolution(level: str) -> dict[str, Any]:
    """Return what data exists for a requested level, including any fallback."""
    info = dict(DATA_AVAILABILITY.get(level, DATA_AVAILABILITY[LEVEL_COUNTY]))
    info["requested_level"] = level
    if not info.get("available"):
        info["effective_level"] = info.get("fallback", LEVEL_COUNTY)
    else:
        info["effective_level"] = level
    return info


def resolution_note(level: str) -> str:
    """
    A sentence the agent can include so it never silently substitutes a
    coarser level for the one the user asked about.
    """
    info = available_resolution(level)
    if info.get("available") and not info.get("partial"):
        return (
            f"Spatial resolution: {level}-level data is available "
            f"({info['source']})."
        )
    if info.get("partial"):
        return (
            f"Spatial resolution: only partial {level}-level data is available "
            f"({info['source']}). Results are reported at "
            f"{info['effective_level']} level where coverage is missing."
        )
    return (
        f"Spatial resolution: this project does NOT have {level}-level "
        f"boundaries. The finest available resolution is "
        f"{info['effective_level']}, so results are reported at that level. "
        f"Do not treat them as {level}-level findings."
    )


# ---------------------------------------------------------------------------
# Sub-county boundary loading
# ---------------------------------------------------------------------------
def _subcounties_path() -> str:
    """Absolute path to data/kenya_subcounties.geojson."""
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", ".."))
    return os.path.join(root, "data", "kenya_subcounties.geojson")


def prettify(name: str) -> str:
    """
    Turn GADM's concatenated names into readable ones.

    GADM level 2 stores "KisumuEast", "TesoNorth", "AlegoUsonga". This inserts
    spaces at case boundaries so the agent and the map show "Kisumu East",
    "Teso North", "Alego Usonga".
    """
    if not isinstance(name, str) or not name:
        return ""
    # Insert a space between a lowercase/digit and a following uppercase letter.
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name.strip())
    return spaced


@lru_cache(maxsize=1)
def _load_subcounties_gdf() -> Any | None:
    """Load and cache the sub-county GeoDataFrame (GADM level 2)."""
    if not _GPD_AVAILABLE:
        logger.warning("geopandas unavailable; sub-county data cannot load.")
        return None
    path = _subcounties_path()
    if not os.path.exists(path):
        logger.warning(
            "Sub-county boundaries not found at %s. Download GADM level 2 for "
            "Kenya and save it there to enable sub-county answers.", path
        )
        return None
    try:
        gdf = gpd.read_file(path)
        if "NAME_2" not in gdf.columns or "NAME_1" not in gdf.columns:
            logger.warning("Sub-county file missing NAME_1/NAME_2 fields.")
            return None
        gdf = gdf.rename(columns={"NAME_1": "county", "NAME_2": "subcounty"})
        gdf["county"] = gdf["county"].astype(str).str.strip()
        gdf["subcounty"] = gdf["subcounty"].astype(str).str.strip()
        # Drop GADM placeholder rows ("unknown6", numeric codes).
        bad = gdf["subcounty"].str.lower().str.startswith("unknown") | gdf[
            "subcounty"
        ].str.isdigit()
        if bad.any():
            logger.info("Dropping %d placeholder sub-county rows.", int(bad.sum()))
            gdf = gdf[~bad]
        gdf["subcounty_display"] = gdf["subcounty"].map(prettify)
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        else:
            gdf = gdf.to_crs("EPSG:4326")
        return gdf
    except Exception as exc:
        logger.warning("Failed to load sub-county boundaries: %s", exc)
        return None


def _norm(name: str) -> str:
    """Normalize a name for tolerant matching (spaces/case/punctuation)."""
    if not isinstance(name, str):
        return ""
    return name.lower().replace(" ", "").replace("-", "").replace("'", "").strip()


def has_subcounty_data() -> bool:
    """True if sub-county boundaries are loaded and usable."""
    gdf = _load_subcounties_gdf()
    return gdf is not None and not gdf.empty


def subcounties_for_county(county: str) -> list[str]:
    """
    Return the display names of all sub-counties within a county.

    Matching is tolerant of spelling variants ("Homa Bay" vs "HomaBay").
    """
    gdf = _load_subcounties_gdf()
    if gdf is None:
        return []
    target = _norm(county)
    match = gdf[gdf["county"].map(_norm) == target]
    return sorted(match["subcounty_display"].tolist())


def basin_subcounties() -> list[str]:
    """All sub-counties across the five Lake Victoria basin counties."""
    from . import lake_victoria

    out: list[str] = []
    for county in lake_victoria.BASIN_COUNTIES:
        out.extend(subcounties_for_county(county))
    return out


def county_for_subcounty(subcounty: str) -> str | None:
    """Return the parent county of a sub-county, or None if unknown."""
    gdf = _load_subcounties_gdf()
    if gdf is None:
        return None
    target = _norm(subcounty)
    match = gdf[
        (gdf["subcounty"].map(_norm) == target)
        | (gdf["subcounty_display"].map(_norm) == target)
    ]
    if match.empty:
        return None
    return str(match["county"].iloc[0])


def get_subcounty_geometry(subcounty: str) -> Any | None:
    """Return the shapely geometry for a sub-county, or None."""
    gdf = _load_subcounties_gdf()
    if gdf is None:
        return None
    target = _norm(subcounty)
    match = gdf[
        (gdf["subcounty"].map(_norm) == target)
        | (gdf["subcounty_display"].map(_norm) == target)
    ]
    if match.empty:
        return None
    return match.geometry.iloc[0]


def resolve_subcounties(names: list[str] | None) -> list[str]:
    """
    Resolve a list of sub-county names to canonical display names.

    None or empty means all sub-counties in the Lake Victoria basin.
    """
    if not names:
        return basin_subcounties()
    gdf = _load_subcounties_gdf()
    if gdf is None:
        return []
    lookup = {
        _norm(row.subcounty): row.subcounty_display for row in gdf.itertuples()
    }
    lookup.update(
        {_norm(row.subcounty_display): row.subcounty_display for row in gdf.itertuples()}
    )
    out: list[str] = []
    for raw in names:
        key = _norm(raw)
        if key in lookup:
            out.append(lookup[key])
        else:
            logger.warning("Unknown sub-county %r ignored.", raw)
    return out


# ---------------------------------------------------------------------------
# Named flood features -> sub-counties
# ---------------------------------------------------------------------------
# Lets the agent answer "which areas of the Kano plains flood?" by mapping a
# named physical feature to the administrative units that contain it.
FLOOD_FEATURES: dict[str, dict[str, Any]] = {
    "Kano Plains": {
        "county": "Kisumu",
        "subcounties": ["Nyando", "Nyakach", "Muhoroni"],
        "description": "Flat, poorly drained floodplain east of Kisumu, drained "
                       "by the Nyando River; floods in both rain seasons.",
    },
    "Nyando Basin": {
        "county": "Kisumu",
        "subcounties": ["Nyando", "Nyakach"],
        "description": "Lower Nyando River basin — one of Kenya's most "
                       "consistently flood-affected sub-basins.",
    },
    "Budalangi": {
        "county": "Busia",
        "subcounties": ["Budalangi"],
        "description": "Nzoia River outlet into Lake Victoria; repeated dyke "
                       "breaches and lake backflow flooding.",
    },
    "Yala Swamp": {
        "county": "Siaya",
        "subcounties": ["Bondo", "Alego Usonga"],
        "description": "Wetland complex at the Yala River mouth; seasonal "
                       "inundation and lake-level sensitivity.",
    },
    "Winam Gulf Shoreline": {
        "county": "Kisumu",
        "subcounties": ["Kisumu East", "Kisumu West", "Seme", "Nyando"],
        "description": "Northeastern arm of Lake Victoria; shoreline "
                       "inundation when lake levels rise.",
    },
}


def features_for_subcounty(subcounty: str) -> list[str]:
    """Return named flood features associated with a sub-county."""
    target = _norm(subcounty)
    return [
        name
        for name, info in FLOOD_FEATURES.items()
        if any(_norm(s) == target for s in info["subcounties"])
    ]


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    print("has sub-county data:", has_subcounty_data())
    for q in [
        "Which sub-counties around Lake Victoria face the highest flood risk?",
        "Which villages lie in flood-prone wetlands?",
        "Which counties are most exposed?",
        "Which hospitals are at risk?",
    ]:
        lvl = detect_admin_level(q)
        print(f"\nQ: {q}\n   level={lvl}\n   {resolution_note(lvl)}")
    print("\nKisumu sub-counties:", subcounties_for_county("Kisumu"))
    print("Busia sub-counties:", subcounties_for_county("Busia"))
