import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import Session

from app.core.database import engine
from app.core.identity import normalize_candidate_id
from app.services.maintenance import purge_candidate_data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete persisted tasks and audit rows for exactly one candidate identity."
    )
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument(
        "--confirm-candidate-id",
        required=True,
        help="Must canonicalize to the same identity as --candidate-id.",
    )
    args = parser.parse_args()
    candidate = normalize_candidate_id(args.candidate_id)
    confirmation = normalize_candidate_id(args.confirm_candidate_id)
    if candidate != confirmation:
        parser.error("confirmation does not match candidate identity")

    with Session(engine) as session:
        counts = purge_candidate_data(session, candidate)
    print(f"Deleted production data for {candidate}: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
