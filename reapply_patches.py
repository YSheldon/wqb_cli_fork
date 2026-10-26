"""Reapply the local wqb_cli 0.6.1 sqlitesimu slot-cap patch, idempotently.

Patch (runtime.py): cap concurrent simulation batches at 4 (GLB account wall).
No checks-dedupe patch needed on 0.6.1: alpha_checks schema v6 keys rows by
(alpha_id, ordinal), so repeated check names no longer violate a UNIQUE index.

Run:  python reapply_patches.py [--target PATH_TO_SITE_PACKAGES_WQB_CLI]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

STEP_ANCHOR = """    def _step_simulation(self, run_id: str, *, now: float) -> bool:
        batch = self.store.next_simulate_batch(run_id, now=now)"""

STEP_PATCHED = """    def _step_simulation(self, run_id: str, *, now: float) -> bool:
        if self._inflight_slots(run_id) >= 4:
            return False
        batch = self.store.next_simulate_batch(run_id, now=now)"""

METHOD_ANCHOR = """    def _simulate(self, batch: BatchRecord, *, now: float) -> None:"""

METHOD_PATCHED = """    def _inflight_slots(self, run_id: str) -> int:
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

    runtime = target / "sqlitesimu" / "runtime.py"
    text = runtime.read_text(encoding="utf-8")
    text, status1 = apply(text, STEP_ANCHOR, STEP_PATCHED, "runtime 4-slot cap")
    text, status2 = apply(text, METHOD_ANCHOR, METHOD_PATCHED, "runtime _inflight_slots")
    runtime.write_text(text, encoding="utf-8")

    for line in (status1, status2):
        print(line)
    if "ANCHOR NOT FOUND" in (status1, status2):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
