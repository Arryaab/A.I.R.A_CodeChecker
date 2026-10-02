def csr_row_slice(indptr: list[int], indices: list[int], data: list[float], row: int):
    # BUG: negative row indexing allowed by python list but invalid in CSR
    start = indptr[row]
    end = indptr[row + 1]
    return indices[start:end], data[start:end]
