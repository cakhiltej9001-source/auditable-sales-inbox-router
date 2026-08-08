# Engineering Decisions

## 1. Gemini extracts facts; Python owns routing

Gemini may identify an explicit company, amount, deadline, and business intent through a narrow JSON schema. It never chooses `assignee_id` or `priority`; deterministic Python applies the published precedence. After transient Gemini failures the service retries up to three times with exponential backoff, then uses a conservative heuristic extractor so an email is not silently dropped.

With two more weeks, I would add a token-budgeted request queue, provider telemetry, circuit breaking, and recorded-model regression tests against redacted production-like messages.

## 2. Idempotency uses an immutable email identity

`ProcessedEmail.source_email_id` is unique. A replay increments audit metadata and returns a duplicate result without another task write. Tasks also use a stable thread-derived ID during ingest, while direct `POST /tasks` checks candidate plus source email before inserting.

With two more weeks, I would add PostgreSQL advisory locks or transactional upserts to make simultaneous delivery of the same message safe across multiple workers.

## 3. Thread reconciliation preserves the original grader key

A new `email_id` on an existing candidate/thread updates the task and increments `update_count`. The task retains the original `source_email_id`, allowing Run 1 to remain alignable, while every reply is stored as its own audit row. Quoted old text is removed before extraction.

With two more weeks, I would store field-level change history and distinguish customer replies from internal forwards more explicitly.

## 4. Chat is a constrained query layer, not text-to-SQL

The path is: question → allow-listed intent → SQLModel query/filter/group-by → `supporting_data` → deterministic answer text. Batch email IDs are part of the request scope. Zero and unknown are valid results, compound filters are explicit, and action requests are refused. Gemini is not allowed to calculate or replace numbers.

With two more weeks, I would formalize the intent grammar, add a read-only analytical view, and optionally let Gemini paraphrase a frozen result object under a schema without changing its values.

## 5. Known limitation knowingly shipped

The fallback parser handles numeric INR forms and a narrow set of date formats, but it misses some word-number values (for example “ten lakhs”), informal deadlines such as “next working Friday,” and implicit company mentions. Returning null or medium/low confidence is safer than fabricating a value or date.

With two more weeks, I would add a locale-aware Indian currency/date parser, more Hinglish fixtures, and calibrated confidence based on held-out data rather than fixed heuristic bands.
