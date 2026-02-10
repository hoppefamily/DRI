"""Command-line interface for DRI."""
import argparse
import logging
import sys
from datetime import datetime

from . import __version__
from .config import Config
from .edgar import EDGARFetcher
from .pipeline import DRIPipeline
from .sensor import ManagerSensor
from .storage import Storage


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_sensor_fetch(args):
    """Fetch 13F filings for a manager."""
    config = Config.from_file(args.config) if args.config else Config.from_default()
    edgar = EDGARFetcher(config.config)
    storage = Storage(config.config)

    print(f"Fetching {args.quarters} quarters of 13F filings for CIK {args.cik}...")

    filings = edgar.fetch_13f_filings(
        cik=args.cik,
        quarters=args.quarters,
    )

    print(f"\nFetched {len(filings)} filings:")
    for filing in filings:
        print(
            f"  {filing.report_date} | "
            f"Filed: {filing.filing_date} | "
            f"Value: ${filing.total_value:,.0f}K | "
            f"Holdings: {filing.holdings_count}"
        )

    # Store filings (as sensor history)
    if args.name:
        sensor = ManagerSensor(config.config)
        sensor_history = sensor.build_sensor_history(
            cik=args.cik,
            name=args.name,
            filings=filings,
            decay_halflife=30,  # Default
        )
        storage.save_sensor_history(sensor_history, args.cik)
        print(f"\nSaved sensor history to {storage.output_dir}")


def cmd_sensor_show(args):
    """Show latest sensor reading for a manager."""
    config = Config.from_file(args.config) if args.config else Config.from_default()
    storage = Storage(config.config)

    sensor_history = storage.load_sensor_history(args.cik)

    if not sensor_history:
        print(f"No sensor data found for CIK {args.cik}")
        return

    latest = sensor_history[-1]

    if args.format == "json":
        import json
        from dataclasses import asdict
        print(json.dumps(asdict(latest), indent=2, default=str))
    else:
        # Table format
        print(f"\nSensor Reading for {latest.name} ({latest.cik})")
        print("=" * 60)
        print(f"Quarter End:        {latest.asof_quarter_end}")
        print(f"Filing Date:        {latest.filing_date}")
        print(f"13F Value:          ${latest.total_13f_value:,.0f}K")
        print(f"Exposure Index:     {latest.exposure_index:.1f}%")
        print(f"Delta:              {latest.delta_exposure:+.1f}%")
        print(f"Days Since:         {latest.days_since_snapshot}")
        print(f"Effective Exposure: {latest.effective_exposure:.3f}")
        print(f"Rolling Max (5y):   ${latest.rolling_max_5y:,.0f}K")


def cmd_run(args):
    """Run full DRI pipeline."""
    config = Config.from_file(args.config) if args.config else Config.from_default()
    pipeline = DRIPipeline(config)

    asof_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else None

    print("Running DRI pipeline...")
    print(f"Panel size: {len(config['panel'])} managers")

    try:
        snapshot = pipeline.run(
            asof_date=asof_date,
            upload_s3=args.s3,
            dry_run=args.dry_run,
        )

        print("\n" + "=" * 60)
        print(f"DRI Snapshot — {snapshot.asof_date}")
        print("=" * 60)
        print(f"Regime:              {snapshot.regime_state}")
        print(f"Median Exposure:     {snapshot.median_effective_exposure:.1%}")
        print(f"Median Delta:        {snapshot.median_delta:+.1%}")
        print(f"Dispersion:          {snapshot.dispersion:.3f}")
        print(f"Dispersion Spread:   {snapshot.dispersion_spread:.3f}")
        print(f"Panel Members:       {len(snapshot.panel_members)}")
        print("=" * 60)

        if args.dry_run:
            print("\n(Dry run — results not saved)")

    except Exception as e:
        print(f"Pipeline failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_show(args):
    """Show latest DRI snapshot."""
    config = Config.from_file(args.config) if args.config else Config.from_default()
    storage = Storage(config.config)

    snapshot = storage.load_dri_snapshot()

    if not snapshot:
        print("No DRI snapshot found. Run 'dri run' first.")
        return

    if args.format == "json":
        import json
        from dataclasses import asdict
        print(json.dumps(asdict(snapshot), indent=2, default=str))
    else:
        # Table format
        print("\n" + "=" * 60)
        print(f"DRI Snapshot — {snapshot.asof_date}")
        print("=" * 60)
        print(f"Regime:              {snapshot.regime_state}")
        print(f"Median Exposure:     {snapshot.median_effective_exposure:.1%}")
        print(f"Median Delta:        {snapshot.median_delta:+.1%}")
        print(f"Dispersion:          {snapshot.dispersion:.3f}")
        print(f"Dispersion Spread:   {snapshot.dispersion_spread:.3f}")
        print(f"Panel Members:       {len(snapshot.panel_members)}")
        print("=" * 60)


def cmd_history(args):
    """Show DRI history."""
    config = Config.from_file(args.config) if args.config else Config.from_default()
    storage = Storage(config.config)

    snapshots = storage.load_dri_history()

    if not snapshots:
        print("No DRI history found.")
        return

    # Filter by since date
    if args.since:
        since_date = datetime.strptime(args.since, "%Y-%m-%d").date()
        snapshots = [s for s in snapshots if s.asof_date >= since_date]

    if args.format == "json":
        import json
        from dataclasses import asdict
        print(json.dumps([asdict(s) for s in snapshots], indent=2, default=str))
    else:
        # Table format
        print(f"\nDRI History ({len(snapshots)} snapshots)")
        print("=" * 100)
        print(f"{'Date':<12} {'Regime':<20} {'Med Exp':<10} {'Delta':<10} {'Dispersion':<12}")
        print("-" * 100)
        for s in snapshots:
            print(
                f"{s.asof_date!s:<12} "
                f"{s.regime_state:<20} "
                f"{s.median_effective_exposure:>8.1%}  "
                f"{s.median_delta:>+8.1%}  "
                f"{s.dispersion:>10.3f}"
            )
        print("=" * 100)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="DRI — Discretionary Risk Index",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"dri {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Sensor commands
    sensor_parser = subparsers.add_parser("sensor", help="Single-manager sensor operations")
    sensor_subparsers = sensor_parser.add_subparsers(dest="sensor_command")

    # sensor fetch
    fetch_parser = sensor_subparsers.add_parser("fetch", help="Fetch 13F filings for a manager")
    fetch_parser.add_argument("cik", help="Manager CIK (10-digit)")
    fetch_parser.add_argument("--quarters", type=int, default=8, help="Number of quarters to fetch")
    fetch_parser.add_argument("--name", help="Manager name (for storage)")
    fetch_parser.add_argument("--config", help="Path to config file")

    # sensor show
    show_sensor_parser = sensor_subparsers.add_parser("show", help="Show latest sensor reading")
    show_sensor_parser.add_argument("cik", help="Manager CIK")
    show_sensor_parser.add_argument("--format", choices=["table", "json"], default="table")
    show_sensor_parser.add_argument("--config", help="Path to config file")

    # run
    run_parser = subparsers.add_parser("run", help="Run full DRI pipeline")
    run_parser.add_argument("--config", help="Path to config file")
    run_parser.add_argument("--date", help="As-of date (YYYY-MM-DD, default: today)")
    run_parser.add_argument("--s3", action="store_true", help="Upload results to S3")
    run_parser.add_argument("--dry-run", action="store_true", help="Validate without saving")

    # show
    show_parser = subparsers.add_parser("show", help="Show latest DRI snapshot")
    show_parser.add_argument("--format", choices=["table", "json"], default="table")
    show_parser.add_argument("--config", help="Path to config file")

    # history
    history_parser = subparsers.add_parser("history", help="Show DRI history")
    history_parser.add_argument("--since", help="Show since date (YYYY-MM-DD)")
    history_parser.add_argument("--format", choices=["table", "json"], default="table")
    history_parser.add_argument("--config", help="Path to config file")

    args = parser.parse_args()

    setup_logging(args.verbose)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to command handlers
    try:
        if args.command == "sensor":
            if args.sensor_command == "fetch":
                cmd_sensor_fetch(args)
            elif args.sensor_command == "show":
                cmd_sensor_show(args)
            else:
                sensor_parser.print_help()
        elif args.command == "run":
            cmd_run(args)
        elif args.command == "show":
            cmd_show(args)
        elif args.command == "history":
            cmd_history(args)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.error(f"Command failed: {e}", exc_info=args.verbose)
        sys.exit(1)


if __name__ == "__main__":
    main()
