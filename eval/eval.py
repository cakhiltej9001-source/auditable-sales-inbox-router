import json
import sys
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import Settings  # noqa: E402
from app.schemas import EmailIn  # noqa: E402
from app.services.extractor import HeuristicExtractor  # noqa: E402
from app.services.ingestion import IngestionService  # noqa: E402
from app.services.task_api import TaskApiClient  # noqa: E402


def main() -> int:
    labels = json.loads((Path(__file__).parent / "labels.json").read_text())
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    settings = Settings(database_url="sqlite://")

    total = len(labels)
    passed = 0
    failures = []
    with Session(engine) as session:
        service = IngestionService(session, HeuristicExtractor(), TaskApiClient(settings))
        for item in labels:
            result = service.ingest_email(EmailIn.model_validate(item["email"]))
            expected = item["expected"]
            ok = (
                result.status == expected["status"]
                and result.assignee_id == expected["assignee_id"]
                and result.priority == expected["priority"]
            )
            if ok:
                passed += 1
            else:
                failures.append(
                    {
                        "name": item["name"],
                        "expected": expected,
                        "actual": {
                            "status": result.status,
                            "assignee_id": result.assignee_id,
                            "priority": result.priority,
                            "reason": result.reason,
                        },
                    }
                )

    print(json.dumps({"passed": passed, "total": total, "failures": failures}, indent=2))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

