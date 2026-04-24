"""
Chart rendering — ASCII candles, mplfinance PNG, Plotly HTML.
"""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def render_ascii_candles(
    df: pd.DataFrame,
    symbol: str,
    days: int = 60,
    width: int = 80,
    height: int = 20,
) -> str:
    """
    Generate an ASCII candlestick chart for rendering inside Textual.
    Returns a multi-line string.
    """
    if df.empty:
        return f"No data for {symbol}"

    # Ensure expected columns
    cols = {"date", "open", "high", "low", "close"}
    if not cols.issubset(df.columns):
        return f"Missing required columns for {symbol}"

    df = df.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
    df = df.tail(days)

    if df.empty:
        return f"No data for {symbol}"

    min_price = df["low"].min()
    max_price = df["high"].max()
    if min_price == max_price:
        return f"Flat price for {symbol}: {min_price:.2f}"

    price_range = max_price - min_price
    rows = []

    # Header
    rows.append(f"{symbol} — last {len(df)} sessions")
    rows.append(f"Range: {min_price:.2f} - {max_price:.2f}")
    rows.append("")

    # Build grid
    grid = [[" " for _ in range(width)] for _ in range(height)]
    n_bars = min(len(df), width // 2)
    step = max(1, len(df) // n_bars) if len(df) > n_bars else 1

    for idx in range(n_bars):
        data_idx = idx * step
        if data_idx >= len(df):
            break
        row = df.iloc[data_idx]
        o, h, lo, c = row["open"], row["high"], row["low"], row["close"]

        top = max(o, c)
        bottom = min(o, c)

        y_high = int((h - min_price) / price_range * (height - 1))
        y_low = int((lo - min_price) / price_range * (height - 1))
        y_top = int((top - min_price) / price_range * (height - 1))
        y_bottom = int((bottom - min_price) / price_range * (height - 1))

        col = idx * 2
        if col >= width:
            break

        char_body = "█" if c >= o else "░"
        char_wick = "│"

        for y in range(y_low, y_high + 1):
            if y_bottom <= y <= y_top:
                grid[height - 1 - y][col] = char_body
            else:
                grid[height - 1 - y][col] = char_wick

    for line in grid:
        rows.append("".join(line))

    return "\n".join(rows)


def save_mpl_chart(
    df: pd.DataFrame,
    symbol: str,
    output_path: str,
    days: int = 120,
    show_volume: bool = True,
    show_sma: list[int] | None = None,
) -> str:
    """
    Generate a PNG candlestick chart with mplfinance.
    Returns the path of the generated file.
    """
    try:
        import mplfinance as mpf
    except ImportError:
        logger.error("mplfinance not installed")
        raise

    if df.empty:
        raise ValueError(f"No data for {symbol}")

    df = df.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)

    # Ensure required columns
    for col in ["open", "high", "low", "close", "volume"]:
        if col not in df.columns:
            raise ValueError(f"Missing column {col}")

    df = df.tail(days)

    # Calculate SMAs
    addplot = []
    if show_sma:
        for period in show_sma:
            col_name = f"SMA{period}"
            df[col_name] = df["close"].rolling(window=period).mean()
            addplot.append(mpf.make_addplot(df[col_name]))

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    kwargs = {
        "type": "candle",
        "style": "charles",
        "title": f"{symbol}",
        "ylabel": "Price",
        "savefig": str(out),
        "addplot": addplot if addplot else None,
    }

    if show_volume:
        kwargs["volume"] = True
        kwargs["ylabel_lower"] = "Volume"

    mpf.plot(df, **kwargs)
    logger.info(f"Saved mplfinance chart: {out}")
    return str(out)


def save_plotly_chart(
    df: pd.DataFrame,
    symbol: str,
    output_path: str,
    days: int = 120,
) -> str:
    """
    Generate an interactive HTML candlestick chart with Plotly.
    Returns the path of the generated file.
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        logger.error("plotly not installed")
        raise

    if df.empty:
        raise ValueError(f"No data for {symbol}")

    df = df.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])

    df = df.tail(days)

    fig = go.Figure(
        data=[
            go.Candlestick(
                x=df["date"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name=symbol,
            )
        ]
    )

    fig.update_layout(
        title=f"{symbol}",
        xaxis_title="Date",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out))
    logger.info(f"Saved plotly chart: {out}")
    return str(out)


def build_plotly_figure(
    df: pd.DataFrame,
    symbol: str,
    days: int = 120,
    show_sma: list[int] | None = None,
    show_volume: bool = True,
) -> dict:
    """
    Retorna el dict JSON de una figura Plotly para embeber en HTML
    via <div id="chart"></div> + Plotly.newPlot().

    Args:
        df: DataFrame con columnas date, open, high, low, close, volume
        symbol: ticker a graficar
        days: número de sesiones a mostrar
        show_sma: periodos de SMA a overlayear (ej [20, 50])
        show_volume: si incluir panel de volumen

    Returns:
        dict con keys "data" y "layout" (formato Plotly JSON)
    """
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        logger.error("plotly not installed")
        raise

    if df.empty:
        raise ValueError(f"No data for {symbol}")

    df = df.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])

    df = df.tail(days)

    if show_volume and "volume" in df.columns:
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.75, 0.25],
        )
    else:
        fig = go.Figure()

    # Candlestick trace
    candle = go.Candlestick(
        x=df["date"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name=symbol,
    )

    if show_volume and "volume" in df.columns:
        fig.add_trace(candle, row=1, col=1)
    else:
        fig.add_trace(candle)

    # SMA overlays
    if show_sma:
        for period in show_sma:
            col_name = f"SMA{period}"
            df[col_name] = df["close"].rolling(window=period).mean()
            sma_trace = go.Scatter(
                x=df["date"],
                y=df[col_name],
                mode="lines",
                name=f"SMA {period}",
                line={"width": 1},
            )
            if show_volume and "volume" in df.columns:
                fig.add_trace(sma_trace, row=1, col=1)
            else:
                fig.add_trace(sma_trace)

    # Volume bars
    if show_volume and "volume" in df.columns:
        colors = ["#3fb950" if c >= o else "#f85149" for c, o in zip(df["close"], df["open"])]
        vol_trace = go.Bar(
            x=df["date"],
            y=df["volume"],
            marker_color=colors,
            name="Volume",
            showlegend=False,
        )
        fig.add_trace(vol_trace, row=2, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)

    fig.update_layout(
        title=f"{symbol}",
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=50, t=60, b=40),
        paper_bgcolor="#0d1117",
        plot_bgcolor="#161b22",
    )

    fig.update_xaxes(title_text="Date", row=1 if (show_volume and "volume" in df.columns) else 1, col=1)
    fig.update_yaxes(title_text="Price", row=1, col=1)

    import json
    return json.loads(fig.to_json())
