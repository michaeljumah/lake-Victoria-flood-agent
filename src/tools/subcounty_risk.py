"""
subcounty_risk.py
=================

Sub-county (constituency) level flood-risk scoring for the Lake Victoria basin.

Why this tool exists
--------------------
The agent used to answer "which SUB-COUNTIES flood most?" with COUNTY names —
factually wrong. This tool provides the correct resolution: it scores and ranks
sub-counties such as Nyando, Nyakach, Budalangi, Rarieda and Mbita using the
same transparent, auditable formula as the county scorer.

Scoring model — identical weights to `risk_score.py`, so results are comparable
and equally explainable (no machine learning):

    risk = 0.4*flood + 0.3*rainfall + 0.2*population + 0.1*elevation

Population is apportioned from the parent county by area share, because
sub-county population tables are not bundled with the boundary file. That
approximation is reported honestly in the output metadata so the agent can
state it rather than implying census-grade precision.

Output contract (mirrors risk_score for easy fusion/vis reuse):

    {
        "ranking": [
            {
                "subcounty": "Nyando",
                "county": "Kisumu",
                "risk_score": 0.71,
                "components": {...},
                "contributions": {...},
                "exposed_population": 123456,
                "flood_features": ["Kano Plains", "Nyando Basin"]
            }, ...
        ],
        "weights": {...},
        "meta": {"level": "subcounty", "population_method": "...", ...}
    }
"""

from __future__ import annotations

import logging
from typing import Any

from ..utils import admin_levels, geo, lake_victoria
from . import earth_engine, population as population_tool, risk_score

logger = logging.getLogger(__name__)


def _clamp_unit(value: Any) -> float:
    """Coerce to a float in [0, 1]."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, v))


def _area(geometry: Any) -> float:
    """Planar area of a geometry (degrees^2) — used only for ratio shares."""
    try:
        return float(geometry.area)
    except Exception:
        return 0.0


def _apportion_population(
    subcounties: list[str], county_population: dict[str, Any]
) -> dict[str, int]:
    """
    Split each county's population among its sub-counties by area share.

    This is an approximation, not census data. It is flagged in the output so
    the agent can state the limitation instead of implying precision.
    """
    # Group sub-counties by parent county with their areas.
    grouped: dict[str, list[tuple[str, float]]] = {}
    for sc in subcounties:
        parent = admin_levels.county_for_subcounty(sc)
        if not parent:
            continue
        geometry = admin_levels.get_subcounty_geometry(sc)
        grouped.setdefault(parent, []).append((sc, _area(geometry)))

    out: dict[str, int] = {}
    for parent, members in grouped.items():
        # Look up the parent county's population tolerantly.
        pop_entry = None
        for name, entry in county_population.items():
            if geo._normalize_name(name) == geo._normalize_name(parent):
                pop_entry = entry
                break
        total_pop = int((pop_entry or {}).get("exposed_population", 0) or 0)
        total_area = sum(a for _, a in members) or 1.0
        for sc, area in members:
            out[sc] = int(round(total_pop * (area / total_area)))
    return out


def compute_subcounty_risk(
    subcounties: list[str] | None = None,
    counties: list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Rank sub-counties in the Lake Victoria basin by flood risk.

    Parameters
    ----------
    subcounties:
        Specific sub-county names. None/empty means all basin sub-counties
        (optionally narrowed by `counties`).
    counties:
        Restrict to sub-counties within these counties.
    config:
        Configuration dict passed through to the data tools.
    """
    if not admin_levels.has_subcounty_data():
        return {
            "ranking": [],
            "weights": {},
            "meta": {
                "level": "subcounty",
                "available": False,
                "note": (
                    "Sub-county boundaries are not installed. Add GADM level 2 "
                    "for Kenya as data/kenya_subcounties.geojson to enable "
                    "sub-county answers. Results cannot be produced at this "
                    "resolution."
                ),
            },
        }

    # Resolve the target sub-counties.
    if subcounties:
        targets = admin_levels.resolve_subcounties(subcounties)
    elif counties:
        targets = []
        for c in counties:
            targets.extend(admin_levels.subcounties_for_county(c))
    else:
        targets = admin_levels.basin_subcounties()

    if not targets:
        return {
            "ranking": [],
            "weights": {},
            "meta": {"level": "subcounty", "available": True, "note": "No sub-counties matched."},
        }

    weights = risk_score._resolve_weights(config)

    # Parent counties we need county-level layers/population for.
    parents = sorted(
        {
            admin_levels.county_for_subcounty(sc)
            for sc in targets
            if admin_levels.county_for_subcounty(sc)
        }
    )

    layers = earth_engine.get_county_risk_layers(counties=parents, config=config)
    county_pop = population_tool.get_population_exposure(counties=parents, config=config)
    layer_counties = layers.get("counties", {})
    pop_counties = county_pop.get("counties", {})

    sub_pop = _apportion_population(targets, pop_counties)
    max_pop = max(sub_pop.values()) if sub_pop else 1

    ranking: list[dict[str, Any]] = []
    for sc in targets:
        parent = admin_levels.county_for_subcounty(sc) or ""

        # Inherit the parent county's geophysical signals (county-resolution
        # satellite aggregation), matched tolerantly on name.
        layer = {}
        for name, entry in layer_counties.items():
            if geo._normalize_name(name) == geo._normalize_name(parent):
                layer = entry
                break

        flood = _clamp_unit(layer.get("flood"))
        rainfall = _clamp_unit(layer.get("rainfall"))
        elevation = _clamp_unit(layer.get("elevation"))

        exposed = int(sub_pop.get(sc, 0))
        pop_norm = _clamp_unit(exposed / max_pop) if max_pop else 0.0

        features = admin_levels.features_for_subcounty(sc)
        # Named flood features are documented hazard zones; nudge the flood
        # term upward for them, transparently and by a fixed, stated amount.
        feature_bonus = 0.15 if features else 0.0
        flood_adj = min(1.0, flood + feature_bonus)

        contributions = {
            "flood": round(weights["flood"] * flood_adj, 4),
            "rainfall": round(weights["rainfall"] * rainfall, 4),
            "population": round(weights["population"] * pop_norm, 4),
            "elevation": round(weights["elevation"] * elevation, 4),
        }
        score = round(sum(contributions.values()), 4)

        ranking.append(
            {
                "subcounty": sc,
                "county": admin_levels.prettify(parent),
                "risk_score": score,
                "components": {
                    "flood": round(flood_adj, 3),
                    "rainfall": rainfall,
                    "population": round(pop_norm, 3),
                    "elevation": elevation,
                },
                "contributions": contributions,
                "exposed_population": exposed,
                "flood_features": features,
            }
        )

    ranking.sort(key=lambda r: (-r["risk_score"], r["subcounty"]))

    return {
        "ranking": ranking,
        "weights": weights,
        "meta": {
            "level": "subcounty",
            "available": True,
            "count": len(ranking),
            "population_method": (
                "Sub-county population apportioned from county totals by area "
                "share — an approximation, not census data."
            ),
            "signal_method": (
                "Flood/rainfall/elevation are inherited from the parent county's "
                "satellite aggregation; sub-counties containing documented flood "
                "features receive a fixed +0.15 flood adjustment."
            ),
            "sources": {
                "layers": layers.get("meta", {}),
                "population": county_pop.get("meta", {}),
                "boundaries": "GADM level 2 (NAME_2)",
            },
        },
    }


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    out = compute_subcounty_risk()
    for r in out["ranking"][:12]:
        feats = f" [{', '.join(r['flood_features'])}]" if r["flood_features"] else ""
        print(
            f"  {r['subcounty']:18s} ({r['county']:10s}) "
            f"{r['risk_score']:.4f}  pop~{r['exposed_population']:,}{feats}"
        )
