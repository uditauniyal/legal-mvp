from clients.openai_client import chat_json

def get_json_answer(messages: list[dict]) -> str:
    return chat_json(messages, max_tokens=900)
