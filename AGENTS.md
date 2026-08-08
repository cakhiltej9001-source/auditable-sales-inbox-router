# AGENTS.md

## Project

Sales Inbox -> Task Router for the Alumnx AI Labs FDE Intern Challenge.

The goal is not a generic email classifier. The system must convert noisy sales inbox emails into trustworthy routed tasks with auditability, replay safety, and grounded analytics.

## Architecture

- `backend/`: FastAPI service.
  - `POST /ingest`: accepts a batch of emails, dedupes by `source_email_id`, reconciles by `thread_id`, extracts structured fields, routes deterministically, and persists an audit trail.
  - `GET /stats`: dashboard aggregates.
  - `GET /tasks`: processed task list.
  - `GET /skipped`: skipped/no-task log.
  - `POST /chat`: grounded analytics chat using validated query intents and database results.
- `frontend/`: React + Vite + TypeScript reviewer dashboard.
- `eval/`: labeled examples and lightweight evaluator.
- PostgreSQL is the production database. SQLite is acceptable for local quick starts and tests.
- Gemini is used only for structured extraction and optional answer phrasing. Routing decisions must stay deterministic in Python.

## Core Business Rules

Use deterministic precedence:

1. Skip out-of-office, newsletters, vendor spam, and non-actionable emails.
2. Government/PSU tender or enterprise deal above INR 10L -> `u_aarti`.
3. Finance/billing/payment issue -> `u_divya`.
4. Marketing/sponsorship/campaign -> `u_meera`.
5. Partnership/alliance/channel request -> `u_karan`.
6. SMB deal at or below INR 10L -> `u_rohit`.
7. Ambiguous but possibly actionable -> `u_triage`.

Priority:

- Deadline within 72 hours -> `high`.
- Explicit deadline later than 72 hours -> `medium`.
- No deadline -> `normal`.

Do not fabricate company, due date, deal value, source email id, or thread id. Unknown values must remain null/unknown and be visible in the decision reason.

## Commands

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
npm run build
```

Full stack with PostgreSQL:

```bash
cp .env.example .env
docker compose up --build
```

Evaluations:

```bash
cd backend
python ../eval/eval.py
```

## Test Requirements

Before publishing code, run:

- `pytest` from `backend/`
- `npm run build` from `frontend/`

Add or update tests when changing:

- routing precedence
- idempotency behavior
- thread reconciliation
- chat query support
- database models

## Guardrails

- Never commit `.env`, API keys, task API tokens, email payload dumps, or production credentials.
- Keep Gemini prompts and schemas narrow. Do not let an LLM decide final assignee or priority.
- Never generate arbitrary SQL from user chat text.
- Preserve auditability: every skipped, created, duplicate, and updated email should have a reason.
- Keep changes focused. Do not refactor unrelated surfaces during hackathon work.

