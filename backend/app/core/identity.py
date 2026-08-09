def normalize_candidate_id(value: str) -> str:
    """Return the canonical identity used by every candidate-scoped query."""
    candidate = str(value).strip().lower()
    local_part, separator, domain = candidate.partition("@")
    if not separator:
        return candidate
    canonical_local = local_part.split("+", 1)[0]
    return f"{canonical_local}@{domain}"
