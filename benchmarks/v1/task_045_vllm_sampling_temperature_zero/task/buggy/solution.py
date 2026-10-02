def sample_token(logits: list[float], temperature: float = 0.0) -> int:
    # BUG: divides by temperature even when temperature == 0.0 -> ZeroDivisionError
    scaled = [x / temperature for x in logits]
    return max(range(len(scaled)), key=lambda i: scaled[i])
