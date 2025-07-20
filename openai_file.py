
# ────────────────────────────────────────────────────────────────────────────
# Optional OpenAI (autocorrect & semantic search); can work without key.txt
# ────────────────────────────────────────────────────────────────────────────
try:
    from openai import OpenAI

    with open("key.txt", "r", encoding="utf‑8") as f:
        _client = OpenAI(api_key=f.read().strip())
except (ImportError, FileNotFoundError):
    _client = None