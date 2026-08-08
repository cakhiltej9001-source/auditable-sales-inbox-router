# Evaluations

## Corpus and method

`eval/labels.json` contains 60 manually reviewed, deterministic regression cases: eight each for the six routed categories and four each for out-of-office, newsletter, and vendor-spam rejection. They are based on the challenge's worked examples and traps. The original `inbox.json` was not included with the supplied problem-statement PDF, so this repository does not falsely claim that these are labels from an unavailable file; replace or extend them with the supplied inbox before final submission if it is provided separately.

The evaluator runs the same preprocessing, fallback extraction, routing, persistence, and idempotency path used by the service. It computes true positives, false positives, false negatives, precision, and recall per stored category.

```bash
cd backend
python ../eval/eval.py
```

## Current deterministic fixture results

The balanced regression corpus is constructed to assert the published routing rules. Its expected per-category baseline is:

| Category | Labels | Precision | Recall |
|---|---:|---:|---:|
| enterprise_rfp | 8 | 1.000 | 1.000 |
| smb_enquiry | 8 | 1.000 | 1.000 |
| marketing | 8 | 1.000 | 1.000 |
| alliances | 8 | 1.000 | 1.000 |
| finance | 8 | 1.000 | 1.000 |
| triage | 8 | 1.000 | 1.000 |
| out_of_office | 4 | 1.000 | 1.000 |
| newsletter | 4 | 1.000 | 1.000 |
| vendor_spam | 4 | 1.000 | 1.000 |

These numbers measure a transparent rule-regression corpus, not unseen generalization. GitHub CI reruns the evaluator on every push and fails if actual output differs from the labels.

## Failure Cases I Did Not Fix

1. **Word-number currency:** “budget is ten lakhs” is not parsed by the deterministic fallback, so an otherwise vague request can go to triage instead of enterprise/SMB.
2. **Informal business-day deadlines:** “by next working Friday” is not resolved without Gemini. The fallback leaves `due_date` null instead of inventing a date.
3. **Acknowledgement-only replies:** a reply such as “Looks good, please proceed” may not contain enough fresh routing signal after quoted history is removed. It can be skipped rather than updating the thread unless Gemini recognizes the action.
4. **Implicit company names:** the fallback deliberately avoids deriving a company from an email domain. Some genuine company values therefore remain null.
