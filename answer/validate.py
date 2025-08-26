import json
from clients.openai_client import chat_json

REPAIR_SYS = "You output JSON only. Do not include any extra text."
REPAIR_USER = "Repair the following into valid JSON only, keeping the same keys and content:\n\n{}"

def parse_or_repair(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        repaired = chat_json([
            {"role": "system", "content": REPAIR_SYS},
            {"role": "user", "content": REPAIR_USER.format(raw)}
        ], max_tokens=900)
        return json.loads(repaired)
