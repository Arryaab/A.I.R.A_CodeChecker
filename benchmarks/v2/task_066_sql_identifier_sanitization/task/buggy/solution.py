def quote_identifier(identifier: str) -> str:
    """Quotes a SQL identifier according to ANSI SQL standards."""
    if not identifier:
        raise ValueError("Identifier cannot be empty")
    # BUG: Wraps in quotes but fails to escape internal double quotes, permitting injection breakout
    return f'"{identifier}"'
