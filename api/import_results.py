"""Usage: python -m api.import_results [data/ads/dashboard.json]."""
import argparse
import hashlib
import json
import sys
import uuid
from pathlib import Path

from . import db


def import_snapshot(snapshot):
    db.validate_snapshot(snapshot)
    encoded = json.dumps(snapshot, ensure_ascii=False, allow_nan=False, sort_keys=True)
    run_id = str(uuid.uuid4())
    with db.connect() as conn:
        db.initialize_schema(conn)
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO dashboard_runs (run_id, source_sha256, meta, kpis, quality, model) VALUES (%s, %s, %s, %s, %s, %s)",
                            (run_id, hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
                             *(json.dumps(snapshot[key], ensure_ascii=False, allow_nan=False) for key in ("meta", "kpis", "quality", "model"))))
                cur.executemany("INSERT INTO dashboard_charts (run_id, chart_name, chart_data) VALUES (%s, %s, %s)",
                                [(run_id, name, json.dumps(rows, ensure_ascii=False, allow_nan=False)) for name, rows in snapshot["charts"].items()])
                cur.execute("INSERT INTO dashboard_active (singleton, run_id) VALUES (1, %s) ON DUPLICATE KEY UPDATE run_id = %s", (run_id, run_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return run_id


def main():
    parser = argparse.ArgumentParser(description="Transactionally import a Spark dashboard into MySQL")
    parser.add_argument("path", nargs="?", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "ads" / "dashboard.json")
    args = parser.parse_args()
    try:
        snapshot = json.loads(args.path.read_text(encoding="utf-8-sig"))
        run_id = import_snapshot(snapshot)
    except (OSError, ValueError, db.DatabaseUnavailable):
        print("Import failed: check input contract and local MySQL configuration. Credentials are not logged.", file=sys.stderr)
        return 1
    print(f"Imported run {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
