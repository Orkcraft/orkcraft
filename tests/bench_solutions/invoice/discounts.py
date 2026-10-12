def apply_code(cents, code):
    code = (code or "").upper()
    if not code:
        return cents
    if code == "TENOFF":
        return -(-cents * 9 // 10)
    if code == "FIVER":
        return max(0, cents - 500)
    raise KeyError(code)
