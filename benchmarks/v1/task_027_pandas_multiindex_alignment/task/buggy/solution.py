def align_multiindex_data(df1: dict, df2: dict) -> dict:
    aligned = {}
    for (k1, k2), v1 in df1.items():
        # BUG: only keys present in df1 are inspected, misses keys only in df2
        v2 = df2.get((k1, k2), 0)
        aligned[(k1, k2)] = v1 + v2
    return aligned
