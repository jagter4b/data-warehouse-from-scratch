import plotly.express as px
import plotly.graph_objects as go

# Common dark theme layout for all charts
CHART_LAYOUT = dict(
    plot_bgcolor="#1A1D27",
    paper_bgcolor="#0E1117",
    font_color="#FAFAFA",
    margin=dict(l=20, r=20, t=40, b=20)
)
COLORS = ["#00C853", "#29B6F6", "#FFA000", "#EF5350", "#AB47BC"]

def make_donut_chart(df, names_col, values_col, title):
    fig = px.pie(df, names=names_col, values=values_col, hole=0.6, title=title,
                 color_discrete_sequence=COLORS)
    fig.update_layout(**CHART_LAYOUT)
    return fig

def make_bar_chart(df, x_col, y_col, title, barmode='group'):
    fig = px.bar(df, x=x_col, y=y_col, title=title, barmode=barmode,
                 color_discrete_sequence=COLORS)
    fig.update_layout(**CHART_LAYOUT)
    return fig

def make_scatter_plot(df, x_col, y_col, color_col, title, size_col=None):
    if size_col and size_col in df.columns:
        fig = px.scatter(df, x=x_col, y=y_col, color=color_col, size=size_col,
                         title=title, color_discrete_sequence=COLORS)
    else:
        fig = px.scatter(df, x=x_col, y=y_col, color=color_col,
                         title=title, color_discrete_sequence=COLORS)
    fig.update_layout(**CHART_LAYOUT)
    return fig

def make_histogram(df, x_col, title, nbins=30):
    fig = px.histogram(df, x=x_col, nbins=nbins, title=title, 
                       color_discrete_sequence=["#00C853"])
    fig.update_layout(**CHART_LAYOUT)
    return fig

def make_box_plot(df, x_col, y_col, title):
    fig = px.box(df, x=x_col, y=y_col, title=title,
                 color_discrete_sequence=["#00C853"])
    fig.update_layout(**CHART_LAYOUT)
    return fig
