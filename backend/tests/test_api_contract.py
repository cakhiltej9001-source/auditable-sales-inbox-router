from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.core.database import get_session
from app.main import app
from app.api.routes import _normalized_category, _normalized_priority


def _client(tmp_path) -> TestClient:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def _task_payload() -> dict:
    return {
        "candidate_id": "cakhiltej9001@gmail.com",
        "source_email_id": "api-email-1",
        "thread_id": "api-thread-1",
        "title": "Enterprise RFP",
        "description": "A persisted task",
        "assignee_id": "u_aarti",
        "category": "enterprise_rfp",
        "priority": "high",
        "due_date": "2026-08-10",
        "deal_value_inr": 2500000,
        "company_name": None,
        "confidence": 0.91,
    }


def test_bad_enum_has_exact_400_shape(tmp_path):
    client = _client(tmp_path)
    payload = _task_payload()
    payload["assignee_id"] = "Aarti"
    response = client.post("/tasks", json=payload)
    assert response.status_code == 400
    assert response.json() == {
        "error": "invalid_enum_value",
        "field": "assignee_id",
        "received": "Aarti",
        "allowed": ["u_aarti", "u_rohit", "u_meera", "u_karan", "u_divya", "u_triage"],
    }


def test_task_crud_contract(tmp_path):
    client = _client(tmp_path)
    created = client.post("/tasks", json=_task_payload())
    assert created.status_code == 201
    task_id = created.json()["task_id"]

    listed = client.get("/tasks", params={"candidate_id": "cakhiltej9001@gmail.com"})
    assert listed.status_code == 200
    assert listed.json()[0]["source_email_id"] == "api-email-1"

    patched = client.patch(f"/tasks/{task_id}", json={"priority": "medium"})
    assert patched.status_code == 200
    assert patched.json()["priority"] == "medium"

    assert client.delete(f"/tasks/{task_id}").status_code == 204
    assert client.get("/tasks", params={"candidate_id": "cakhiltej9001@gmail.com"}).json() == []


def test_ingest_is_synchronous_and_idempotent(tmp_path):
    client = _client(tmp_path)
    payload = {
        "candidate_id": "cakhiltej9001@gmail.com",
        "emails": [{
            "email_id": "ingest-1", "thread_id": "ingest-thread-1", "message_index": 0,
            "from_name": "Buyer", "from_email": "buyer@example.com", "to": "sales@company.com", "cc": [],
            "subject": "Product demo", "body": "Please schedule a demo. Budget INR 5L.",
            "received_at": "2026-08-08T10:00:00Z", "attachments": [], "is_reply": False,
        }],
    }
    first = client.post("/ingest", json=payload)
    second = client.post("/ingest", json=payload)
    assert first.json() == {"processed": 1, "tasks_created": 1, "tasks_updated": 0, "skipped": 0, "errors": []}
    assert second.json() == {"processed": 1, "tasks_created": 0, "tasks_updated": 0, "skipped": 1, "errors": []}
    assert len(client.get("/tasks", params={"candidate_id": "cakhiltej9001@gmail.com"}).json()) == 1


def test_legacy_values_are_normalized_for_contract_responses():
    assert _normalized_category("rfp") == "enterprise_rfp"
    assert _normalized_category("government") == "enterprise_rfp"
    assert _normalized_category("smb") == "smb_enquiry"
    assert _normalized_category("unknown") == "triage"
    assert _normalized_priority("normal") == "low"
