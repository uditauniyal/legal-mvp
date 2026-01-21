import fitz
from pathlib import Path

files = [
    "tests/data/repealedfileopen.pdf",
    "tests/data/a2019-35.pdf",
    "tests/data/the_code_of_criminal_procedure,_1973.pdf"
]

print("--- PDF Content Inspection ---")
for f_path in files:
    path = Path(f_path)
    print(f"\nChecking: {path}")
    if not path.exists():
        print("  [MISSING] File not found.")
        continue
    
    try:
        doc = fitz.open(path)
        if doc.page_count > 0:
            text = doc.load_page(0).get_text("text")[:500] # First 500 chars
            print(f"  [Header Text]:\n{text.replace('\n', ' ')}")
            
            # Simple keyword check for BNS
            full_text_sample = "".join([doc.load_page(i).get_text("text") for i in range(min(5, doc.page_count))]).lower()
            if "bharatiya nyaya" in full_text_sample or "bns" in full_text_sample:
                 print("  >>> LOOKS LIKE BNS! <<<")
            elif "consumer protection" in full_text_sample:
                 print("  >>> LOOKS LIKE CONSUMER PROTECTION ACT <<<")
            elif "criminal procedure" in full_text_sample:
                 print("  >>> LOOKS LIKE CrPC <<<")

    except Exception as e:
        print(f"  [ERROR] {e}")
