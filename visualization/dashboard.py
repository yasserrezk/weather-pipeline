import sys
from dotenv import load_dotenv
import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc
from datetime import datetime
import pytz

sys.path.insert(0, os.path.abspath(".."))
load_dotenv("../.env")

# ── database ──────────────────────────────────────────────────────────────────


def load_data() -> pd.DataFrame:
    """Load weather data from PostgreSQL."""
    from sqlalchemy import create_engine, text

    host = "localhost"
    port = os.getenv("DB_PORT", "5432")
    db = os.getenv("DB_NAME", "weather")
    user = os.getenv("DB_USER", "admin")
    pwd = os.getenv("DB_PASSWORD", "password")
    url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"
    engine = create_engine(url)

    with engine.connect() as conn:
        df = pd.read_sql(
            text("SELECT * FROM weather_forecasts ORDER BY forecast_time"),
            conn,
        )
    df["forecast_time"] = pd.to_datetime(df["forecast_time"], utc=True)
    return df


# ── palette & layout helpers ──────────────────────────────────────────────────

DARK_BG = "#160f17"
CARD_BG = "#2d133a"
ACCENT = "#4f8ef7"
ACCENT2 = "#f7934f"
ACCENT3 = "#4ff7a8"
TEXT = "#e0e4f0"
MUTED = "#6c7293"

CARD_STYLE = {
    "background": CARD_BG,
    "borderRadius": "12px",
    "padding": "20px",
    "marginBottom": "16px",
    "border": "1px solid #2a2d3e",
}


def stat_card(title, value, unit="", icon="", color=ACCENT):
    return html.Div(
        [
            html.Div(
                [
                    html.Span(icon, style={"fontSize": "28px", "marginRight": "10px"}),
                    html.Span(
                        title,
                        style={
                            "fontSize": "12px",
                            "color": MUTED,
                            "textTransform": "uppercase",
                            "letterSpacing": "1px",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "marginBottom": "8px",
                },
            ),
            html.Div(
                [
                    html.Span(
                        value,
                        style={"fontSize": "32px", "fontWeight": "700", "color": color},
                    ),
                    html.Span(f" {unit}", style={"fontSize": "16px", "color": MUTED}),
                ]
            ),
        ],
        style={**CARD_STYLE, "minWidth": "180px"},
    )


# ── load data ─────────────────────────────────────────────────────────────────
df_all = load_data()

LOCATIONS = [
    {
        "label": f"({row['latitude']:.2f}, {row['longitude']:.2f})",
        "value": f"{row['latitude']}|{row['longitude']}",
    }
    for _, row in df_all[["latitude", "longitude"]].drop_duplicates().iterrows()
]

# ── app ───────────────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],
    title="Weather Pipeline Dashboard",
)

app.layout = html.Div(
    style={
        "background": DARK_BG,
        "minHeight": "100vh",
        "fontFamily": "'Inter', sans-serif",
        "color": TEXT,
    },
    children=[
        # ── header ──
        html.Div(
            [
                html.Div(
                    [
                        html.H1(
                            "🌤 Weather Pipeline Dashboard",
                            style={
                                "margin": 0,
                                "fontSize": "30px",
                                "fontWeight": "800",
                            },
                        ),
                        html.Span(
                            "    Weather Dashboard ETL Analytics",
                            style={"fontSize": "16px", "color": MUTED},
                        ),
                    ]
                ),
                html.Div(
                    [
                        # Cairo clock — updates every second
                        html.Div(
                            id="cairo-clock",
                            style={
                                "fontSize": "16px",
                                "color": "#cbbad4",
                                "fontWeight": "600",
                                "background": "#160f17",
                                "padding": "6px 16px",
                                "borderRadius": "20px",
                                "border": "1px solid #2a2d3e",
                                "marginRight": "12px",
                                "letterSpacing": "0.5px",
                            },
                        ),
                        html.Span(
                            "Live database connected",
                            style={
                                "fontSize": "16px",
                                "color": "#cbbad4",
                                "fontWeight": "600",
                                "background": "#160f17",
                                "padding": "6px 14px",
                                "borderRadius": "20px",
                            },
                        ),
                    ],
                    style={"display": "flex", "alignItems": "center"},
                ),
                dcc.Interval(id="clock-interval", interval=1000, n_intervals=0),
            ],
            style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "background": CARD_BG,
                "padding": "16px 28px",
                "borderBottom": "1px solid #2a2d3e",
                "position": "sticky",
                "top": 0,
                "zIndex": 100,
            },
        ),
        html.Div(
            style={"padding": "24px 28px"},
            children=[
                # ── controls ──
                html.Div(
                    [
                        html.Div(
                            [
                                html.Label(
                                    "Location",
                                    style={
                                        "fontSize": "12px",
                                        "color": MUTED,
                                        "marginBottom": "4px",
                                        "display": "block",
                                    },
                                ),
                                dcc.Dropdown(
                                    id="loc-select",
                                    options=LOCATIONS,
                                    value=LOCATIONS[0]["value"],
                                    clearable=True,
                                    style={
                                        "background": CARD_BG,
                                        "color": "#2d133a",
                                        "border": "1px solid #2a2d3e",
                                        "minWidth": "220px",
                                    },
                                ),
                            ]
                        ),
                        html.Div(
                            [
                                html.Label(
                                    "Time Window",
                                    style={
                                        "fontSize": "12px",
                                        "color": MUTED,
                                        "marginBottom": "4px",
                                        "display": "block",
                                    },
                                ),
                                dcc.Dropdown(
                                    id="window-select",
                                    options=[
                                        {"label": "Last 24 h", "value": 24},
                                        {"label": "Last 48 h", "value": 48},
                                        {"label": "Last 7 days", "value": 168},
                                    ],
                                    value=168,
                                    clearable=False,
                                    style={
                                        "backgroundColor": "#2d133a", # or "#FF00FF"
                                        "color": "#2d133a",             # Changed for better contrast
                                        "border": "1px solid #2a2d3e",
                                        "minWidth": "160px",
                                    },
                                ),
                            ]
                        ),
                    ],
                    style={
                        "display": "flex",
                        "gap": "20px",
                        "marginBottom": "24px",
                        "flexWrap": "wrap",
                    },
                ),
                # ── stat cards ──
                html.Div(
                    id="stat-cards",
                    style={
                        "display": "flex",
                        "gap": "16px",
                        "flexWrap": "wrap",
                        "marginBottom": "8px",
                    },
                ),
                # ── row 1: temperature + humidity ──
                html.Div(
                    [
                        html.Div(
                            [
                                dcc.Graph(
                                    id="temp-chart", config={"displayModeBar": False}
                                )
                            ],
                            style={**CARD_STYLE, "flex": "2"},
                        ),
                        html.Div(
                            [
                                dcc.Graph(
                                    id="humidity-chart",
                                    config={"displayModeBar": False},
                                )
                            ],
                            style={**CARD_STYLE, "flex": "1"},
                        ),
                    ],
                    style={"display": "flex", "gap": "16px", "flexWrap": "wrap"},
                ),
                # ── row 2: wind + precipitation ──
                html.Div(
                    [
                        html.Div(
                            [
                                dcc.Graph(
                                    id="wind-chart", config={"displayModeBar": False}
                                )
                            ],
                            style={**CARD_STYLE, "flex": "1"},
                        ),
                        html.Div(
                            [
                                dcc.Graph(
                                    id="rain-chart", config={"displayModeBar": False}
                                )
                            ],
                            style={**CARD_STYLE, "flex": "1"},
                        ),
                    ],
                    style={"display": "flex", "gap": "16px", "flexWrap": "wrap"},
                ),
                # ── row 3: uv + pressure + cloud ──
                html.Div(
                    [
                        html.Div(
                            [
                                dcc.Graph(
                                    id="uv-chart", config={"displayModeBar": False}
                                )
                            ],
                            style={**CARD_STYLE, "flex": "1"},
                        ),
                        html.Div(
                            [
                                dcc.Graph(
                                    id="pressure-chart",
                                    config={"displayModeBar": False},
                                )
                            ],
                            style={**CARD_STYLE, "flex": "1"},
                        ),
                        html.Div(
                            [
                                dcc.Graph(
                                    id="cloud-chart", config={"displayModeBar": False}
                                )
                            ],
                            style={**CARD_STYLE, "flex": "1"},
                        ),
                    ],
                    style={"display": "flex", "gap": "16px", "flexWrap": "wrap"},
                ),
                # ── row 4: wind rose + visibility ──
                html.Div(
                    [
                        html.Div(
                            [
                                dcc.Graph(
                                    id="wind-rose", config={"displayModeBar": False}
                                )
                            ],
                            style={**CARD_STYLE, "flex": "1"},
                        ),
                        html.Div(
                            [
                                dcc.Graph(
                                    id="visibility-chart",
                                    config={"displayModeBar": False},
                                )
                            ],
                            style={**CARD_STYLE, "flex": "2"},
                        ),
                    ],
                    style={"display": "flex", "gap": "16px", "flexWrap": "wrap"},
                ),
            ],
        ),
    ],
)


# ── Cairo clock callback ───────────────────────────────────────────────────────


@app.callback(
    Output("cairo-clock", "children"),
    Input("clock-interval", "n_intervals"),
)
def update_clock(_):
    cairo_tz = pytz.timezone("Africa/Cairo")
    now = datetime.now(cairo_tz)
    return f"🕐 Cairo  {now.strftime('%A, %d %b %Y  |  %H:%M:%S')}"


# ── charts callback ───────────────────────────────────────────────────────────

PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=TEXT, family="Inter, sans-serif", size=12),
    margin=dict(l=10, r=10, t=40, b=10),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
    xaxis=dict(gridcolor="#2a2d3e", linecolor="#2a2d3e", zeroline=False),
    yaxis=dict(gridcolor="#2a2d3e", linecolor="#2a2d3e", zeroline=False),
)


def filter_df(loc_val, window):
    lat_str, lon_str = loc_val.split("|")
    lat, lon = float(lat_str), float(lon_str)
    df = df_all[(df_all["latitude"] == lat) & (df_all["longitude"] == lon)].copy()
    cutoff = df["forecast_time"].max() - pd.Timedelta(hours=window)
    return df[df["forecast_time"] >= cutoff].sort_values("forecast_time")


@app.callback(
    Output("stat-cards", "children"),
    Output("temp-chart", "figure"),
    Output("humidity-chart", "figure"),
    Output("wind-chart", "figure"),
    Output("rain-chart", "figure"),
    Output("uv-chart", "figure"),
    Output("pressure-chart", "figure"),
    Output("cloud-chart", "figure"),
    Output("wind-rose", "figure"),
    Output("visibility-chart", "figure"),
    Input("loc-select", "value"),
    Input("window-select", "value"),
)
def update_all(loc_val, window):
    df = filter_df(loc_val, window)
    latest = df.iloc[-1] if len(df) else pd.Series(dtype=float)

    # ── stat cards ──
    cards = [
        stat_card(
            "Temperature", f"{latest.get('temperature_2m', '—')}", "°C", "🌡️", ACCENT
        ),
        stat_card(
            "Feels Like",
            f"{latest.get('apparent_temperature', '—')}",
            "°C",
            "🤔",
            ACCENT2,
        ),
        stat_card(
            "Humidity", f"{latest.get('relative_humidity_2m', '—')}", "%", "💧", ACCENT3
        ),
        stat_card(
            "Wind Speed",
            f"{latest.get('wind_speed_10m', '—')}",
            "km/h",
            "💨",
            "#a78bfa",
        ),
        stat_card("UV Index", f"{latest.get('uv_index', '—')}", "", "☀️", "#fbbf24"),
        stat_card("Rain", f"{latest.get('rain', '—')}", "mm", "🌧️", "#60a5fa"),
    ]

    # ── temperature chart ──
    fig_temp = go.Figure()
    fig_temp.add_trace(
        go.Scatter(
            x=df["forecast_time"],
            y=df["temperature_2m"],
            name="Temperature",
            line=dict(color=ACCENT, width=2),
            fill="tozeroy",
            fillcolor="rgba(79,142,247,0.08)",
        )
    )
    fig_temp.add_trace(
        go.Scatter(
            x=df["forecast_time"],
            y=df["apparent_temperature"],
            name="Feels Like",
            line=dict(color=ACCENT2, width=1.5, dash="dot"),
        )
    )
    fig_temp.add_trace(
        go.Scatter(
            x=df["forecast_time"],
            y=df["dew_point_2m"],
            name="Dew Point",
            line=dict(color=ACCENT3, width=1.5, dash="dash"),
        )
    )
    fig_temp.update_layout(
        **PLOT_LAYOUT,  # type: ignore
        title="Temperature Overview (°C)",
        yaxis_title="°C",
        xaxis_title="",
    )
    for _, row in df.iterrows():
        if not row["is_day"]:
            fig_temp.add_vrect(
                x0=row["forecast_time"],
                x1=row["forecast_time"] + pd.Timedelta(hours=1),
                fillcolor="rgba(0,0,0,0.15)",
                line_width=0,
                layer="below",
            )

    # ── humidity chart ──
    fig_hum = go.Figure(
        go.Bar(
            x=df["forecast_time"],
            y=df["relative_humidity_2m"],
            name="Humidity %",
            marker=dict(
                color=df["relative_humidity_2m"],
                colorscale=[[0, "#3b82f6"], [0.5, "#0ea5e9"], [1, "#06b6d4"]],
                showscale=False,
            ),
        )
    )
    fig_hum.update_layout(
        **PLOT_LAYOUT,  # type: ignore
        title="Relative Humidity (%)",
        yaxis_range=[0, 100],
        xaxis_title="",
    )

    # ── wind chart ──
    fig_wind = go.Figure()
    fig_wind.add_trace(
        go.Scatter(
            x=df["forecast_time"],
            y=df["wind_speed_10m"],
            name="Wind Speed",
            line=dict(color="#a78bfa", width=2),
        )
    )
    fig_wind.add_trace(
        go.Scatter(
            x=df["forecast_time"],
            y=df["wind_gusts_10m"],
            name="Gusts",
            line=dict(color="#f472b6", width=1.5, dash="dot"),
            fill="tonexty",
            fillcolor="rgba(244,114,182,0.08)",
        )
    )
    fig_wind.update_layout(
        **PLOT_LAYOUT, title="Wind Speed & Gusts (km/h)", xaxis_title=""  # type: ignore
    )

    # ── rain chart ──
    fig_rain = go.Figure()
    fig_rain.add_trace(
        go.Bar(
            x=df["forecast_time"],
            y=df["rain"],
            name="Rain (mm)",
            marker_color="#60a5fa",
            opacity=0.85,
        )
    )
    fig_rain.add_trace(
        go.Scatter(
            x=df["forecast_time"],
            y=df["precipitation_probability"],
            name="Precip. Prob. %",
            yaxis="y2",
            line=dict(color=ACCENT2, width=1.5, dash="dot"),
        )
    )
    fig_rain.update_layout(
        **PLOT_LAYOUT,  # type: ignore
        title="Rainfall & Precipitation Probability",
        yaxis_title="Rain (mm)",
        xaxis_title="",
        yaxis2=dict(
            title="Prob. %",
            overlaying="y",
            side="right",
            gridcolor="#2a2d3e",
            zeroline=False,
            range=[0, 100],
        ),
    )

    # ── UV index chart ──
    uv_vals = df["uv_index"].clip(0, 11)
    fig_uv = go.Figure(
        go.Bar(
            x=df["forecast_time"],
            y=uv_vals,
            marker=dict(
                color=uv_vals,
                colorscale=[
                    [0, "#22c55e"],
                    [0.3, "#eab308"],
                    [0.6, "#f97316"],
                    [1, "#7c3aed"],
                ],
                showscale=True,
                colorbar=dict(thickness=8, title="UV"),
            ),
        )
    )
    fig_uv.update_layout(**PLOT_LAYOUT, title="UV Index", xaxis_title="")  # type: ignore

    # ── surface pressure chart ──
    fig_pres = go.Figure(
        go.Scatter(
            x=df["forecast_time"],
            y=df["surface_pressure"],
            line=dict(color="#34d399", width=2),
            fill="tozeroy",
            fillcolor="rgba(52,211,153,0.07)",
            name="Pressure",
        )
    )
    fig_pres.update_layout(
        **PLOT_LAYOUT, title="Surface Pressure (hPa)", xaxis_title=""  # type: ignore
    )

    # ── cloud cover chart ──
    fig_cloud = go.Figure(
        go.Scatter(
            x=df["forecast_time"],
            y=df["cloud_cover"],
            line=dict(color="#94a3b8", width=2),
            fill="tozeroy",
            fillcolor="rgba(148,163,184,0.12)",
            name="Cloud Cover %",
        )
    )
    fig_cloud.update_layout(
        **PLOT_LAYOUT, title="Cloud Cover (%)", yaxis_range=[0, 100], xaxis_title=""  # type: ignore
    )

    # ── wind rose ──
    dirs = df["wind_direction_10m"].values
    speeds = df["wind_speed_10m"].values
    labels = [
        "N",
        "NNE",
        "NE",
        "ENE",
        "E",
        "ESE",
        "SE",
        "SSE",
        "S",
        "SSW",
        "SW",
        "WSW",
        "W",
        "WNW",
        "NW",
        "NNW",
    ]
    freq = np.zeros(16)
    avg_spd = np.zeros(16)
    for d, s in zip(dirs, speeds):
        b = int((d + 11.25) % 360 // 22.5)
        freq[b] += 1
        avg_spd[b] += s
    mask = freq > 0
    avg_spd[mask] /= freq[mask]
    fig_rose = go.Figure(
        go.Barpolar(
            r=freq,
            theta=labels,
            name="Frequency",
            marker=dict(
                color=avg_spd,
                colorscale="Plasma",
                showscale=True,
                colorbar=dict(title="km/h", thickness=8),
            ),
        )
    )
    fig_rose.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT),
        title="Wind Rose",
        margin=dict(l=20, r=20, t=40, b=20),
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            angularaxis=dict(showgrid=True, gridcolor="#2a2d3e"),
            radialaxis=dict(showgrid=True, gridcolor="#2a2d3e", tickfont=dict(size=9)),
        ),
    )

    # ── visibility chart ──
    fig_vis = go.Figure()
    fig_vis.add_trace(
        go.Scatter(
            x=df["forecast_time"],
            y=df["visibility"] / 1000,
            name="Visibility (km)",
            line=dict(color="#f59e0b", width=2),
            fill="tozeroy",
            fillcolor="rgba(245,158,11,0.08)",
        )
    )
    fig_vis.add_hrect(
        y0=0,
        y1=1,
        fillcolor="rgba(239,68,68,0.08)",
        line_width=0,
        annotation_text="Fog threshold",
        annotation_position="top right",
        annotation_font=dict(color="#ef4444", size=10),
    )
    fig_vis.update_layout(
        **PLOT_LAYOUT, title="Visibility (km)", xaxis_title="", yaxis_title="km"  # type: ignore
    )

    return (
        cards,
        fig_temp,
        fig_hum,
        fig_wind,
        fig_rain,
        fig_uv,
        fig_pres,
        fig_cloud,
        fig_rose,
        fig_vis,
    )


if __name__ == "__main__":
    app.run(debug=True, port=8050)
