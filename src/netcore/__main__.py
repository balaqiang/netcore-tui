"""``python -m netcore`` entry point."""

from __future__ import annotations

import argparse
import sys

from netcore import __version__


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="netcore",
        description="NetCore TUI — data center network management simulator "
        "(simulation only; no real network access).",
    )
    parser.add_argument("--version", action="version", version=f"netcore {__version__}")
    parser.add_argument("--db", help="SQLite database path (env: NETCORE_DB)")
    parser.add_argument(
        "--seed",
        choices=["spine-leaf", "two-router"],
        help="load a sample lab if the database is empty",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Build the container and run the Textual app."""
    args = parse_args(argv)
    from netcore.bootstrap import build_container
    from netcore.infrastructure.config import AppConfig
    from netcore.infrastructure.logging_setup import configure_logging
    from netcore.tui.app import NetCoreApp

    config = AppConfig.resolve(db_flag=args.db, seed_lab=args.seed)
    configure_logging(config.log_path)
    container = build_container(config)
    try:
        NetCoreApp(container.services).run()
    finally:
        container.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
