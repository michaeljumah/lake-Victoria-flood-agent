"""
viz.py
======

Visualization helpers for the Kenya Climate Risk agent.

Turns the risk-scoring output (the 'ranking' list from tools.risk_score) into:
- an interactive county risk map (geemap/folium), choropleth-style by score
- a ranked map highlighting the top-N highest-risk counties
- a risk bar chart (matplotlib) of the top-N counties

Public functions
----------------
- build_risk_map(ranking, top_n, config)        -> map object | None
- build_ranked_map(ranking, top_n, config)      -> map object | None
- build_risk_bar_chart(ranking, top_n)          -> matplotlib Figure | None
- risk_dataframe(ranking)                        -> pandas.DataFrame

Reliability
-----------
geemap/folium and matplotlib are optional. Every function degrades gracefully:
if a plotting library or the county GeoJSON is unavailable, it logs a warning
and returns None (the Streamlit UI then shows the table instead of the map).
County geometries come from utils.geo so this module stays presentation-only.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from . import geo

logger = logging.getLogger(__name__)

try:
    import pandas as pd

    _PANDAS_AVAILABLE = True
except ImportError:  # pragma: no cover
    pd = None  # type: ignore
    _PANDAS_AVAILABLE = False


# Color stops for risk (low -> high). Used for both maps and chart.
_RISK_COLORS = [
    (0.0, "#1a9850"),   # green  - low
    (0.25, "#91cf60"),
    (0.5, "#fee08b"),   # yellow - medium
    (0.75, "#fc8d59"),
    (1.0, "#d73027"),   # red    - high
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _color_for_score(score: float) -> str:
    """Map a 0..1 risk score to a hex color via the stops above."""
    score = max(0.0, min(1.0, float(score)))
    chosen = _RISK_COLORS[0][1]
    for threshold, color in _RISK_COLORS:
        if score >= threshold:
            chosen = color
    return chosen


def _ranking_to_lookup(ranking: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index a ranking list by county name for quick lookup."""
    lookup: dict[str, dict[str, Any]] = {}
    for row in ranking:
        if isinstance(row, dict) and "county" in row:
            lookup[str(row["county"])] = row
    return lookup


def risk_dataframe(ranking: list[dict[str, Any]]) -> Any:
    """
    Build a tidy pandas DataFrame from the ranking for tables/charts.

    Columns: county, risk_score, exposed_population, flood, rainfall,
    population, elevation. Returns an empty DataFrame if pandas is missing.
    """
    if not _PANDAS_AVAILABLE:
        logger.warning("pandas unavailable; cannot build DataFrame.")
        return None

    rows: list[dict[str, Any]] = []
    for r in ranking:
        if not isinstance(r, dict):
            continue
        components = r.get("components", {})
        rows.append(
            {
                "county": r.get("county"),
                "risk_score": r.get("risk_score"),
                "exposed_population": r.get("exposed_population"),
                "flood": components.get("flood"),
                "rainfall": components.get("rainfall"),
                "population": components.get("population"),
                "elevation": components.get("elevation"),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Maps
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Map centring — Lake Victoria (Winam Gulf) is the centre of this study.
# ---------------------------------------------------------------------------
# Exact coordinates (WGS84 decimal degrees), not estimates:
#   Winam Gulf (GeoNames ID 178104): -0.26721, 34.5336
#     the Kenyan arm of Lake Victoria that all five basin counties surround.
#   Kisumu port:      -0.091702, 34.767956
#   Homa Bay town:    -0.517,    34.450
# Winam Gulf is used as the default centre because it is the geographic heart
# of the study area, with Kisumu on its northeastern shore and Homa Bay on the
# southern shore.
LAKE_VICTORIA_CENTER: tuple[float, float] = (-0.26721, 34.5336)  # (lat, lon)
DEFAULT_ZOOM: int = 8


def _new_map(
    center: tuple[float, float] = LAKE_VICTORIA_CENTER,
    zoom: int = DEFAULT_ZOOM,
) -> Any | None:
    """
    Create a base interactive map.

    Prefers folium, which needs no authentication and is ideal for these static
    county choropleths. geemap is only used when Earth Engine has ALREADY been
    initialized in this process — importing/instantiating geemap can otherwise
    trigger a blocking Earth Engine auth prompt, which would hang the Streamlit
    app and the live demo. Returns None if no mapping library is available.
    """
    # 1. folium first: lightweight, no auth, perfect for choropleths.
    try:
        import folium  # type: ignore

        return folium.Map(location=list(center), zoom_start=zoom)
    except ImportError:
        logger.error(
            "folium is NOT installed — the risk map cannot be drawn. "
            "Fix with:  pip install folium"
        )
    except Exception as exc:
        logger.error("folium failed to create a map (%s).", exc)

    # 2. geemap only if Earth Engine is already initialized (never trigger auth).
    try:
        from ..tools import earth_engine as _ee_tool

        if getattr(_ee_tool, "_EE_INITIALIZED", False):
            import geemap  # type: ignore

            return geemap.Map(center=center, zoom=zoom)
        logger.debug("Earth Engine not initialized; skipping geemap to avoid auth.")
    except Exception as exc:
        logger.error("No mapping library available (%s).", exc)

    logger.error(
        "Map could not be created. Install folium:  pip install folium"
    )
    return None


def _add_county_polygons(
    map_obj: Any,
    scored_counties: dict[str, dict[str, Any]],
    only: set[str] | None = None,
) -> int:
    """
    Add county polygons colored by risk score to a folium/geemap map.

    Returns the number of counties drawn. Uses utils.geo for geometries.
    """
    try:
        import folium  # type: ignore
    except ImportError:
        logger.warning("folium not available; cannot draw polygons.")
        return 0

    drawn = 0
    for name, row in scored_counties.items():
        if only is not None and name not in only:
            continue
        geometry = geo.get_county_geometry(name)
        if geometry is None:
            continue
        score = float(row.get("risk_score", 0.0))
        exposed = row.get("exposed_population", 0)
        color = _color_for_score(score)
        tooltip = f"{name}: risk {score:.2f}, ~{int(exposed):,} exposed"
        try:
            gj = folium.GeoJson(
                data=geometry.__geo_interface__,
                style_function=(lambda _f, c=color: {
                    "fillColor": c,
                    "color": "#333333",
                    "weight": 1,
                    "fillOpacity": 0.65,
                }),
                tooltip=tooltip,
            )
            # geemap.Map exposes add_child via the underlying folium map.
            add_child = getattr(map_obj, "add_child", None)
            if callable(add_child):
                map_obj.add_child(gj)
            else:
                gj.add_to(map_obj)
            drawn += 1
        except Exception as exc:
            logger.debug("Failed to draw %s: %s", name, exc)
    return drawn


def _fit_to_counties(map_obj: Any, county_names: set[str]) -> None:
    """
    Zoom the map to the bounding box of the given counties.

    Keeps Lake Victoria and the basin counties filling the frame regardless of
    which subset was scored. Silently does nothing if bounds can't be computed.
    """
    try:
        lats: list[float] = []
        lons: list[float] = []
        for name in county_names:
            geometry = geo.get_county_geometry(name)
            bounds = geo.bounding_box(geometry)
            if bounds is None:
                continue
            minx, miny, maxx, maxy = bounds
            lons.extend([minx, maxx])
            lats.extend([miny, maxy])
        if not lats or not lons:
            return
        # folium expects [[south, west], [north, east]]
        map_obj.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])
    except Exception as exc:
        logger.debug("Could not fit map bounds: %s", exc)


def build_risk_map(
    ranking: list[dict[str, Any]],
    top_n: int | None = None,
    config: dict[str, Any] | None = None,
) -> Any | None:
    """
    Build an interactive choropleth map of county risk scores.

    Parameters
    ----------
    ranking:
        The 'ranking' list from tools.risk_score.compute_risk_score.
    top_n:
        If given, only color the top_n counties (others omitted).
    config:
        Reserved for future styling configuration.

    Returns
    -------
    map object or None
        A geemap/folium map, or None if mapping is unavailable.
    """
    if not ranking:
        logger.warning("Empty ranking; no map produced.")
        return None

    map_obj = _new_map()
    if map_obj is None:
        return None

    lookup = _ranking_to_lookup(ranking)
    only = None
    if top_n:
        only = {row["county"] for row in ranking[: max(1, top_n)] if "county" in row}

    drawn = _add_county_polygons(map_obj, lookup, only=only)
    logger.info("Risk map drew %d counties.", drawn)

    # Fit the view to the counties actually drawn, so the Lake Victoria basin
    # fills the map instead of sitting in a corner.
    _fit_to_counties(map_obj, only if only else set(lookup.keys()))
    return map_obj


def build_ranked_map(
    ranking: list[dict[str, Any]],
    top_n: int = 10,
    config: dict[str, Any] | None = None,
) -> Any | None:
    """
    Build a map highlighting only the top_n highest-risk counties, with
    numbered markers at their centroids.
    """
    if not ranking:
        return None

    map_obj = _new_map()
    if map_obj is None:
        return None

    top = ranking[: max(1, top_n)]
    lookup = _ranking_to_lookup(top)
    only = {row["county"] for row in top if "county" in row}
    _add_county_polygons(map_obj, lookup, only=only)

    # Add ranked markers.
    try:
        import folium  # type: ignore

        for rank, row in enumerate(top, start=1):
            name = row.get("county")
            if not name:
                continue
            c = geo.county_centroid(name)
            if c is None:
                continue
            lon, lat = c
            marker = folium.Marker(
                location=[lat, lon],
                tooltip=f"#{rank} {name} (risk {float(row.get('risk_score', 0)):.2f})",
                icon=folium.DivIcon(
                    html=(
                        f'<div style="font-size:12px;font-weight:bold;color:#fff;'
                        f'background:#222;border-radius:50%;width:22px;height:22px;'
                        f'text-align:center;line-height:22px;">{rank}</div>'
                    )
                ),
            )
            add_child = getattr(map_obj, "add_child", None)
            if callable(add_child):
                map_obj.add_child(marker)
            else:
                marker.add_to(map_obj)
    except Exception as exc:
        logger.debug("Failed to add ranked markers: %s", exc)

    return map_obj


# ---------------------------------------------------------------------------
# Bar chart
# ---------------------------------------------------------------------------
def build_risk_bar_chart(
    ranking: list[dict[str, Any]],
    top_n: int = 10,
) -> Any | None:
    """
    Build a horizontal bar chart of the top_n counties by risk score.

    Returns a matplotlib Figure, or None if matplotlib is unavailable or the
    ranking is empty.
    """
    if not ranking:
        return None
    try:
        import matplotlib

        matplotlib.use("Agg")  # safe for headless / Streamlit environments
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib unavailable; cannot build bar chart.")
        return None

    top = ranking[: max(1, top_n)]
    names = [str(r.get("county", "?")) for r in top][::-1]
    scores = [float(r.get("risk_score", 0.0)) for r in top][::-1]
    colors = [_color_for_score(s) for s in scores]

    fig, ax = plt.subplots(figsize=(8, max(3, 0.45 * len(top))))
    ax.barh(names, scores, color=colors, edgecolor="#333333")
    ax.set_xlabel("Climate-risk score (0–1)")
    ax.set_xlim(0, 1)
    ax.set_title(f"Top {len(top)} Kenyan counties by climate-risk score")
    for i, score in enumerate(scores):
        ax.text(score + 0.01, i, f"{score:.2f}", va="center", fontsize=9)
    fig.tight_layout()
    return fig


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    from ..tools import risk_score

    result = risk_score.compute_risk_score(
        ["Tana River", "Garissa", "Nairobi", "Turkana", "Busia"]
    )
    df = risk_dataframe(result["ranking"])
    if df is not None:
        print(df.to_string(index=False))
    fig = build_risk_bar_chart(result["ranking"], top_n=5)
    print("Bar chart built:", fig is not None)
    m = build_risk_map(result["ranking"], top_n=5)
    print("Risk map built:", m is not None)


# ===========================================================================
# RICH LAKE VICTORIA MAP
# ---------------------------------------------------------------------------
# The plain county choropleth was not enough for the workshop: users need to
# see WHERE the risk is — sub-counties, towns, and named flood features — and
# click for detail. This section adds those layers on top of the existing
# county map, with a LayerControl so each can be toggled.
# ===========================================================================

def _add_subcounty_layer(map_obj: Any, sub_ranking: list[dict[str, Any]]) -> int:
    """
    Draw sub-county polygons coloured by risk, with click popups.

    Each popup shows the sub-county, its parent county, risk score, component
    breakdown, exposed population and any named flood features.
    """
    try:
        import folium  # type: ignore
    except ImportError:
        return 0

    from . import admin_levels

    group = folium.FeatureGroup(name="Sub-counties (risk)", show=True)
    drawn = 0
    for row in sub_ranking:
        name = row.get("subcounty")
        if not name:
            continue
        geometry = admin_levels.get_subcounty_geometry(name)
        if geometry is None:
            continue
        score = float(row.get("risk_score", 0.0))
        comp = row.get("components", {})
        feats = row.get("flood_features") or []
        popup_html = (
            f"<div style='font-family:sans-serif;min-width:230px'>"
            f"<b style='font-size:14px'>{name}</b><br>"
            f"<span style='color:#666'>{row.get('county','')} County — sub-county</span><hr style='margin:4px 0'>"
            f"<b>Risk score: {score:.3f}</b><br>"
            f"Exposed population: ~{int(row.get('exposed_population',0)):,}<br>"
            f"<hr style='margin:4px 0'>"
            f"Flood signal: {comp.get('flood','-')}<br>"
            f"Rainfall: {comp.get('rainfall','-')}<br>"
            f"Elevation vulnerability: {comp.get('elevation','-')}<br>"
            + (f"<hr style='margin:4px 0'><b>Flood features:</b><br>{'<br>'.join(feats)}"
               if feats else "")
            + "</div>"
        )
        try:
            folium.GeoJson(
                data=geometry.__geo_interface__,
                style_function=(lambda _f, c=_color_for_score(score): {
                    "fillColor": c, "color": "#222", "weight": 1, "fillOpacity": 0.6,
                }),
                highlight_function=lambda _f: {"weight": 3, "color": "#000"},
                tooltip=f"{name} — risk {score:.2f}",
                popup=folium.Popup(popup_html, max_width=300),
            ).add_to(group)
            drawn += 1
        except Exception as exc:
            logger.debug("Could not draw sub-county %s: %s", name, exc)
    group.add_to(map_obj)
    return drawn


def _add_settlements_layer(map_obj: Any) -> int:
    """Plot towns and settlements from data/settlements.geojson."""
    try:
        import folium  # type: ignore
        import json as _json
    except ImportError:
        return 0

    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.abspath(os.path.join(here, "..", "..", "data", "settlements.geojson"))
    if not os.path.exists(path):
        return 0

    from . import lake_victoria

    basin = {c.lower().replace(" ", "") for c in lake_victoria.BASIN_COUNTIES}
    group = folium.FeatureGroup(name="Towns & settlements", show=True)
    drawn = 0
    try:
        data = _json.load(open(path, encoding="utf-8"))
        for feat in data.get("features", []):
            props = feat.get("properties", {})
            county = str(props.get("county", "")).lower().replace(" ", "")
            if county not in basin:
                continue
            lon, lat = feat["geometry"]["coordinates"][:2]
            pop = props.get("population")
            folium.CircleMarker(
                location=[lat, lon],
                radius=6,
                color="#1a73e8",
                fill=True,
                fill_color="#1a73e8",
                fill_opacity=0.9,
                tooltip=f"{props.get('name')} ({props.get('county')})",
                popup=folium.Popup(
                    f"<b>{props.get('name')}</b><br>{props.get('county')} County"
                    + (f"<br>Population: ~{int(pop):,}" if pop else ""),
                    max_width=220,
                ),
            ).add_to(group)
            drawn += 1
    except Exception as exc:
        logger.debug("Settlement layer failed: %s", exc)
    group.add_to(map_obj)
    return drawn


def _add_flood_features_layer(map_obj: Any) -> int:
    """
    Mark named flood features — Kano Plains, Nyando Basin, Budalangi, Yala
    Swamp, Winam Gulf shoreline — at the centroid of their sub-counties.
    """
    try:
        import folium  # type: ignore
    except ImportError:
        return 0

    from . import admin_levels

    group = folium.FeatureGroup(name="Flood features (wetlands, plains, basins)", show=True)
    drawn = 0
    for feature_name, info in admin_levels.FLOOD_FEATURES.items():
        for sc in info["subcounties"]:
            geometry = admin_levels.get_subcounty_geometry(sc)
            c = geo.centroid(geometry)
            if c is None:
                continue
            lon, lat = c
            try:
                folium.Marker(
                    location=[lat, lon],
                    tooltip=f"{feature_name} ({sc})",
                    popup=folium.Popup(
                        f"<b>{feature_name}</b><br><i>{sc}, "
                        f"{info['county']} County</i><br><br>{info['description']}",
                        max_width=280,
                    ),
                    icon=folium.Icon(color="darkblue", icon="tint", prefix="fa"),
                ).add_to(group)
                drawn += 1
                break  # one marker per feature is enough
            except Exception as exc:
                logger.debug("Flood feature marker failed (%s): %s", feature_name, exc)
    group.add_to(map_obj)
    return drawn


def build_rich_map(
    ranking: list[dict[str, Any]] | None = None,
    sub_ranking: list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> Any | None:
    """
    Build the full Lake Victoria workshop map.

    Layers (each toggleable):
      - County risk choropleth (if a county ranking is supplied)
      - Sub-county risk choropleth with click popups (if a sub-county ranking is supplied)
      - Towns & settlements
      - Named flood features (Kano Plains, Budalangi, Yala Swamp, ...)

    Returns a folium Map, or None if no mapping library is available.
    """
    map_obj = _new_map()
    if map_obj is None:
        return None

    try:
        import folium  # type: ignore
    except ImportError:
        return map_obj

    fit_names: set[str] = set()

    if ranking:
        lookup = _ranking_to_lookup(ranking)
        county_group = folium.FeatureGroup(name="Counties (risk)", show=not sub_ranking)
        for name, row in lookup.items():
            geometry = geo.get_county_geometry(name)
            if geometry is None:
                continue
            score = float(row.get("risk_score", 0.0))
            try:
                folium.GeoJson(
                    data=geometry.__geo_interface__,
                    style_function=(lambda _f, c=_color_for_score(score): {
                        "fillColor": c, "color": "#333", "weight": 2,
                        "fillOpacity": 0.35,
                    }),
                    tooltip=(
                        f"{name} County — risk {score:.2f}, "
                        f"~{int(row.get('exposed_population', 0)):,} exposed"
                    ),
                ).add_to(county_group)
                fit_names.add(name)
            except Exception as exc:
                logger.debug("County layer failed for %s: %s", name, exc)
        county_group.add_to(map_obj)

    n_sub = _add_subcounty_layer(map_obj, sub_ranking or [])
    n_towns = _add_settlements_layer(map_obj)
    n_feats = _add_flood_features_layer(map_obj)
    logger.info(
        "Rich map layers — sub-counties: %d, towns: %d, flood features: %d",
        n_sub, n_towns, n_feats,
    )

    try:
        folium.LayerControl(collapsed=False).add_to(map_obj)
    except Exception as exc:
        logger.debug("LayerControl failed: %s", exc)

    # Fullscreen button (expand icon, top-left) so the map can fill the screen.
    try:
        from folium.plugins import Fullscreen  # type: ignore

        Fullscreen(
            position="topleft",
            title="Expand to fullscreen",
            title_cancel="Exit fullscreen",
            force_separate_button=True,
        ).add_to(map_obj)
    except Exception as exc:
        logger.debug("Fullscreen control unavailable: %s", exc)

    # Mouse-position readout so users can see coordinates as they hover.
    try:
        from folium.plugins import MousePosition  # type: ignore

        MousePosition(position="bottomleft", prefix="Lat/Lon:").add_to(map_obj)
    except Exception as exc:
        logger.debug("MousePosition unavailable: %s", exc)

    if fit_names:
        _fit_to_counties(map_obj, fit_names)
    else:
        from . import lake_victoria

        _fit_to_counties(map_obj, set(lake_victoria.BASIN_COUNTIES))

    return map_obj


def build_subcounty_bar_chart(
    sub_ranking: list[dict[str, Any]],
    top_n: int = 5,
) -> Any | None:
    """
    Horizontal bar chart of the top_n SUB-COUNTIES by flood-risk score.

    Mirrors build_risk_bar_chart but labels each bar with the sub-county and
    its parent county, so a sub-county answer always gets a matching chart.
    Returns a matplotlib Figure, or None if matplotlib is unavailable.
    """
    if not sub_ranking:
        return None
    try:
        import matplotlib

        matplotlib.use("Agg")  # headless-safe for Streamlit
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib unavailable; cannot build sub-county chart.")
        return None

    top = sub_ranking[: max(1, top_n)]
    labels = [
        f"{r.get('subcounty', '?')}\n({r.get('county', '')})" for r in top
    ][::-1]
    scores = [float(r.get("risk_score", 0.0)) for r in top][::-1]
    colors = [_color_for_score(s) for s in scores]

    fig, ax = plt.subplots(figsize=(8, max(3, 0.75 * len(top))))
    ax.barh(labels, scores, color=colors, edgecolor="#333333")
    ax.set_xlabel("Flood-risk score (0-1)")
    ax.set_xlim(0, 1)
    ax.set_title(f"Top {len(top)} sub-counties by flood-risk score")
    for i, score in enumerate(scores):
        ax.text(score + 0.01, i, f"{score:.2f}", va="center", fontsize=9)
    fig.tight_layout()
    return fig


def save_map_html(map_obj: Any, filename: str = "lake_victoria_map.html") -> str | None:
    """
    Save a folium map to a standalone HTML file and return its path.

    Used by the Streamlit app to offer a "open full map in a new tab" download,
    which gives users an unconstrained, full-window version of the map.
    """
    if map_obj is None:
        return None
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        root = os.path.abspath(os.path.join(here, "..", ".."))
        out_dir = os.path.join(root, "outputs")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, filename)
        map_obj.save(path)
        return path
    except Exception as exc:
        logger.warning("Could not save map HTML: %s", exc)
        return None