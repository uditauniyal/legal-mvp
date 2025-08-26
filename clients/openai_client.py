from openai import OpenAI
from core.config import EMBED_MODEL, GEN_MODEL

client = OpenAI()

def embed_texts(texts: list[str]) -> list[list[float]]:
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]

def chat_json(messages: list[dict], max_tokens=800):
    return client.chat.completions.create(
        model=GEN_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=messages,
        max_tokens=max_tokens
    ).choices[0].message.content
