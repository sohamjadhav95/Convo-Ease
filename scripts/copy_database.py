"""
Copy every ConvoEase table from one database to another, e.g. to move from the
Neon database made by Vercel's integration to a standalone Neon project.

Usage (PowerShell; the URLs stay out of the command line and shell history):
    $env:SOURCE_DATABASE_URL = "postgresql://...old..."
    $env:TARGET_DATABASE_URL = "postgresql://...new..."
    python scripts/copy_database.py            # copy, then compare row counts
    python scripts/copy_database.py --dry-run  # only show the row counts to copy

The source is only read. The target must have no rows yet (tables are created
if missing), so a second run cannot duplicate data. Message numbers (seq) are
kept so chat order and read positions stay the same.
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sqlalchemy import func, insert, select, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from database.Database_processing.db_manager import (  # noqa: E402
    _create_engine,
    metadata,
    normalize_database_url,
)

BATCH = 100  # media rows hold whole files, so keep batches small


def open_engine(env_name):
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        sys.exit(f"Set {env_name} first (see the usage at the top of this file).")
    url = normalize_database_url(raw)
    parsed = make_url(url)
    where = parsed.database if parsed.drivername.startswith("sqlite") else f"{parsed.host}/{parsed.database}"
    print(f"{env_name.split('_')[0].title():<7} {parsed.drivername.split('+')[0]}  {where}")
    return _create_engine(url)


def counts(engine, tables):
    with engine.connect() as conn:
        return {t.name: conn.execute(select(func.count()).select_from(t)).scalar() for t in tables}


def main():
    parser = argparse.ArgumentParser(description="Copy all ConvoEase data between databases.")
    parser.add_argument("--dry-run", action="store_true", help="show row counts without writing")
    args = parser.parse_args()

    source = open_engine("SOURCE_DATABASE_URL")
    target = open_engine("TARGET_DATABASE_URL")
    if str(source.url) == str(target.url):
        sys.exit("Source and target are the same database.")

    tables = metadata.sorted_tables  # parents before children
    source_counts = counts(source, tables)
    print("\nRows to copy:")
    for name, number in source_counts.items():
        print(f"  {name:<14} {number}")
    if args.dry_run:
        return 0

    metadata.create_all(target)
    existing = {name: n for name, n in counts(target, tables).items() if n}
    if existing:
        sys.exit(f"Target already has data ({existing}). Use an empty database.")

    with target.begin() as out, source.connect() as src:
        for table in tables:
            copied = 0
            result = src.execution_options(stream_results=True).execute(select(table))
            while True:
                rows = result.fetchmany(BATCH)
                if not rows:
                    break
                out.execute(insert(table), [dict(row._mapping) for row in rows])
                copied += len(rows)
            print(f"  copied {table.name:<14} {copied}")

        # Rows were inserted with explicit message numbers, so move the
        # Postgres counter past them or the next new message would collide.
        if target.dialect.name == "postgresql":
            out.execute(text(
                "SELECT setval(pg_get_serial_sequence('messages', 'seq'), "
                "COALESCE((SELECT MAX(seq) FROM messages), 1))"
            ))

    after = counts(target, tables)
    mismatched = {n: (source_counts[n], after[n]) for n in source_counts if source_counts[n] != after[n]}
    if mismatched:
        sys.exit(f"Row counts differ (source, target): {mismatched}")
    print("\nDone. Every table matches the source row for row.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
