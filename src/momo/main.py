"""
MOMO Scanner — CLI entry point.

Usage:
    python -m momo init                  # Initialize DB
    python -m momo universe              # Fetch ticker universe
    python -m momo download [--full]     # Download/update OHLCV
    python -m momo scan [--all | --scan ID]  # Run scans
    python -m momo full                  # Full pipeline: universe + download + scan
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


def setup_logging(level: str = "INFO"):
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def get_db_path() -> str:
    """Get database path from config or default."""
    config_path = Path("config/settings.toml")
    if config_path.exists():
        import tomli
        with open(config_path, "rb") as f:
            config = tomli.load(f)
        return config.get("general", {}).get("db_path", "data/momo.db")
    return "data/momo.db"


def cmd_init(args):
    """Initialize database."""
    from momo.data.ingest import init_db
    db_path = get_db_path()
    conn = init_db(db_path)
    conn.close()
    print(f"✅ Database initialized: {db_path}")


def cmd_universe(args):
    """Fetch and classify ticker universe."""
    from momo.data.ingest import update_universe
    db_path = get_db_path()
    cache_path = args.cache or "data/universe.parquet"
    df = update_universe(db_path, cache_path=cache_path)
    print(f"✅ Universe updated: {len(df)} tickers")
    print(f"   Exchanges: {df['exchange'].value_counts().to_dict()}")


def cmd_download(args):
    """Download/update OHLCV data."""
    from momo.data.ingest import update_ohlcv, get_universe_symbols, init_db
    db_path = get_db_path()

    # Ensure DB exists
    conn = init_db(db_path)
    conn.close()

    symbols = get_universe_symbols(db_path)
    if not symbols:
        print("⚠️  No tickers in universe. Run 'python -m momo universe' first.")
        return

    if args.limit:
        symbols = symbols[:args.limit]
        print(f"   Limited to {args.limit} tickers")

    print(f"📥 Downloading OHLCV for {len(symbols)} tickers...")
    if args.full:
        print("   (Full download — this may take 30-60 minutes)")
    else:
        print("   (Incremental update — ~5 minutes)")

    # Force full download if no data exists yet
    import sqlite3
    conn = sqlite3.connect(db_path)
    existing_count = pd.read_sql("SELECT COUNT(*) as c FROM daily_prices", conn)["c"].iloc[0]
    conn.close()
    force_full = args.full or (existing_count == 0)

    if force_full and not args.full:
        print("   (No existing data — running full download)")

    count = update_ohlcv(db_path, symbols, full=force_full)
    print(f"✅ Downloaded: {count}/{len(symbols)} tickers")


def cmd_scan(args):
    """Run scans."""
    from momo.scanner.engine import run_all_scans, build_indicator_table, format_results_table
    from momo.scanner.loader import load_all_scans
    from momo.alerts.telegram_alerts import send_nightly_report

    db_path = get_db_path()
    config_dir = args.config_dir or "config/scans"

    print("🔍 Building indicator table...")
    indicator_table = build_indicator_table(db_path)

    if indicator_table.empty:
        print("❌ No data. Run 'python -m momo download' first.")
        return

    print(f"   {len(indicator_table)} symbols with indicators")

    if args.scan_id:
        # Run single scan
        scans = load_all_scans(config_dir)
        target = [s for s in scans if s["scan"]["id"] == args.scan_id]
        if not target:
            print(f"❌ Scan '{args.scan_id}' not found")
            return

        from momo.scanner.engine import run_scan
        results = run_scan(target[0], indicator_table, db_path)
        if not results.empty:
            print(f"\n{'='*60}")
            print(f"  {target[0]['scan']['name']} — {len(results)} results")
            print(f"{'='*60}")
            print(format_results_table(results, target[0], max_rows=args.limit or 30))
        else:
            print(f"   0 results for scan '{args.scan_id}'")
    else:
        # Run all enabled scans
        all_results = run_all_scans(db_path, config_dir, indicator_table)

        print(f"\n{'='*60}")
        print(f"  SCAN RESULTS — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*60}")

        for scan_id, results in all_results.items():
            scans = load_all_scans(config_dir)
            scan_config = next((s for s in scans if s["scan"]["id"] == scan_id), None)
            if scan_config:
                print(f"\n--- {scan_config['scan']['name']} ({len(results)} results) ---")
                print(format_results_table(results, scan_config, max_rows=args.limit or 20))

        # Export CSV
        if args.export:
            export_dir = Path("data/exports")
            export_dir.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now().strftime("%Y%m%d")
            for scan_id, results in all_results.items():
                csv_path = export_dir / f"{date_str}_{scan_id}.csv"
                results.to_csv(csv_path, index=False)
                print(f"   📄 Exported: {csv_path}")

        # Send Telegram
        if args.telegram:
            send_nightly_report(all_results, db_path)


def cmd_full(args):
    """Full pipeline: init + universe + download + scan."""
    print("=" * 60)
    print("  MOMO Scanner — Full Pipeline")
    print("=" * 60)

    # Step 1: Init
    print("\n[1/4] Initializing database...")
    cmd_init(args)

    # Step 2: Universe
    print("\n[2/4] Fetching universe...")
    cmd_universe(args)

    # Step 3: Download
    print("\n[3/4] Downloading OHLCV data...")
    args.full = True
    args.limit = getattr(args, "limit", None)
    cmd_download(args)

    # Step 4: Scan
    print("\n[4/4] Running scans...")
    args.scan_id = None
    args.export = True
    cmd_scan(args)

    print("\n" + "=" * 60)
    print("  ✅ Pipeline complete!")
    print("=" * 60)


def cmd_tui(args):
    """Launch the Textual TUI."""
    from momo.ui.app import MomoApp
    db_path = get_db_path()
    app = MomoApp(db_path=db_path)
    app.run()


def cmd_watchlist(args):
    """Watchlist management CLI."""
    from momo.watchlist import manager as wl
    db_path = get_db_path()
    action = args.wl_action

    if action == "list":
        df = wl.list_watchlists(db_path)
        if df.empty:
            print("No watchlists found.")
        else:
            print(df.to_string(index=False))
    elif action == "create":
        name = args.name
        desc = getattr(args, "description", "")
        try:
            wl_id = wl.create_watchlist(db_path, name, desc)
            print(f"✅ Created watchlist '{name}' (id={wl_id})")
        except ValueError as exc:
            print(f"❌ {exc}")
    elif action == "delete":
        try:
            wl.delete_watchlist(db_path, args.watchlist_id)
            print(f"✅ Deleted watchlist {args.watchlist_id}")
        except ValueError as exc:
            print(f"❌ {exc}")
    elif action == "add":
        # Resolve watchlist by name or id
        wls = wl.list_watchlists(db_path)
        target = wls[wls["name"] == args.name]
        if target.empty:
            print(f"❌ Watchlist '{args.name}' not found")
            return
        wl_id = int(target.iloc[0]["id"])
        wl.add_symbol(db_path, wl_id, args.symbol, notes=getattr(args, "notes", ""))
        print(f"✅ Added {args.symbol} to '{args.name}'")
    elif action == "remove":
        wls = wl.list_watchlists(db_path)
        target = wls[wls["name"] == args.name]
        if target.empty:
            print(f"❌ Watchlist '{args.name}' not found")
            return
        wl_id = int(target.iloc[0]["id"])
        wl.remove_symbol(db_path, wl_id, args.symbol)
        print(f"✅ Removed {args.symbol} from '{args.name}'")
    elif action == "show":
        wls = wl.list_watchlists(db_path)
        target = wls[wls["name"] == args.name]
        if target.empty:
            print(f"❌ Watchlist '{args.name}' not found")
            return
        wl_id = int(target.iloc[0]["id"])
        items = wl.get_items(db_path, wl_id)
        print(f"\nWatchlist: {args.name}")
        print(f"Items: {len(items)}\n")
        if not items.empty:
            print(items.to_string(index=False))


def cli():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="momo",
        description="MOMO Scanner — Momentum stock scanner inspired by Qullamaggie",
    )
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init
    subparsers.add_parser("init", help="Initialize database")

    # universe
    p_universe = subparsers.add_parser("universe", help="Fetch ticker universe")
    p_universe.add_argument("--cache", default="data/universe.parquet", help="Cache file path")

    # download
    p_download = subparsers.add_parser("download", help="Download OHLCV data")
    p_download.add_argument("--full", action="store_true", help="Full download (ignore cache)")
    p_download.add_argument("--limit", type=int, help="Limit to N tickers (for testing)")

    # scan
    p_scan = subparsers.add_parser("scan", help="Run scans")
    p_scan.add_argument("--scan", dest="scan_id", help="Run specific scan by ID")
    p_scan.add_argument("--config-dir", default="config/scans", help="Scan configs directory")
    p_scan.add_argument("--limit", type=int, default=20, help="Max rows to display")
    p_scan.add_argument("--export", action="store_true", help="Export results to CSV")
    p_scan.add_argument("--telegram", action="store_true", help="Send results via Telegram")

    # full
    p_full = subparsers.add_parser("full", help="Full pipeline: init + universe + download + scan")
    p_full.add_argument("--limit", type=int, help="Limit to N tickers (for testing)")

    # tui
    subparsers.add_parser("tui", help="Launch interactive TUI dashboard")

    # watchlist
    p_watchlist = subparsers.add_parser("watchlist", help="Manage watchlists")
    wl_sub = p_watchlist.add_subparsers(dest="wl_action", help="Watchlist actions")

    wl_sub.add_parser("list", help="List watchlists")

    wl_create = wl_sub.add_parser("create", help="Create a watchlist")
    wl_create.add_argument("name", help="Watchlist name")
    wl_create.add_argument("--description", default="", help="Description")

    wl_delete = wl_sub.add_parser("delete", help="Delete a watchlist")
    wl_delete.add_argument("watchlist_id", type=int, help="Watchlist ID")

    wl_add = wl_sub.add_parser("add", help="Add symbol to watchlist")
    wl_add.add_argument("name", help="Watchlist name")
    wl_add.add_argument("symbol", help="Ticker symbol")
    wl_add.add_argument("--notes", default="", help="Notes")

    wl_remove = wl_sub.add_parser("remove", help="Remove symbol from watchlist")
    wl_remove.add_argument("name", help="Watchlist name")
    wl_remove.add_argument("symbol", help="Ticker symbol")

    wl_show = wl_sub.add_parser("show", help="Show watchlist contents")
    wl_show.add_argument("name", help="Watchlist name")

    args = parser.parse_args()
    setup_logging(args.log_level)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "init": cmd_init,
        "universe": cmd_universe,
        "download": cmd_download,
        "scan": cmd_scan,
        "full": cmd_full,
        "tui": cmd_tui,
        "watchlist": cmd_watchlist,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    cli()
