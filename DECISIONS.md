# Engineering Decisions

## 1. Gemini extracts facts; Python owns routing

Gemini may identify an explicit company, amount, deadline, and business intent through a narrow JSON schema. It never chooses `assignee_id` or `priority`; deterministic Python applies the published precedence. After transient Gemini failures the service retries up to three times with exponential backoff, then uses a conservative heuristic extractor so an email is not silently dropped.

With two more weeks, I would add a token-budgeted request queue, provider telemetry, circuit breaking, and recorded-model regression tests against redacted production-like messages.

## 2. Idempotency uses an immutable email identity

`ProcessedEmail.source_email_id` is unique within a canonical candidate identity. Candidate IDs are trimmed, lowercased, and stripped of `+alias` tags on every read and write, so an alias cannot create a second task namespace. A replay increments audit metadata and returns a duplicate result without another task write. Tasks also use a stable thread-derived ID during ingest, while direct `POST /tasks` and ingestion share one task-write service.

With two more weeks, I would add PostgreSQL advisory locks or transactional upserts to make simultaneous delivery of the same message safe across multiple workers.

## 3. Thread reconciliation preserves supported facts and the grader key

A new `email_id` on an existing candidate/thread updates the task and increments `update_count`. The task retains the original `source_email_id`, allowing Run 1 to remain alignable, while every reply is stored as its own audit row. Quoted old text is removed before extraction. Acknowledgement-only replies update the audit without rerouting, and partial replies merge only newly supported facts so existing company, value, deadline, and priority evidence are not erased.

With two more weeks, I would store field-level change history and distinguish customer replies from internal forwards more explicitly.

## 4. Chat is a constrained query layer, not text-to-SQL

The path is: question → allow-listed intent → SQLModel query/filter/group-by → `supporting_data` → deterministic answer text. Batch email IDs are part of the request scope. Zero and unknown are valid results, compound filters are explicit, and action requests are refused. Gemini is not allowed to calculate or replace numbers. Reviewer spurious flags are persisted with a reason and timestamp, making the spurious-rate answer auditable.

With two more weeks, I would formalize the intent grammar, add a read-only analytical view, and optionally let Gemini paraphrase a frozen result object under a schema without changing its values.

## 5. Known limitation knowingly shipped

The fallback parser handles Indian comma currency, lakh/crore units, ISO/numeric/ordinal dates, explicit company labels, clear signature companies, and organization-like sender names, but it still misses word-number values such as “ten lakhs,” informal deadlines such as “next working Friday,” and implicit company mentions. Returning null or medium/low confidence is safer than fabricating a value or date.

With two more weeks, I would add a locale-aware word-number/date parser, more multilingual fixtures, and calibrated confidence based on held-out data rather than fixed heuristic bands.
