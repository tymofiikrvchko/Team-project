from typing import Optional
from rich.console import Console

console = Console()

def make_key(name: str, surname: str = "") -> str:
    return f"{name} {surname}".strip().lower()

def make_key_from_input(fullname: str) -> str:
    parts = fullname.strip().split(maxsplit=1)
    return make_key(*parts)

