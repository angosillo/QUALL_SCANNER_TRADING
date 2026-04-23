"""
Telegram alert system — sends scan results and intraday alerts.
"""

import logging
import os

import pandas as pd

logger = logging.getLogger(__name__)


def get_telegram_config() -> tuple[str, str]:
    """Get Telegram token and chat ID from env vars."""
    token = os.environ.get("MOMO_TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("MOMO_TELEGRAM_CHAT_ID", "")
    return token, chat_id


def format_nightly_report(all_results: dict[str, "pd.DataFrame"], run_date: str) -> str:
    """
    Format a nightly summary message for Telegram.

    Args:
        all_results: {scan_id: DataFrame} from run_all_scans()
        run_date: Date string for the report

    Returns:
        Formatted message string
    """
    import pandas as pd

    lines = [f"📊 MOMO Scanner — Nightly Report ({run_date})", ""]

    scan_labels = {
        "one_month_gainers": ("🔥 Top Momentum (1M Gainers)", "price_growth_1m"),
        "high_trending": ("📈 High Trending (TI > 108)", "trend_intensity"),
        "friday_gainers": ("⚡ Short Candidates (5-Day Gainers)", "price_growth_5d"),
        "one_year_losers": ("📉 1-Year Losers", "price_growth_1y"),
        "two_year_losers": ("📉 2-Year Losers", "price_growth_2y"),
        "adr_stocks": ("🌍 ADR Stocks", "adr_pct_20"),
        "recent_ipos": ("🆕 Recent IPOs", "composite_score"),
        "five_day_losers": ("📊 5-Day Losers", "price_growth_5d"),
    }

    for scan_id, results in all_results.items():
        if results.empty:
            continue

        label, sort_col = scan_labels.get(scan_id, (f"📋 {scan_id}", "composite_score"))
        lines.append(label)
        lines.append(f"   {len(results)} stocks found")

        # Show top 5
        top = results.head(5)
        for i, (_, row) in enumerate(top.iterrows(), 1):
            symbol = row.get("symbol", "?")
            score = row.get("composite_score", "")
            score_str = f" | Score: {score:.0f}" if pd.notna(score) else ""

            # Show the key metric
            if sort_col in row and pd.notna(row[sort_col]):
                val = row[sort_col]
                if "growth" in sort_col or "pct" in sort_col:
                    metric_str = f" | {val:+.1f}%"
                elif "trend" in sort_col:
                    metric_str = f" | TI: {val:.1f}"
                else:
                    metric_str = f" | {val:.2f}"
            else:
                metric_str = ""

            adr_str = ""
            if "adr_pct_20" in row and pd.notna(row["adr_pct_20"]):
                adr_str = f" | ADR: {row['adr_pct_20']:.1f}%"

            lines.append(f"   {i}. {symbol}{metric_str}{adr_str}{score_str}")

        lines.append("")

    if len(all_results) == 0:
        lines.append("⚠️ No scan results. Check data freshness.")

    return "\n".join(lines)


async def send_telegram_message(token: str, chat_id: str, message: str) -> bool:
    """Send a message via Telegram Bot API."""
    try:
        from telegram import Bot
        bot = Bot(token=token)
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=None,  # Plain text
        )
        logger.info(f"Telegram message sent to {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


def send_telegram_sync(token: str, chat_id: str, message: str) -> bool:
    """Synchronous wrapper for sending Telegram messages."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in async context, use nest_asyncio or run in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(
                    lambda: asyncio.run(send_telegram_message(token, chat_id, message))
                ).result()
        else:
            return asyncio.run(send_telegram_message(token, chat_id, message))
    except Exception as e:
        logger.error(f"Telegram sync send failed: {e}")
        return False


def send_nightly_report(all_results: dict, db_path: str) -> bool:
    """Send the nightly scan report via Telegram."""
    token, chat_id = get_telegram_config()
    if not token or not chat_id:
        logger.warning("Telegram not configured — skipping notification")
        return False

    from datetime import datetime
    run_date = datetime.now().strftime("%Y-%m-%d")
    message = format_nightly_report(all_results, run_date)

    # Telegram has a 4096 char limit
    if len(message) > 4000:
        message = message[:3900] + "\n\n... (truncated — full results in CSV)"

    return send_telegram_sync(token, chat_id, message)
