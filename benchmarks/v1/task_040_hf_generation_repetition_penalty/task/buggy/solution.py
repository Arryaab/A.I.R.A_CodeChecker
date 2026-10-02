def apply_repetition_penalty(logits: list[float], seen_tokens: set[int], penalty: float = 1.2) -> list[float]:
    out = list(logits)
    for token_id in seen_tokens:
        if token_id < len(out):
            # BUG: always divides by penalty even for negative logits (making them less negative!)
            out[token_id] /= penalty
    return out
