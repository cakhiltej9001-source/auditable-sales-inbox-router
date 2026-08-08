# Decisions

## 1. Deterministic Routing Owns Final Assignment

Gemini can extract category, deadline, amount, organization hints, and confidence. It cannot decide the final assignee or priority.

Reason: judges can inspect and test routing rules. Deterministic logic is easier to defend than hidden model behavior.

## 2. SQLite for Tests, PostgreSQL for Deployment

The code uses SQLModel/SQLAlchemy and works with SQLite for fast local checks. `docker-compose.yml` uses PostgreSQL for deployment-like runs.

Reason: hackathon teams need fast iteration, but the persistence model should still reflect production needs.

## 3. Idempotency Is Local First

`source_email_id` is unique locally. Replays return `duplicate` and do not call the Task API again.

Reason: the challenge brief states the shared Task API does not dedupe repeated POSTs.

## 4. Thread Replies Patch Existing Tasks

If a new email has a `thread_id` already associated with a task, the backend updates the task instead of creating a new one.

Reason: sales inbox threads evolve. Duplicate task creation hurts operators and makes analytics unreliable.

## 5. Grounded Chat Uses Validated Query Intents

The chat endpoint maps questions to a constrained query intent, queries the database, returns `supporting_data`, and only then asks Gemini to phrase the answer when configured.

Reason: free-form SQL generation is unnecessary and risky for this MVP.

## 6. Local Task API Fallback

When `TASK_API_BASE_URL` is unset, the backend creates stable mock task IDs.

Reason: this keeps demos and tests working without secrets or external infrastructure.

