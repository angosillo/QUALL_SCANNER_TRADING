"""
Watchlist manager — CRUD operations for persistent watchlists in SQLite.
"""

import logging
from datetime import datetime

import pandas as pd

from ..data.ingest import get_connection

logger = logging.getLogger(__name__)


def create_watchlist(
    db_path: str,
    name: str,
    description: str = "",
    auto_populate_scan: str | None = None,
) -> int:
    """Create a watchlist. Returns its ID. Raises ValueError if name exists."""
    conn = get_connection(db_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor = conn.execute(
            """
            INSERT INTO watchlists (name, description, auto_populate_scan, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, description, auto_populate_scan, now, now),
        )
        conn.commit()
        watchlist_id = cursor.lastrowid
        logger.info(f"Created watchlist '{name}' (id={watchlist_id})")
        return watchlist_id
    except Exception as exc:
        logger.error(f"Failed to create watchlist '{name}': {exc}")
        raise ValueError(f"Watchlist '{name}' already exists or invalid") from exc
    finally:
        conn.close()


def list_watchlists(db_path: str) -> pd.DataFrame:
    """List watchlists with item count."""
    conn = get_connection(db_path)
    query = """
        SELECT
            w.id,
            w.name,
            w.description,
            w.auto_populate_scan,
            w.created_at,
            COUNT(wi.symbol) AS item_count
        FROM watchlists w
        LEFT JOIN watchlist_items wi ON w.id = wi.watchlist_id
        GROUP BY w.id
        ORDER BY w.created_at DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


def delete_watchlist(db_path: str, watchlist_id: int) -> None:
    """Delete a watchlist and its items (cascade)."""
    conn = get_connection(db_path)
    try:
        conn.execute("DELETE FROM watchlist_items WHERE watchlist_id = ?", (watchlist_id,))
        cursor = conn.execute("DELETE FROM watchlists WHERE id = ?", (watchlist_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Watchlist {watchlist_id} not found")
        logger.info(f"Deleted watchlist {watchlist_id}")
    finally:
        conn.close()


def rename_watchlist(db_path: str, watchlist_id: int, new_name: str) -> None:
    """Rename a watchlist."""
    conn = get_connection(db_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor = conn.execute(
            "UPDATE watchlists SET name = ?, updated_at = ? WHERE id = ?",
            (new_name, now, watchlist_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Watchlist {watchlist_id} not found")
        logger.info(f"Renamed watchlist {watchlist_id} to '{new_name}'")
    except Exception as exc:
        logger.error(f"Failed to rename watchlist {watchlist_id}: {exc}")
        raise ValueError(f"Name '{new_name}' already exists or invalid") from exc
    finally:
        conn.close()


def add_symbol(
    db_path: str,
    watchlist_id: int,
    symbol: str,
    added_from_scan: str | None = None,
    notes: str = "",
) -> None:
    """Add a symbol to a watchlist. Idempotent (no duplicates)."""
    conn = get_connection(db_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO watchlist_items
            (watchlist_id, symbol, added_at, added_from_scan, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (watchlist_id, symbol, now, added_from_scan, notes),
        )
        conn.commit()
        logger.info(f"Added {symbol} to watchlist {watchlist_id}")
    finally:
        conn.close()


def remove_symbol(db_path: str, watchlist_id: int, symbol: str) -> None:
    """Remove a symbol from a watchlist."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "DELETE FROM watchlist_items WHERE watchlist_id = ? AND symbol = ?",
            (watchlist_id, symbol),
        )
        conn.commit()
        logger.info(f"Removed {symbol} from watchlist {watchlist_id}")
    finally:
        conn.close()


def get_items(db_path: str, watchlist_id: int) -> pd.DataFrame:
    """
    Return watchlist items JOINed with latest indicators.
    Columns: symbol, added_at, added_from_scan, notes, flagged,
             close, volume, adr_pct_20, trend_intensity, composite_score
    """
    conn = get_connection(db_path)
    query = """
        SELECT
            wi.symbol,
            wi.added_at,
            wi.added_from_scan,
            wi.notes,
            wi.flagged,
            i.close,
            i.volume,
            i.adr_pct_20,
            i.trend_intensity,
            i.composite_score
        FROM watchlist_items wi
        LEFT JOIN indicators i ON wi.symbol = i.symbol
        AND i.date = (
            SELECT MAX(date) FROM indicators WHERE symbol = wi.symbol
        )
        WHERE wi.watchlist_id = ?
        ORDER BY wi.added_at DESC
    """
    df = pd.read_sql(query, conn, params=(watchlist_id,))
    conn.close()
    return df


def toggle_flag(db_path: str, watchlist_id: int, symbol: str) -> bool:
    """Toggle the flagged field. Returns the new state."""
    conn = get_connection(db_path)
    try:
        # Get current state
        row = conn.execute(
            "SELECT flagged FROM watchlist_items WHERE watchlist_id = ? AND symbol = ?",
            (watchlist_id, symbol),
        ).fetchone()
        if row is None:
            raise ValueError(f"Symbol {symbol} not in watchlist {watchlist_id}")
        new_state = 0 if row[0] else 1
        conn.execute(
            "UPDATE watchlist_items SET flagged = ? WHERE watchlist_id = ? AND symbol = ?",
            (new_state, watchlist_id, symbol),
        )
        conn.commit()
        logger.info(f"Toggled flag for {symbol} in watchlist {watchlist_id} -> {new_state}")
        return bool(new_state)
    finally:
        conn.close()


def auto_populate(db_path: str, watchlist_id: int) -> int:
    """
    If the watchlist has auto_populate_scan, add all symbols
    from the latest run of that scan. Returns count added.
    """
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT auto_populate_scan FROM watchlists WHERE id = ?",
            (watchlist_id,),
        ).fetchone()
        if row is None or row[0] is None:
            return 0
        scan_id = row[0]

        # Get latest run results for this scan
        symbols_df = pd.read_sql(
            """
            SELECT DISTINCT symbol
            FROM scan_results
            WHERE scan_id = ? AND run_date = (
                SELECT MAX(run_date) FROM scan_results WHERE scan_id = ?
            )
            """,
            conn,
            params=(scan_id, scan_id),
        )
        if symbols_df.empty:
            return 0

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        added = 0
        for symbol in symbols_df["symbol"]:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO watchlist_items
                (watchlist_id, symbol, added_at, added_from_scan)
                VALUES (?, ?, ?, ?)
                """,
                (watchlist_id, symbol, now, scan_id),
            )
            added += cursor.rowcount
        conn.commit()
        logger.info(f"Auto-populated watchlist {watchlist_id} with {added} symbols from {scan_id}")
        return added
    finally:
        conn.close()
