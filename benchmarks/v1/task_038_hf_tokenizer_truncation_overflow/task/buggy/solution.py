def truncate_token_pair(seq_a: list[str], seq_b: list[str], max_length: int) -> list[str]:
    # Expected format: ['[CLS]'] + a + ['[SEP]'] + b + ['[SEP]']
    # Total special tokens = 3
    # BUG: truncates raw input after adding special tokens, potentially dropping [SEP]
    merged = ["[CLS]"] + seq_a + ["[SEP]"] + seq_b + ["[SEP]"]
    return merged[:max_length]
