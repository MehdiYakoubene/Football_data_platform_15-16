from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from scripts.build_dataset import DEFAULT_PRESET, PIPELINE_PRESETS, build_dataset
from src.utils.data_access import duckdb_ready, load_manifest
from src.utils.logging import configure_project_logging


PROJECT_ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = PROJECT_ROOT / "data" / "analytics" / "build_manifest.json"
DUCKDB_PATH = PROJECT_ROOT / "data" / "analytics" / "football_analytics.duckdb"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Modern Football Data Platform command line interface.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pipeline = subparsers.add_parser("pipeline", help="Build analytics datasets from StatsBomb Open Data.")
    pipeline.add_argument("--stage", choices=["all", "status"], default="all", help="Pipeline stage to run. Default: all.")
    pipeline.add_argument("--competition-id", type=int, default=None, help="StatsBomb competition_id to ingest.")
    pipeline.add_argument("--season-id", type=int, default=None, help="StatsBomb season_id to ingest.")
    pipeline.add_argument("--preset", choices=sorted(PIPELINE_PRESETS), default=DEFAULT_PRESET, help="Named dataset scope to ingest.")
    pipeline.add_argument("--competition-limit", type=int, default=None, help="Limit competition-season rows. Default: all.")
    pipeline.add_argument("--max-matches", type=int, default=0, help="Maximum matches per competition-season. Default 0 means all.")
    pipeline.add_argument("--demo", action="store_true", help="Fast demo build: first competition-season and 8 matches.")
    pipeline.add_argument("--refresh", action="store_true", help="Re-download JSON files even when cache exists.")
    pipeline.add_argument("--workers", type=int, default=8, help="Parallel workers for match event/lineup ingestion.")
    pipeline.add_argument("--if-needed", action="store_true", help="Skip the build when DuckDB and the build manifest already exist.")
    pipeline.add_argument("--quiet", action="store_true", help="Do not print build logs in the terminal.")
    pipeline.add_argument("--log-file", default=None, help="Write build logs to this file, for example logs/build_dataset.log.")

    app = subparsers.add_parser("app", help="Launch the Streamlit application.")
    app.add_argument("--debug", action="store_true", help="Run Streamlit with debug logs.")
    app.add_argument("--port", type=int, default=None, help="Optional Streamlit server port.")
    app.add_argument("--headless", action="store_true", help="Run Streamlit in headless mode.")

    return parser.parse_args()


def run_pipeline(args: argparse.Namespace) -> None:
    if args.stage == "status":
        print_dataset_status()
        return

    if args.demo:
        args.competition_limit = 1
        args.max_matches = 8

    if args.if_needed and dataset_ready_for_request(args):
        print("Dataset already ready. Skipping rebuild.")
        print_dataset_status()
        return

    configure_project_logging(quiet=args.quiet, log_file=args.log_file)
    build_dataset(args)


def dataset_ready() -> bool:
    return duckdb_ready() and MANIFEST_PATH.exists()


def dataset_ready_for_request(args: argparse.Namespace) -> bool:
    if not dataset_ready():
        return False
    manifest = load_manifest()
    manifest_args = manifest.get("args", {})
    if not isinstance(manifest_args, dict):
        return False

    requested_keys = ("preset", "competition_id", "season_id", "competition_limit", "max_matches", "demo")
    for key in requested_keys:
        if getattr(args, key, None) != manifest_args.get(key):
            return False
    return True


def print_dataset_status() -> None:
    manifest = load_manifest()
    ready = dataset_ready()
    print("Modern Football Data Platform - dataset status")
    print(f"Ready: {'yes' if ready else 'no'}")
    print(f"DuckDB: {DUCKDB_PATH if DUCKDB_PATH.exists() else 'missing'}")
    print(f"Manifest: {MANIFEST_PATH if MANIFEST_PATH.exists() else 'missing'}")

    if not manifest:
        print("Run: python main.py pipeline --stage all")
        return

    print(f"Build mode: {manifest.get('build_mode', 'n/a')}")
    manifest_args = manifest.get("args", {})
    if isinstance(manifest_args, dict):
        print(f"Preset: {manifest_args.get('preset', 'n/a')}")
    print(f"Schema version: {manifest.get('schema_version', 'n/a')}")
    print(f"Completed at UTC: {manifest.get('completed_at_utc', 'n/a')}")
    print(f"Duration seconds: {manifest.get('duration_seconds', 'n/a')}")
    print(f"Competition-seasons loaded: {manifest.get('competition_seasons_loaded', 'n/a')}")
    print(f"Matches loaded: {manifest.get('matches_loaded', 'n/a')}")
    table_counts = manifest.get("table_counts", {})
    if isinstance(table_counts, dict):
        print("Key tables:")
        for table in ("fact_events", "fact_shots", "fact_passes", "fact_carries", "player_profile_stats", "team_match_stats"):
            print(f"  - {table}: {table_counts.get(table, 'n/a')}")


def run_app(args: argparse.Namespace) -> int:
    command = [sys.executable, "-m", "streamlit", "run", str(PROJECT_ROOT / "app.py")]
    if args.debug:
        command.extend(["--logger.level", "debug"])
    if args.port is not None:
        command.extend(["--server.port", str(args.port)])
    if args.headless:
        command.extend(["--server.headless", "true"])

    return subprocess.call(command, cwd=PROJECT_ROOT)


def main() -> int:
    args = parse_args()
    if args.command == "pipeline":
        run_pipeline(args)
        return 0
    if args.command == "app":
        return run_app(args)
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
