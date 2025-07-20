try:
    from openai import OpenAI
    with open("key.txt", "r", encoding="utf-8") as f:
        client = OpenAI(api_key=f.read().strip())
except (ImportError, FileNotFoundError):
    client = None
