# Evaluations

## Corpus and method

`eval/labels.json` contains 60 manually reviewed deterministic routing cases. `eval/challenge_cases.json` adds twelve harder worked-example regressions for Indian comma currency, ordinal and Hinglish dates, explicitly priced sponsorships, government overrides, ambiguous requests, directional vendor spam, and high-value non-sales amounts that must not override Marketing, Alliances, or Triage ownership.

The original `inbox.json` was not included with the supplied problem-statement PDF. This repository therefore does not falsely claim that these are labels from an unavailable file; replace or extend them with the supplied inbox before final submission if it is provided separately.

The evaluator runs the same preprocessing, fallback extraction, routing, persistence, and idempotency path used by the service. It also verifies explicitly expected company, deal-value, and due-date fields in the challenge cases. It computes true positives, false positives, false negatives, precision, and recall per stored category.

```bash
cd backend
python ../eval/eval.py
```

## Current deterministic fixture results

| Category | Labels | Precision | Recall |
|---|---:|---:|---:|
| enterprise_rfp | 11 | 1.000 | 1.000 |
| smb_enquiry | 9 | 1.000 | 1.000 |
| marketing | 10 | 1.000 | 1.000 |
| alliances | 10 | 1.000 | 1.000 |
| finance | 9 | 1.000 | 1.000 |
| triage | 10 | 1.000 | 1.000 |
| out_of_office | 4 | 1.000 | 1.000 |
| newsletter | 4 | 1.000 | 1.000 |
| vendor_spam | 5 | 1.000 | 1.000 |

These 72 results measure a transparent rule-regression corpus, not unseen generalization. GitHub CI reruns the evaluator on every push and fails if output differs from the labels.

## Failure Cases I Did Not Fix

1. **Word-number currency:** “budget is ten lakhs” is not parsed by the deterministic fallback, so an otherwise vague request can go to triage instead of enterprise or SMB.
2. **Informal business-day deadlines:** “by next working Friday” is not resolved without Gemini. The fallback leaves `due_date` null instead of inventing a date.
3. **Implicit company names:** explicit labels, organization-like sender names, and clear signature companies are extracted, but the fallback deliberately avoids deriving a company from an email domain. Some genuine company values therefore remain null.
4. **Novel vendor-pitch language:** directional spam is covered for common SEO, promotion, audit, backlink, and lead-generation patterns, but unfamiliar wording can still require Gemini or human review.
