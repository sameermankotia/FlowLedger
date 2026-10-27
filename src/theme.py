"""Chart palette and Altair defaults for the dashboard.

The colour choices are not freehand. The categorical pair and the ordinal
ramp below were checked with a palette validator for colour-vision
separation, lightness banding and contrast against the chart surface:

    categorical  #2a78d6 / #eb6834   worst adjacent CVD dE 24.7, normal 33.6
    ordinal      5-step single-hue blue, monotone L, light end 2.06:1

Everything renders on the light surface the palette was validated against,
which is why .streamlit/config.toml pins the theme rather than following the
operating system.
"""

from __future__ import annotations

import altair as alt

# -- surfaces and ink -------------------------------------------------------
SURFACE = "#fcfcfb"
PLANE = "#f9f9f7"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BORDER = "rgba(11,11,11,0.10)"

# -- categorical: identity. Fixed order, never cycled. ----------------------
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]

# -- ordinal: discrete ordered magnitude (aging buckets) --------------------
# Light end clears 2:1 against the surface, as an ordinal ramp must.
RAMP_BLUE = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"]

# -- diverging: polarity (profit vs loss). Gray midpoint, never a hue. ------
POSITIVE = "#2a78d6"
NEGATIVE = "#d03b3b"
MIDPOINT = "#f0efec"

# -- status: reserved. Always paired with a label, never colour alone. ------
STATUS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
}

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

MONEY = "$,.0f"


def altair_theme() -> dict:
    """Recessive axes, hairline grid, text in ink tokens not series colour."""
    return {
        "config": {
            "background": SURFACE,
            "font": FONT,
            "view": {"stroke": "transparent", "continuousHeight": 280},
            "title": {
                "fontSize": 14,
                "fontWeight": 600,
                "color": INK,
                "subtitleColor": INK_SECONDARY,
                "subtitleFontSize": 12,
                "anchor": "start",
                "offset": 12,
            },
            "axis": {
                "labelColor": INK_MUTED,
                "labelFontSize": 11,
                "titleColor": INK_SECONDARY,
                "titleFontSize": 11,
                "titleFontWeight": 500,
                "gridColor": GRID,
                "gridWidth": 1,
                "domainColor": AXIS,
                "tickColor": AXIS,
                "tickSize": 4,
                "labelPadding": 6,
            },
            "axisX": {"grid": False},
            "axisY": {"domain": False, "ticks": False},
            "legend": {
                "labelColor": INK_SECONDARY,
                "labelFontSize": 11,
                "titleColor": INK_MUTED,
                "titleFontSize": 11,
                "symbolType": "square",
                "symbolSize": 90,
                "orient": "top",
                "direction": "horizontal",
                "offset": 4,
            },
            "range": {"category": SERIES, "ordinal": RAMP_BLUE},
            "bar": {"cornerRadiusEnd": 4},
            "line": {"strokeWidth": 2},
            "point": {"size": 70, "filled": True},
            "text": {"font": FONT, "fontSize": 11, "color": INK_SECONDARY},
        }
    }


def register() -> None:
    """Install the theme as Altair's active one."""
    alt.theme.register("erp", enable=True)(altair_theme)
