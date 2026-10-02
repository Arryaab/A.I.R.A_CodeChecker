def is_token_expired(exp_timestamp: int, current_timestamp: int, leeway_seconds: int = 60) -> bool:
    """Returns True if the token is expired given a leeway window for clock skew.
    A token is expired only if current_timestamp > (exp_timestamp + leeway_seconds).
    """
    if leeway_seconds < 0:
        raise ValueError("leeway_seconds must be non-negative")
    # BUG: Subtracts leeway instead of adding, declaring valid tokens expired prematurely
    effective_exp = exp_timestamp - leeway_seconds
    return current_timestamp > effective_exp
