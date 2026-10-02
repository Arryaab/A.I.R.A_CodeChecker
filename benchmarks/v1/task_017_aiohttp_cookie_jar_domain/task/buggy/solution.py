def is_domain_match(request_domain: str, cookie_domain: str) -> bool:
    # BUG: simple endswith allows attackerexample.com to match example.com
    return request_domain.endswith(cookie_domain)
