# modules/dashboard.py
import os
import json
import logging
from datetime import datetime
from collections import Counter

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, callback
from sqlalchemy import create_engine, text

DB_PATH = os.getenv("DB_PATH", "/opt/airflow/data/ria_news.db")
engine = create_engine(f"sqlite:///{DB_PATH}")
logger = logging.getLogger(__name__)


def load_events():
    query = text("""
                 SELECT re.id,
                        re.first_seen,
                        re.last_seen,
                        re.total_mentions,
                        re.avg_interval_days,
                        re.dates_json,
                        re.titles_json,
                        na.title as original_title,
                        na.url   as original_url
                 FROM recurrent_events re
                          JOIN news_articles na ON re.original_article_id = na.id
                 ORDER BY re.total_mentions DESC
                 """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    import json
    df['dates_list'] = df['dates_json'].apply(json.loads)
    df['titles_list'] = df['titles_json'].apply(json.loads)

    # Добавляем длительность в днях
    df['duration_days'] = (pd.to_datetime(df['last_seen']) - pd.to_datetime(df['first_seen'])).dt.days

    return df


def create_layout():
    return html.Div([
        html.H1("📊 Анализ рекуррентных новостных событий", style={'textAlign': 'center'}),
        html.Hr(),

        html.Div(id="stats", style={'textAlign': 'center', 'marginBottom': 30}),

        # Выбор события для детального просмотра
        html.Label("🔍 Выберите событие для детального просмотра:"),
        dcc.Dropdown(id="event_selector", style={'marginBottom': 20}),
        dcc.Graph(id="timeline_graph"),

        # Два графика в ряд
        html.Div([
            html.Div([
                html.H3("📈 Распределение событий по количеству упоминаний"),
                dcc.Graph(id="histogram")
            ], style={'width': '48%', 'display': 'inline-block'}),
            html.Div([
                html.H3("⏱️ Длительность событий (дни)"),
                dcc.Graph(id="duration_histogram")
            ], style={'width': '48%', 'display': 'inline-block', 'float': 'right'})
        ]),

        # Топ-10 событий в виде горизонтальной гистограммы
        html.H3("🏆 Топ-10 событий по количеству упоминаний"),
        dcc.Graph(id="top_events_chart"),

        # Таблица топ-событий
        html.H3("📋 Детальная таблица топ-10 событий"),
        html.Div(id="top_events_table"),

        dcc.Interval(id="interval", interval=60 * 1000)
    ])


@callback(
    Output("stats", "children"),
    Output("event_selector", "options"),
    Output("event_selector", "value"),
    Input("interval", "n_intervals")
)
def update_global_stats(_):
    df = load_events()
    if df.empty:
        return html.Div("Нет данных. Запустите пайплайн."), [], None

    total_events = len(df)
    total_mentions = df['total_mentions'].sum()
    avg_mentions = df['total_mentions'].mean()
    max_mentions = df['total_mentions'].max()
    max_event_title = df[df['total_mentions'] == max_mentions]['original_title'].values[0][:60]

    stats = html.Div([
        html.Div(f"📌 Всего событий: {total_events}", style={'display': 'inline-block', 'marginRight': 30}),
        html.Div(f"🔁 Всего упоминаний: {total_mentions}", style={'display': 'inline-block', 'marginRight': 30}),
        html.Div(f"📊 В среднем: {avg_mentions:.1f} упоминаний", style={'display': 'inline-block', 'marginRight': 30}),
        html.Div(f"🏆 Самое частотное: {max_mentions} упоминаний ({max_event_title}...)",
                 style={'display': 'inline-block'}),
    ])

    options = [{"label": f"{row['original_title'][:80]}... ({row['total_mentions']} упоминаний)", "value": idx}
               for idx, row in df.iterrows()]
    default_value = options[0]['value'] if options else None
    return stats, options, default_value


@callback(
    Output("timeline_graph", "figure"),
    Input("event_selector", "value"),
    Input("interval", "n_intervals")
)
def update_timeline(selected_idx, _):
    if selected_idx is None:
        return go.Figure()
    df = load_events()
    if df.empty or selected_idx >= len(df):
        return go.Figure()
    row = df.iloc[selected_idx]

    dates = [datetime.strptime(d, "%Y-%m-%d") for d in row['dates_list']]
    titles = row['titles_list']

    # Создаём точки для графика
    fig = go.Figure()

    # Добавляем точки
    fig.add_trace(go.Scatter(
        x=dates,
        y=list(range(1, len(dates) + 1)),
        mode='markers+lines',
        name='Упоминания',
        marker=dict(size=12, color='#1f77b4', line=dict(width=2, color='DarkSlateGrey')),
        line=dict(width=2, color='#1f77b4'),
        text=[f"{t}<br>{d.strftime('%d.%m.%Y')}" for t, d in zip(titles, dates)],
        hovertemplate='%{text}<extra></extra>'
    ))

    fig.update_layout(
        title=f"<b>{row['original_title']}</b><br>"
              f"📅 Период: {row['first_seen']} — {row['last_seen']} | "
              f"📊 Всего упоминаний: {row['total_mentions']} | "
              f"⏱️ Средний интервал: {row['avg_interval_days']:.1f} дней",
        xaxis_title="Дата",
        yaxis_title="Порядок упоминания",
        height=450,
        xaxis=dict(tickformat="%d.%m.%Y", tickangle=-45),
        yaxis=dict(tickmode='linear', dtick=1, autorange=True),
        hoverlabel=dict(bgcolor="white", font_size=12)
    )

    return fig


@callback(
    Output("histogram", "figure"),
    Input("interval", "n_intervals")
)
def update_histogram(_):
    df = load_events()
    if df.empty:
        return go.Figure()

    fig = px.histogram(
        df, x='total_mentions', nbins=30,
        title="Распределение событий по количеству упоминаний",
        labels={'total_mentions': 'Количество упоминаний', 'count': 'Количество событий'},
        color_discrete_sequence=['#1f77b4'],
        marginal='box'
    )
    fig.update_layout(height=400)
    return fig


@callback(
    Output("duration_histogram", "figure"),
    Input("interval", "n_intervals")
)
def update_duration_histogram(_):
    df = load_events()
    if df.empty:
        return go.Figure()

    # Берём только события длительностью до 30 дней (для читаемости)
    df_duration = df[df['duration_days'] <= 30].copy()

    if df_duration.empty:
        df_duration = df.copy()

    fig = px.histogram(
        df_duration,
        x='duration_days',
        nbins=15,
        title="⏱️ Длительность событий (дни)",
        labels={'duration_days': 'Длительность (дни)', 'count': 'Количество событий'},
        color_discrete_sequence=['#ff7f0e']
    )

    fig.update_layout(
        height=400,
        xaxis_title="Длительность (дни)",
        yaxis_title="Количество событий",
        bargap=0.05
    )

    return fig


@callback(
    Output("top_events_chart", "figure"),
    Input("interval", "n_intervals")
)
def update_top_events_chart(_):
    df = load_events().head(10)
    if df.empty:
        return go.Figure()

    fig = px.bar(
        df,
        x='total_mentions',
        y='original_title',
        orientation='h',
        title="Топ-10 событий по количеству упоминаний",
        labels={'total_mentions': 'Количество упоминаний', 'original_title': 'Событие'},
        color='total_mentions',
        color_continuous_scale='Viridis',
        text='total_mentions'
    )
    fig.update_traces(textposition='outside')
    fig.update_layout(
        height=500,
        yaxis={'categoryorder': 'total ascending'},
        xaxis_title="Количество упоминаний",
        yaxis_title=""
    )
    return fig


@callback(
    Output("top_events_table", "children"),
    Input("interval", "n_intervals")
)
def top_table(_):
    df = load_events().head(10)
    if df.empty:
        return html.Div("Нет данных")

    table = html.Table([
        html.Thead(html.Tr([
            html.Th("№"), html.Th("Событие"), html.Th("Упоминаний"),
            html.Th("Период"), html.Th("Средний интервал (дни)")
        ])),
        html.Tbody([
            html.Tr([
                html.Td(str(i + 1)),
                html.Td(row['original_title'][:80] + ("..." if len(row['original_title']) > 80 else "")),
                html.Td(row['total_mentions']),
                html.Td(f"{row['first_seen']} — {row['last_seen']}"),
                html.Td(f"{row['avg_interval_days']:.1f}")
            ]) for i, (_, row) in enumerate(df.iterrows())
        ])
    ], style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '14px'})

    return table


def run_dashboard():
    app = Dash(__name__)
    app.layout = create_layout()
    app.run(host='0.0.0.0', port=8050, debug=False)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_dashboard()