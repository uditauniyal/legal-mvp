import argparse, mimetypes, sys, traceback
from pathlib import Path
from contextlib import ExitStack
import requests

URL_DEFAULT = "http://127.0.0.1:8000/ingest"

def find_files(root: Path, patterns=("*.pdf","*.docx","*.txt")):
    all_files = []
    for pat in patterns:
        all_files += list((root / "tests" / "data").rglob(pat))
    return [p.resolve() for p in all_files]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=URL_DEFAULT)
    ap.add_argument("--root", default=".")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    print(f"[DBG] Python: {sys.executable}")
    print(f"[DBG] CWD:     {Path.cwd()}")
    print(f"[DBG] Root:    {root}")
    print(f"[DBG] URL:     {args.url}")

    # 0) Health check
    try:
        h = requests.get(args.url.replace("/ingest","/healthz"), timeout=10)
        print(f"[DBG] /healthz -> {h.status_code} {h.text}")
    except Exception as e:
        print("[ERR] Could not reach FastAPI /healthz")
        traceback.print_exc(); sys.exit(2)

    # 1) Discover files
    files_on_disk = find_files(root)
    print(f"[DBG] Found {len(files_on_disk)} files:")
    for p in files_on_disk: print("      -", p)

    if not files_on_disk:
        print("[ERR] No files found under tests/data. Aborting.")
        sys.exit(3)

    # 2) Open & POST
    try:
        with ExitStack() as stack:
            form = []
            for p in files_on_disk:
                mt = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
                fh = stack.enter_context(open(p, "rb"))
                # Prove we can read
                fh.peek = fh.read(16); fh.seek(0)
                print(f"[DBG] Readable: {p.name} (first 16B: {fh.peek!r})")
                form.append(("files", (p.name, fh, mt)))
            r = requests.post(args.url, files=form, timeout=300)
        print(f"[OK ] POST /ingest -> {r.status_code}")
        print(r.text)
    except Exception:
        print("[ERR] Exception during POST /ingest")
        traceback.print_exc(); sys.exit(4)

if __name__ == "__main__":
    main()