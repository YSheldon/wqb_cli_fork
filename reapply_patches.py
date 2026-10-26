"""Reapply the two local wqb_cli sqlitesimu patches, idempotently.

Patch 1 (runtime.py): cap concurrent simulation batches at 4 (GLB account wall).
Patch 2 (db.py): dedupe repeated check names returned by /alphas/{id}.

Run:  python reapply_patches.py [--target PATH_TO_SITE_PACKAGES_WQB_CLI]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RUNTIME_ANCHOR = """        experiment = self.store.next_enrichment(run_id, now=now)
        if experiment:
            self._enrich(experiment, now=now)
            return True

        batch = self.store.next_simulate_batch(run_id, now=now)"""

RUNTIME_PATCHED = """        experiment = self.store.next_enrichment(run_id, now=now)
        if experiment:
            self._enrich(experiment, now=now)
            return True

        if self._inflight_slots(run_id) >= 4:
            return False

        batch = self.store.next_simulate_batch(run_id, now=now)"""

RUNTAIL_ANCHOR = """        if self.store.create_next_batch(run_id, now=now):
            return True
        return False

    def _simulate(self, batch: BatchRecord, *, now: float) -> None:"""

RUNTAIL_PATCHED = """        if self.store.create_next_batch(run_id, now=now):
            return True
        return False

    def _inflight_slots(self, run_id: str) -> int:
        with self.store.connect() as conn:
            row = conn.execute(
                \"\"\"
                SELECT COUNT(*) FROM simulation_batches
                WHERE run_id = ? AND state IN ('SIMULATING', 'POLLING', 'CHILD_POLLING')
                \"\"\",
                (run_id,),
            ).fetchone()
        return int(row[0])

    def _simulate(self, batch: BatchRecord, *, now: float) -> None:"""

DB_ANCHOR = """            conn.execute("DELETE FROM alpha_checks WHERE alpha_id = ?", (alpha_id,))
            for check in checks if isinstance(checks, list) else []:
                if not isinstance(check, dict) or not check.get("name"):
                    continue
                conn.execute("""

DB_PATCHED = """            conn.execute("DELETE FROM alpha_checks WHERE alpha_id = ?", (alpha_id,))
            seen_check_names: set[str] = set()
            for check in checks if isinstance(checks, list) else []:
                if not isinstance(check, dict) or not check.get("name"):
                    continue
                check_name = str(check["name"])
                if check_name in seen_check_names:
                    continue
                seen_check_names.add(check_name)
                conn.execute("""

DB_NAME_ANCHOR = """                    (
                        alpha_id,
                        str(check["name"]),
                        check.get("result"),"""

DB_NAME_PATCHED = """                    (
                        alpha_id,
                        check_name,
                        check.get("result"),"""


def apply(text: str, anchor: str, patched: str, label: str) -> tuple[str, str]:
    if patched in text:
        return text, f"already patched: {label}"
    if anchor not in text:
        return text, f"ANCHOR NOT FOUND: {label}"
    return text.replace(anchor, patched, 1), f"patched: {label}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target",
        default=r"C:\Users\XCrab\AppData\Local\Programs\Python\Python313\Lib\site-packages\wqb_cli",
    )
    args = parser.parse_args()
    target = Path(args.target)
    log = []

    runtime = target / "sqlitesimu" / "runtime.py"
    text, status = apply(runtime.read_text(encoding="utf-8"), RUNTIME_ANCHOR, RUNTIME_PATCHED, "runtime slots cap")
    text, status2 = apply(text, RUNTAIL_ANCHOR, RUNTAIL_PATCHED, "runtime _inflight_slots")
    log += [status, status2]
    runtime.write_text(text, encoding="utf-8")

    db = target / "sqlitesimu" / "db.py"
    text, status = apply(db.read_text(encoding="utf-8"), DB_ANCHOR, DB_PATCHED, "db checks dedupe")
    text, status2 = apply(text, DB_NAME_ANCHOR, DB_NAME_PATCHED, "db check name reuse")
    log += [status, status2]
    db.write_text(text, encoding="utf-8")

    for line in log:
        print(line)
    if any("ANCHOR NOT FOUND" in line for line in log):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
