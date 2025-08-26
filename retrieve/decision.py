import re

SEC_RE = re.compile(r'(?i)(section|sec)\s*(\d+[A-Za-z]?)\s*(bns|ipc|bnss|crpc|bsa|iea)?')
ART_RE = re.compile(r'(?i)(article)\s*(\d+[A-Za-z]?)\s*(constitution)?')

def normalize_code(code):
    if not code: return None
    c = code.lower()
    return {"ipc":"BNS", "bns":"BNS", "crpc":"BNSS", "bnss":"BNSS", "iea":"BSA", "bsa":"BSA"}.get(c, None)

def looks_like_case(q):
    return any(k in q for k in [" v. ", "vs.", "judgment", "appeal", "petition", "scc", "air "])

def decision_agent(query: str):
    q = query.lower()
    m = SEC_RE.search(q) or ART_RE.search(q)
    code = None; boosts = []
    if m:
        num = m.group(2)
        code = normalize_code(m.group(3)) if m.re is SEC_RE else "Constitution"
        if m.re is ART_RE and not code: code = "Constitution"
        if num:
            boosts.append(f"Section {num} {code}" if m.re is SEC_RE else f"Article {num} Constitution")
    
    if not code:
        if any(k in q for k in ["bns", "ipc"]): code = "BNS"
        elif any(k in q for k in ["bnss", "crpc", "procedure"]): code = "BNSS"
        elif any(k in q for k in ["bsa", "evidence", "iea"]): code = "BSA"
        elif any(k in q for k in ["constitution", "fundamental rights", "article "]): code = "Constitution"
        elif looks_like_case(q): code = "Judgments"

    payload_filter = {"must": [{"key":"corpus","match":{"value": code}}]} if code else None
    return {"filter": payload_filter, "boosts": boosts, "code": code}

def rewrite_query(original: str, boosts: list[str]) -> str:
    return (" ".join(boosts) + " || " if boosts else "") + original
