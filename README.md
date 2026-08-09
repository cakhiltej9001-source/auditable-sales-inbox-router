# Sales Inbox Task Router

**candidate_id:** `cakhiltej9001@gmail.com`

**Frontend:** https://auditable-sales-inbox-router-1.onrender.com

**Backend / ingest / Task API:** https://auditable-sales-inbox-router.onrender.com

**Chat endpoint:** https://auditable-sales-inbox-router.onrender.com/api/chat

Video Walkthrough - https://drive.google.com/file/d/1DTjFWwX5rU2PrYZrI0zk7VkA2rOYACC_/view?usp=drive_link

An auditable sales-inbox agent: it extracts grounded facts with Gemini when configured, applies deterministic business rules, prevents replay duplicates, reconciles thread replies, persists every decision, and answers analytics questions only from stored data.

## Quick start — three commands

```bash
cp .env.example .env
docker compose up --build
# open http://localhost:5173 (API docs: http://localhost:8000/docs)
```

On Windows, copy `.env.example` to `.env` in Explorer or use `Copy-Item .env.example .env` for the first command.

## What the system does

1. Accepts the exact inbox schema through synchronous `POST /ingest` in batches of at most 100.
2. Strips HTML and quoted reply history, rejects obvious noise, then uses Gemini structured output or a deterministic fallback extractor.
3. Applies fixed precedence in Python: government/PSU override → Finance/Marketing/Alliances intent → ambiguity → enterprise sales threshold → SMB.
4. Writes through one shared task persistence service and stores an audit row in PostgreSQL. Replayed `email_id` values are ignored; new messages on an existing thread merge into its task without erasing previously supported facts.
5. Serves aggregate and conversational answers from stored classifications rather than asking a model to invent numbers.

## Required API contract

All routes use the backend URL above and require no authentication:

- `POST /tasks` — create a validated task
- `PATCH /tasks/{task_id}` — update allowed task fields
- `GET /tasks?candidate_id=cakhiltej9001@gmail.com` — grader-facing task list
- `DELETE /tasks/{task_id}` — development cleanup
- `GET /users` — team roster
- `POST /ingest` — synchronous batch ingest, maximum 100
- `GET /ready` — verifies the database and reports `gemini` or `heuristic_fallback` extraction mode without exposing secrets
- `GET /api/tasks` — enriched frontend task list
- `GET /api/stats` — processed/created/updated/skipped/spurious aggregates by category and run
- `PATCH /api/tasks/{task_id}/spurious` — record or clear an auditable reviewer spurious flag
- `POST /api/chat` — grounded analytics with `supporting_data`

Example:

```bash
curl -X POST https://auditable-sales-inbox-router.onrender.com/ingest \
  -H "Content-Type: application/json" \
  -d '{"candidate_id":"cakhiltej9001@gmail.com","emails":[{"email_id":"em_00142","thread_id":"th_0091","message_index":0,"from_name":"Suresh Kulkarni","from_email":"suresh@example.com","to":"sales@company.com","cc":[],"subject":"Enterprise RFP","body":"Please submit a proposal. Budget INR 25L.","received_at":"2026-08-08T09:14:22+05:30","attachments":[],"is_reply":false}]}'
```

## Local development

Backend on Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
pytest
uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm ci
npm run build
npm run dev
```

Evaluation:

```powershell
cd backend
python ../eval/eval.py
```

The checked-in evaluator currently runs 72 deterministic cases, including twelve challenge-trap cases. `EVALS.md` clearly separates these regression fixtures from the unavailable original `inbox.json` corpus.

## Environment and deployment

- `DATABASE_URL`: persistent PostgreSQL URL. On Render, use the Internal Database URL for a database in the same region.
- `GEMINI_API_KEY`: server-only Gemini key. Never prefix it with `VITE_` or expose it to browser code.
- `GEMINI_MODEL`: defaults to `gemini-2.5-flash`.
- `FRONTEND_ORIGIN`: exact deployed frontend origin, without a trailing slash.
- `CANDIDATE_ID`: must remain `cakhiltej9001@gmail.com`.
- `VITE_API_BASE_URL`: frontend build-time backend URL.
- `VITE_CANDIDATE_ID`: optional frontend override; production must use the same candidate ID above.

Render backend settings:

```text
Root Directory: backend
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health Check Path: /ready
```

Render frontend static-site settings:

```text
Root Directory: frontend
Build Command: npm ci && npm run build
Publish Directory: dist
Environment: VITE_API_BASE_URL=https://auditable-sales-inbox-router.onrender.com
```

Do not commit `.env`, API keys, database passwords, production email payloads, or access tokens.

## Submission readiness

Before sharing the URLs, confirm the backend responds inside the grader's 60-second timeout and that Gemini is active:

```powershell
curl.exe https://auditable-sales-inbox-router.onrender.com/ready
```

The response should contain `"status":"ready"`, `"database":"ok"`, and `"extractor":"gemini"`. If it reports `heuristic_fallback`, set `GEMINI_API_KEY` only on the Render backend and redeploy.

Use a fresh production database for grading. If this candidate's database contains demo runs, the following operator-only command deletes only that canonical candidate's tasks and audit rows. It requires the identity twice and is intentionally not exposed as a public HTTP endpoint:

```powershell
cd backend
python scripts/reset_candidate_data.py --candidate-id cakhiltej9001@gmail.com --confirm-candidate-id cakhiltej9001@gmail.com
```

Run it only against the intended database, then verify that `GET /tasks?candidate_id=cakhiltej9001@gmail.com` returns an empty list before the grader starts.
