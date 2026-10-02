def rle_encode(s: str) -> str:
    # BUG: Crashes on empty string and miscounts single-character runs
    if not s:
        return ""
    result = []
    current_char = s[0]
    count = 1
    for ch in s[1:]:
        if ch == current_char:
            count += 1
        else:
            result.append(f"{current_char}{count}")
            current_char = ch
            count = 1
    result.append(f"{current_char}{count}")
    return "".join(result)

def rle_decode(s: str) -> str:
    # BUG: Fails on counts > 9 because it assumes single digit count
    if not s:
        return ""
    result = []
    i = 0
    while i < len(s):
        ch = s[i]
        count = int(s[i+1])
        result.append(ch * count)
        i += 2
    return "".join(result)
