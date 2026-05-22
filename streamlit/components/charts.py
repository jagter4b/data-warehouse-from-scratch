"""
charts.py — Chart factory for Olist ML Analytics.
All charts use transparent backgrounds so the CSS surface cards show through.
Semantic palettes are keyed to the exact label strings produced by each ML script.
"""
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# ── Semantic palettes (exact labels from ML scripts) ─────────────
PALETTE      = ["#7C3AED","#06B6D4","#10B981","#F59E0B","#F43F5E",
                 "#A78BFA","#34D399","#FCD34D","#FB7185","#38BDF8"]

RISK_COLORS  = {"High":"#F43F5E", "Medium":"#F59E0B", "Low":"#10B981"}

SEG_COLORS   = {
    "Champions":       "#10B981",
    "Loyal Customers": "#06B6D4",
    "At Risk":         "#F59E0B",
    "Lost/Inactive":   "#52525B",
}

CLV_COLORS   = {
    "Platinum": "#06B6D4",
    "Gold":     "#F59E0B",
    "Silver":   "#A1A1AA",
    "Bronze":   "#92400E",
}

PERF_COLORS  = {
    "Top Performer":  "#10B981",
    "Average Seller": "#7C3AED",
    "Underperformer": "#F43F5E",
}

SAT_COLORS   = {
    "Excellent": "#10B981",
    "Good":      "#06B6D4",
    "Poor":      "#F59E0B",
    "Very Poor": "#F43F5E",
}

# ── Base layout (transparent, so CSS glass shows) ─────────────────
_L = dict(
    plot_bgcolor  = "rgba(0,0,0,0)",
    paper_bgcolor = "rgba(0,0,0,0)",
    font          = dict(family="Inter, sans-serif", color="#A1A1AA", size=13),
    margin        = dict(l=24, r=24, t=48, b=24),
    legend        = dict(orientation="h", yanchor="top", y=-0.22,
                         xanchor="center", x=0.5,
                         bgcolor="rgba(0,0,0,0)",
                         font=dict(size=12, color="#71717A")),
    hoverlabel    = dict(bgcolor="#1C1C1E", font_size=13,
                         font_family="Inter,sans-serif",
                         bordercolor="#3F3F46"),
    title         = dict(font=dict(size=14, color="#E4E4E7"),
                         x=0.0, xanchor="left"),
    coloraxis_colorbar = dict(tickfont=dict(color="#71717A")),
)
_XGRID = dict(showgrid=False, zeroline=False, title_text="",
              tickfont=dict(color="#52525B"), linecolor="rgba(0,0,0,0)")
_YGRID = dict(gridcolor="rgba(113,113,122,0.12)", zeroline=False,
              title_text="", tickfont=dict(color="#52525B"))


def _apply(fig, title=None):
    kw = dict(_L)
    if title:
        kw["title"] = dict(text=title, **_L["title"])
    fig.update_layout(**kw)
    fig.update_xaxes(**_XGRID)
    fig.update_yaxes(**_YGRID)
    return fig


# ── Bar chart ─────────────────────────────────────────────────────
def bar(df, x, y, title, *, color_col=None, cmap=None, barmode="group",
        h=False, show_legend=True):
    kx, ky = (y, x) if h else (x, y)
    orient = "h" if h else "v"
    hover  = ("<b>%{y}</b><br>%{x:,.1f}<extra></extra>" if h
               else "<b>%{x}</b><br>%{y:,.1f}<extra></extra>")

    if color_col and color_col in df.columns:
        fig = px.bar(df, x=kx, y=ky, color=color_col, barmode=barmode,
                     orientation=orient,
                     color_discrete_map=cmap, color_discrete_sequence=PALETTE)
    elif cmap and not color_col:
        axis_col = ky if h else kx
        fig = px.bar(df, x=kx, y=ky, color=axis_col, orientation=orient,
                     color_discrete_map=cmap, color_discrete_sequence=PALETTE)
        show_legend = False
    else:
        fig = px.bar(df, x=kx, y=ky, orientation=orient,
                     color_discrete_sequence=["#7C3AED"])

    fig.update_traces(marker_line_width=0, opacity=0.92,
                      hovertemplate=hover)
    _apply(fig, title)
    if not show_legend:
        fig.update_layout(showlegend=False)
    return fig


# ── Funnel chart ──────────────────────────────────────────────────
def funnel(df, cat, val, title, *, cmap=None):
    df_s = df.sort_values(val, ascending=False).reset_index(drop=True)
    colors = [(cmap or {}).get(r, PALETTE[i % len(PALETTE)])
               for i, r in enumerate(df_s[cat])]
    fig = go.Figure(go.Funnel(
        y=df_s[cat], x=df_s[val],
        marker=dict(color=colors, line=dict(width=0)),
        textinfo="value+percent total",
        textfont=dict(size=13, color="#E4E4E7"),
        hovertemplate="<b>%{y}</b><br>%{x:,} (%{percentTotal:.1%})<extra></extra>",
        connector=dict(line=dict(color="rgba(113,113,122,0.10)", width=1)),
    ))
    _apply(fig, title)
    fig.update_layout(showlegend=False)
    return fig


# ── Donut chart ───────────────────────────────────────────────────
def donut(df, names, values, title, *, cmap=None):
    colors = [(cmap or {}).get(n, PALETTE[i % len(PALETTE)])
               for i, n in enumerate(df[names])]
    fig = go.Figure(go.Pie(
        labels=df[names], values=df[values], hole=0.58,
        marker=dict(colors=colors, line=dict(color="#09090B", width=2)),
        textinfo="label+percent", textposition="outside",
        textfont=dict(size=12, color="#A1A1AA"),
        hovertemplate="<b>%{label}</b><br>%{value:,}<br>%{percent}<extra></extra>",
        pull=[0.025]*len(df),
    ))
    _apply(fig, title)
    fig.update_layout(showlegend=False)
    return fig


# ── Scatter (auto-sampled) ────────────────────────────────────────
def scatter(df, x, y, color_col, title, *, cmap=None, size_col=None, n=5000):
    if len(df) > n:
        df = df.sample(n, random_state=42)
    kw = dict(opacity=0.50,
              color_discrete_map=cmap, color_discrete_sequence=PALETTE)
    if size_col and size_col in df.columns:
        kw.update(size=size_col, size_max=18)
    fig = px.scatter(df, x=x, y=y, color=color_col, **kw)
    fig.update_traces(
        marker=dict(line=dict(width=0.4, color="#09090B")),
        hovertemplate=f"<b>{x}</b>: %{{x:,.2f}}<br><b>{y}</b>: %{{y:,.2f}}<extra></extra>",
    )
    _apply(fig, title)
    return fig


# ── Histogram ────────────────────────────────────────────────────
def hist(df, x, title, *, bins=40, color="#7C3AED"):
    fig = px.histogram(df, x=x, nbins=bins, color_discrete_sequence=[color])
    fig.update_traces(marker_line_width=0, opacity=0.85,
                      hovertemplate="%{x:.2f}  Count: %{y:,}<extra></extra>")
    _apply(fig, title)
    return fig


# ── Box plot ──────────────────────────────────────────────────────
def box(df, x, y, title, *, cmap=None):
    if cmap:
        fig = px.box(df, x=x, y=y, color=x,
                     color_discrete_map=cmap, color_discrete_sequence=PALETTE)
    else:
        fig = px.box(df, x=x, y=y, color_discrete_sequence=["#7C3AED"])
    fig.update_traces(marker=dict(opacity=0.4, size=3))
    _apply(fig, title)
    return fig


# ── Line chart ───────────────────────────────────────────────────
def line(df, x, y, title, *, color_col=None, cmap=None):
    kw = dict(markers=True,
              color_discrete_map=cmap, color_discrete_sequence=PALETTE)
    if color_col and color_col in df.columns:
        fig = px.line(df, x=x, y=y, color=color_col, **kw)
    else:
        fig = px.line(df, x=x, y=y, markers=True,
                      color_discrete_sequence=["#7C3AED"])
    fig.update_traces(
        line=dict(width=2.5),
        marker=dict(size=8, line=dict(width=1.5, color="#09090B")),
        hovertemplate="<b>%{x}</b> · %{y:.2f}<extra></extra>",
    )
    _apply(fig, title)
    return fig


# ── Gauge ────────────────────────────────────────────────────────
def gauge(value, label, *, max_val=100, suffix="%",
          lo=33, hi=66, c_lo="#10B981", c_mid="#F59E0B", c_hi="#F43F5E"):
    def rgba(h, a=0.20):
        r, g, b = (int(h.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        return f"rgba({r},{g},{b},{a})"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number=dict(suffix=suffix, font=dict(size=32, color="#E4E4E7")),
        gauge=dict(
            axis=dict(range=[0, max_val], tickcolor="#52525B",
                      tickfont=dict(color="#52525B", size=10)),
            bar=dict(color="#7C3AED", thickness=0.26),
            bgcolor="rgba(0,0,0,0)", borderwidth=0,
            steps=[
                dict(range=[0,     max_val*lo/100], color=rgba(c_lo)),
                dict(range=[max_val*lo/100, max_val*hi/100], color=rgba(c_mid)),
                dict(range=[max_val*hi/100, max_val], color=rgba(c_hi)),
            ],
        ),
        title=dict(text=label, font=dict(size=13, color="#71717A")),
    ))
    _apply(fig)
    fig.update_layout(height=230, margin=dict(l=24, r=24, t=60, b=8))
    return fig


# ── Treemap ──────────────────────────────────────────────────────
def treemap(df, names, values, title, *, cmap=None):
    colors = [(cmap or {}).get(n, PALETTE[i % len(PALETTE)])
               for i, n in enumerate(df[names])]
    fig = go.Figure(go.Treemap(
        labels=df[names], values=df[values],
        parents=[""]*len(df),
        marker=dict(colors=colors, line=dict(width=2, color="#09090B")),
        textinfo="label+value+percent root",
        textfont=dict(size=13),
        hovertemplate="<b>%{label}</b><br>%{value:,}<br>%{percentRoot:.1%}<extra></extra>",
    ))
    _apply(fig, title)
    fig.update_layout(margin=dict(l=8, r=8, t=48, b=8))
    return fig
