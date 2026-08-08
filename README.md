# Sales Inbox -> Task Router

FastAPI + React implementation of the Alumnx AI Labs FDE Intern Challenge.

The app ingests noisy sales inbox emails, extracts structured business signals with Gemini, applies deterministic routing rules, creates or updates tasks safely, and exposes a reviewer dashboard plus grounded analytics chat.

## Why This Stands Out

- Gemini is used for extraction, not final decisions.
- Routing rules are deterministic, testable, and auditable.
- Duplicate emails do not create duplicate tasks.
- Replies on an existing thread update the existing task.
- Analytics chat answers from database-backed `supporting_data`, not model guesses.
- Skipped/no-task emails are logged for reviewer trust.

## Repo Structure

```text
backend/      FastAPI API, routing engine, persistence, tests
frontend/     React/Vite TypeScript dashboard
eval/         Labeled examples and evaluator
.github/      CI workflow
AGENTS.md     Codex coding conventions and guardrails
```

## Quick Start

1. Copy environment settings:

```bash
cp .env.example .env
```

2. Start PostgreSQL and both apps:

```bash
docker compose up --build
```

3. Open:

- Frontend: http://localhost:5173
- Backend docs: http://localhost:8000/docs

## Backend Local Run

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

On Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

If `DATABASE_URL` is not set, the backend uses local SQLite for easy testing.

## Frontend Local Run

```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE_URL` if the backend is not on `http://localhost:8000`.

## Example Ingest

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "candidate_id": "your-name",
    "emails": [
      {
        "source_email_id": "msg-001",
        "thread_id": "thread-psu-001",
        "from_email": "procurement@example.gov.in",
        "subject": "Urgent PSU LMS tender closes Monday",
        "body": "We need a proposal for 5000 learners. Budget INR 25L. Deadline 2026-08-10.",
        "received_at": "2026-08-08T10:00:00Z"
      }
    ]
  }'
```

## Environment

See `.env.example`.

Important values:

- `GEMINI_API_KEY`: enables Gemini structured extraction.
- `TASK_API_BASE_URL`: optional external Task API base URL.
- `TASK_API_TOKEN`: optional token for the external Task API.
- `DATABASE_URL`: PostgreSQL URL for production.

Without Gemini or Task API credentials, the project still runs with deterministic local fallbacks so reviewers can test the flow.

## Verification

```bash
cd backend
pytest
python ../eval/eval.py

cd ../frontend
npm run build
```

## GitHub Flow

Recommended:

```bash
git checkout -b agent/sales-inbox-task-router
git add AGENTS.md README.md DECISIONS.md EVALS.md .env.example backend frontend eval docker-compose.yml .github
git commit -m "feat: build sales inbox task router"
git push -u origin agent/sales-inbox-task-router
gh pr create --draft --fill
```

Do not commit `.env` or real email data.

