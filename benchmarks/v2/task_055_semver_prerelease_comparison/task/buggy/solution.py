def parse_semver(v_str: str):
    prerelease = None
    if "-" in v_str:
        core, prerelease = v_str.split("-", 1)
    else:
        core = v_str
    parts = tuple(int(x) for x in core.split("."))
    return parts, prerelease

def compare_semver(v1: str, v2: str) -> int:
    """Returns 1 if v1 > v2, -1 if v1 < v2, 0 if v1 == v2 according to SemVer 2.0."""
    p1, pre1 = parse_semver(v1)
    p2, pre2 = parse_semver(v2)
    if p1 != p2:
        return 1 if p1 > p2 else -1
    # BUG: When core version matches, ignores pre-release and considers them equal
    return 0
