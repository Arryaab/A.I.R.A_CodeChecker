def verify_draft_tokens(draft_tokens: list[int], target_tokens: list[int]) -> tuple[list[int], int]:
    # Returns (accepted_tokens, rollback_count)
    accepted = []
    # BUG: does not break on mismatch, accepting subsequent matching tokens out of order!
    for d, t in zip(draft_tokens, target_tokens):
        if d == t:
            accepted.append(d)
    rollback = len(draft_tokens) - len(accepted)
    return accepted, rollback
