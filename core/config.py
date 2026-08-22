"""Central configuration, read once from .env.

Everything the pipeline needs to know about models, providers, and
reproducibility guards lives here so that no module reads os.getenv directly
and drifts out of step with the others.

WHY THE PROVIDER PINNING MATTERS
    OpenRouter load-balances across providers by default. Two companies can
    serve the "same" model at different numerical precision, so the same code
    on the same day can produce different results. A NeurIPS 2025 paper had
    its claims invalidated by exactly this.

    So: pin the provider, forbid fallbacks, and require that the parameters
    we send are actually supported rather than silently dropped.
    See docs/DECISIONS.md.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# --- Credentials & endpoint -------------------------------------------------
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")

# --- Generation -------------------------------------------------------------
GEN_MODEL = os.getenv("MODEL_NAME", "google/gemini-3.7-flash")
GEN_PROVIDER = os.getenv("GEN_PROVIDER", "").strip() or None
GEN_TEMPERATURE = float(os.getenv("GEN_TEMPERATURE", "0"))

# --- Embeddings -------------------------------------------------------------
EMBED_MODEL = os.getenv("EMBED_MODEL", "openai/text-embedding-3-small")
EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "").strip() or None
EMBED_DIM = _int("EMBED_DIM", 1536)

# --- Reproducibility guards -------------------------------------------------
ALLOW_FALLBACKS = _bool("ALLOW_FALLBACKS", False)
REQUIRE_PARAMETERS = _bool("REQUIRE_PARAMETERS", True)
SEED = _int("SEED", 20260822)

# --- Vector store -----------------------------------------------------------
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION = os.getenv("QDRANT_COLLECTION", "legal_mvp")

# --- Retrieval --------------------------------------------------------------
TOP_K = _int("TOP_K", 15)

# --- Ingest -----------------------------------------------------------------
LANGS_OCR = os.getenv("LANGS_OCR", "eng+hin+tam+tel")
USE_TRANSLATION = _bool("USE_TRANSLATION", False)


def provider_block(provider: str | None) -> dict:
    """Build OpenRouter's `provider` routing object.

    `only`             restrict to one provider — no silent substitution
    `allow_fallbacks`  False = fail loudly instead of quietly rerouting
    `require_parameters` True = error if temperature/seed/json unsupported,
                       rather than OpenRouter deleting them from the request
    """
    block: dict = {
        "allow_fallbacks": ALLOW_FALLBACKS,
        "require_parameters": REQUIRE_PARAMETERS,
    }
    if provider:
        block["only"] = [provider]
    return block


def describe() -> dict:
    """Config snapshot for run metadata. Never includes the key."""
    return {
        "api_base": OPENAI_BASE_URL,
        "gen_model": GEN_MODEL,
        "gen_provider": GEN_PROVIDER,
        "gen_temperature": GEN_TEMPERATURE,
        "embed_model": EMBED_MODEL,
        "embed_provider": EMBED_PROVIDER,
        "embed_dim": EMBED_DIM,
        "allow_fallbacks": ALLOW_FALLBACKS,
        "require_parameters": REQUIRE_PARAMETERS,
        "seed": SEED,
        "top_k": TOP_K,
        "collection": COLLECTION,
    }


def check() -> list[str]:
    """Return a list of configuration problems, empty if all good."""
    problems = []
    if not OPENROUTER_API_KEY:
        problems.append("OPENROUTER_API_KEY is empty — paste your key into .env")
    elif not OPENROUTER_API_KEY.startswith("sk-or-"):
        problems.append(
            "OPENROUTER_API_KEY does not look like an OpenRouter key "
            "(expected it to start with 'sk-or-')"
        )
    if "/" not in EMBED_MODEL:
        problems.append(
            f"EMBED_MODEL={EMBED_MODEL!r} is missing a provider prefix; "
            "OpenRouter expects e.g. 'openai/text-embedding-3-small'"
        )
    if "/" not in GEN_MODEL:
        problems.append(
            f"MODEL_NAME={GEN_MODEL!r} is missing a provider prefix; "
            "OpenRouter expects e.g. 'google/gemini-3.7-flash'"
        )
    return problems
