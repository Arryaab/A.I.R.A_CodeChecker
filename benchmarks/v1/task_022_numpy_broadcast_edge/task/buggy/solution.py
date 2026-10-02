def broadcast_shapes(s1: tuple[int, ...], s2: tuple[int, ...]) -> tuple[int, ...]:
    r1 = list(reversed(s1))
    r2 = list(reversed(s2))
    max_len = max(len(r1), len(r2))
    res = []
    for i in range(max_len):
        d1 = r1[i] if i < len(r1) else 1
        d2 = r2[i] if i < len(r2) else 1
        if d1 == d2:
            res.append(d1)
        elif d1 == 1:
            res.append(d2)
        # BUG: forgot to handle d2 == 1, erroneously raises mismatch
        else:
            raise ValueError(f"Shapes {s1} and {s2} not broadcastable")
    return tuple(reversed(res))
