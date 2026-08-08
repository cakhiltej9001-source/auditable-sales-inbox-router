# Evals

The evaluator checks routing and skip behavior against labeled email fixtures in `eval/labels.json`.

Run:

```bash
cd backend
python ../eval/eval.py
```

Current coverage:

- PSU/government tender override
- enterprise deal above INR 10L
- finance escalation
- marketing/sponsorship routing
- alliance routing
- SMB routing
- out-of-office skip
- newsletter skip
- ambiguous triage

Key metrics:

- route accuracy
- skip accuracy
- priority accuracy

The evaluator intentionally uses the deterministic fallback extractor. This makes failures actionable and avoids hiding rule regressions behind model variance.

