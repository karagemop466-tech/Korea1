"""Keep the manually maintained, audit-qualified executive summary intact.

The previous generator made unsupported assertions from provisional backtests.
Update EXECUTIVE_SUMMARY.md only after re-verifying its claims and sources.
"""
from pathlib import Path

if __name__ == "__main__":
    path = Path(__file__).resolve().parents[1] / "EXECUTIVE_SUMMARY.md"
    if not path.is_file():
        raise SystemExit("Executive summary missing; restore the audit-qualified document")
    print(f"Preserved audit-qualified summary: {path}")
