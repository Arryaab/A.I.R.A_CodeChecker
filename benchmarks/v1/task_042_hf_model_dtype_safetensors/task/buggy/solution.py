def dequantize_weights(qweights: list[int], scale: float) -> list[float]:
    # BUG: integer division truncates float values
    return [float(w // scale) for w in qweights]
