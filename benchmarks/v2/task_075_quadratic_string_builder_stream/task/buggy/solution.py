from typing import List

def assemble_stream_chunks(chunks: List[str]) -> str:
    """Concatenates list of text chunks into complete document."""
    # BUG: Repeated quadratic string re-allocation in loop O(N^2)
    result = ""
    for chunk in chunks:
        result += chunk
    return result
