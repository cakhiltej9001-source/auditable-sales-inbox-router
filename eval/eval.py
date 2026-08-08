import json
import sys
from collections import defaultdict
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.models import ProcessedEmail  # noqa: E402
from app.schemas import EmailIn  # noqa: E402
from app.services.extractor import HeuristicExtractor  # noqa: E402
from app.services.ingestion import IngestionService  # noqa: E402


def main() -> int:
    labels = json.loads((Path(__file__).parent / "labels.json").read_text(encoding="utf-8"))
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    failures: list[dict] = []
    counts = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})

    with Session(engine) as session:
        service = IngestionService(session, HeuristicExtractor())
        for item in labels:
            email = EmailIn.model_validate(item["email"])
            result = service.ingest_email(email, "cakhiltej9001@gmail.com", "eval")
            audit = session.exec(select(ProcessedEmail).where(ProcessedEmail.source_email_id == email.email_id)).one()
            expected = item["expected"]
            actual_category = audit.category
            expected_category = expected["category"]
            if actual_category == expected_category:
                counts[expected_category]["tp"] += 1
            else:
                counts[expected_category]["fn"] += 1
                counts[actual_category]["fp"] += 1
            ok = (
                result.status == expected["status"]
                and result.assignee_id == expected["assignee_id"]
                and result.priority == expected["priority"]
                and actual_category == expected_category
            )
            if not ok:
                failures.append({
                    "name": item["name"],
                    "expected": expected,
                    "actual": {
                        "status": result.status,
                        "category": actual_category,
                        "assignee_id": result.assignee_id,
                        "priority": result.priority,
                        "reason": result.reason,
                    },
                })

    metrics = {}
    for category, values in sorted(counts.items()):
        precision_denominator = values["tp"] + values["fp"]
        recall_denominator = values["tp"] + values["fn"]
        metrics[category] = {
            **values,
            "precision": round(values["tp"] / precision_denominator, 3) if precision_denominator else 0.0,
            "recall": round(values["tp"] / recall_denominator, 3) if recall_denominator else 0.0,
        }
    output = {"passed": len(labels) - len(failures), "total": len(labels), "per_category": metrics, "failures": failures}
    print(json.dumps(output, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
