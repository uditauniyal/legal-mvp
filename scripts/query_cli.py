# scripts/query_cli.py
import sys
import requests
import json

URL = "http://127.0.0.1:8000/query"

def ask(query_text: str):
    payload = {"query": query_text}
    try:
        r = requests.post(URL, json=payload)
        if r.status_code == 200:
            data = r.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"Error {r.status_code}: {r.text}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    # Case 1: Query passed as arguments
    if len(sys.argv) > 1:
        query_text = " ".join(sys.argv[1:])
        print(f"\nQuerying with: {query_text}\n")
        ask(query_text)
        sys.exit(0)

    # Case 2: No arguments → interactive mode
    print("🔎 Interactive Legal Query CLI")
    print("Type your question and press Enter. Type 'exit' or 'quit' to leave.\n")

    while True:
        try:
            query = input("❓ Ask: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break
        if query.lower() in ("exit", "quit"):
            print("👋 Goodbye!")
            break
        if not query:
            continue
        print(f"\nQuerying with: {query}\n")
        ask(query)
        print("\n" + "="*80 + "\n")
