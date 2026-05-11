"""
run_all_ingestion.py
---------------------
Master runner – executes all three Bronze ingestion pipelines
in sequence and reports a final summary.

Run from the project root:
    python ingestion/run_all_ingestion.py
"""

import sys
import os
import time
import logging
from datetime import datetime

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Import individual ingestion modules ──────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ingestion.ingest_neon_postgres as neon_ingestion
import ingestion.ingest_google_drive as drive_ingestion
import ingestion.ingest_geolocation_api as geo_ingestion


PIPELINES = [
    ("Neon PostgreSQL (7 tables)", neon_ingestion.run),
    ("Google Drive CSV files (3 files)", drive_ingestion.run),
    ("Geolocation API (GAS endpoint)", geo_ingestion.run),
]


def main():
    overall_start = time.time()
    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║          BRONZE LAYER – FULL INGESTION RUN               ║")
    log.info(f"║          Started at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC              ║")
    log.info("╚══════════════════════════════════════════════════════════╝")

    results = []

    for name, run_fn in PIPELINES:
        log.info(f"\n▶ Running pipeline: {name}")
        start = time.time()
        status = "SUCCESS"
        try:
            run_fn()
        except SystemExit as e:
            if e.code != 0:
                status = "FAILED"
        except Exception as exc:
            log.error(f"  Unexpected error in '{name}': {exc}")
            status = "FAILED"

        elapsed = time.time() - start
        results.append((name, status, elapsed))
        log.info(f"▶ Pipeline '{name}' → {status} ({elapsed:.1f}s)\n")

    # ── Summary ──────────────────────────────────────────────────────────────
    total_elapsed = time.time() - overall_start
    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║                    INGESTION SUMMARY                     ║")
    log.info("╠══════════════════════════════════════════════════════════╣")
    for name, status, elapsed in results:
        icon = "✓" if status == "SUCCESS" else "✗"
        log.info(f"║  {icon}  {name:<42}  {elapsed:>6.1f}s  ║")
    log.info("╠══════════════════════════════════════════════════════════╣")
    log.info(f"║  Total time: {total_elapsed:.1f}s".ljust(57) + "║")
    log.info("╚══════════════════════════════════════════════════════════╝")

    failed = [r for r in results if r[1] == "FAILED"]
    if failed:
        log.error(f"{len(failed)} pipeline(s) failed. Check logs above.")
        sys.exit(1)
    else:
        log.info("All pipelines completed successfully. Bronze layer is ready.")


if __name__ == "__main__":
    main()
