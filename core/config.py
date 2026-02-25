import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
GEN_MODEL   = os.getenv("MODEL_NAME") or os.getenv("GEN_MODEL", "gpt-4o-mini")
QDRANT_URL  = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
TOP_K = int(os.getenv("TOP_K", "8"))
USE_TRANSLATION = os.getenv("USE_TRANSLATION", "false").lower() == "true"
LANGS_OCR = os.getenv("LANGS_OCR", "eng+hin+tam+tel")
