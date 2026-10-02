def match_choice(val: str, choices: list[str], case_sensitive: bool = True) -> str:
    # BUG: ignores case_sensitive flag completely
    if val in choices:
        return val
    raise ValueError(f"'{val}' is not in {choices}")
