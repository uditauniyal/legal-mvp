import re
from langdetect import detect

SENT_SPLIT = re.compile(r'(?<=[.?!])\s+')

def chunk_page(doc_name, page, text, target_tokens=450, overlap_sentences=1):
    sents = [s.strip() for s in SENT_SPLIT.split(text) if s.strip()]
    chunks, cur, cur_len = [], [], 0

    def tokens(x): 
        return max(1, len(x.split()))

    for s in sents:
        if cur_len + tokens(s) > target_tokens and cur:
            chunks.append(" ".join(cur))
            cur = cur[-overlap_sentences:] if overlap_sentences else []
            cur_len = sum(tokens(x) for x in cur)
        cur.append(s)
        cur_len += tokens(s)

    if cur: 
        chunks.append(" ".join(cur))

    out = []
    for idx, c in enumerate(chunks):
        lang = "en"
        try: 
            lang = detect(c)
        except: 
            pass

        out.append({
            "doc_name": doc_name,
            "page": page,
            "chunk_index": idx,
            "chunk_id": f"{doc_name}:{page}:{idx:03d}",
            "text": c,
            "corpus": guess_corpus(doc_name, c),
            "lang_detected": lang
        })
    return out


def guess_corpus(doc_name, text):
    n = (doc_name + " " + text[:200]).lower()
    if any(k in n for k in ["bns", "nyaya", "ipc"]): 
        return "BNS"
    if any(k in n for k in ["bnss", "crpc", "procedure"]): 
        return "BNSS"
    if any(k in n for k in ["bsa", "evidence", "iea"]): 
        return "BSA"
    if any(k in n for k in ["constitution", "article "]): 
        return "Constitution"
    if any(k in n for k in [" v. ", "scc", "air ", "judgment", "appeal"]): 
        return "Judgments"
    return "Unknown"
