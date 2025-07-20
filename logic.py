# import datetime
import re
# from collections import UserDict
from typing import Optional, List, Type #Tuple
try:
    from rich.columns import Columns
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    HAVE_RICH = True
except ImportError:  # pragma: no cover - fallback for minimal envs
    HAVE_RICH = False

    class Console:
        def print(self, *args, **kwargs):
            print(*args)

        def input(self, prompt: str = "") -> str:
            return input(prompt)

    class Columns(list):
        pass

    class Panel:
        def __init__(self, renderable, title: str = "", border_style: str = ""):
            self.renderable = renderable
            self.title = title

        def __str__(self):
            return f"{self.title}\n{self.renderable}"

    class Table:
        def __init__(self, *args, **kwargs):
            self.rows = []

        def add_column(self, *args, **kwargs):
            pass

        def add_row(self, *args, **kwargs):
            self.rows.append(" | ".join(args))

        def __str__(self):
            return "\n".join(self.rows)
import getpass
from ai import client as _client
from models import GeneralNote, Field, Record, AddressBook
from storage import *
from storage import save_users

console = Console()

# ────────────────────────────────────────────────────────────────────────────
# Command dictionaries – кратко; полный список по команде help внутри режима
# ────────────────────────────────────────────────────────────────────────────
CONTACT_DESC = {
    "add": "add new contact",
    "change": "change contact name or phone or email or notes",
    "remove-phone": "remove contact`s phone",
    "delete": "delete <Name>",
    "all": "show all contacts",
    "search": "search contact by name or phone or email or notes",
    "add-birthday": "add birthday to contact",
    "show-birthday": "show contact`s birthday",
    "birthdays": "show all contacts whose birthday is in the next N days",
    "add-contact-note": "add note to contact",
    "back":  "return to mode selection",
    "exit | close":  "end assistant work",
    "hello | help": "output all commands"
}

NOTE_DESC = {
    "add-note":   "add new note",
    "list-notes": "view all notes",
    "add-tag":    "add new tags",
    "search-tag": "find a note by tag",
    "search-note":"find note by text",
    "group-notes": "find notes grouped by tags",
    "back":  "return to mode selection",
    "exit | close":  "end assistant work",
    "hello | help": "output all commands"
}

# ────────────────────────────────────────────────────────────────────────────
# GPT‑autocorrect helper
# ────────────────────────────────────────────────────────────────────────────
def suggest_correction(user_input: str,
                       desc_map: dict[str, str]) -> Optional[str]:
    """
    Просим GPT‑4o‑mini угадать опечатанную команду.
    Возвращает canonical‑имя команды или None.
    """
    if _client is None:
        return None
    sys_prompt = (
            "You are a CLI assistant that fixes mistyped commands. "
            "User may write RU/UA/EN with typos.\n\n"
            "Supported commands:\n" +
            "\n".join(desc_map.keys()) +
            "\n\nReturn ONLY the canonical command name or empty string."
    )
    resp = _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_input}
        ],
        temperature=0.0,
        max_tokens=6
    )
    guess = resp.choices[0].message.content.strip().strip("\"'")
    return guess if guess in desc_map else None

# ────────────────────────────────────────────────────────────────────────────
# simple keyword match
# ────────────────────────────────────────────────────────────────────────────
def simple_match(query: str, note: "GeneralNote") -> bool:
    q_words = {w.lower() for w in re.findall(r"\w+", query)}
    text    = note.text.lower()
    tags    = " ".join(note.tags).lower()
    return all(any(word in field for field in (text, tags)) for word in q_words)

# ────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ────────────────────────────────────────────────────────────────────────────
def ok(msg): return f"[green]✔ {msg}[/]"

def prompt_validated(prompt: str, factory: Optional[Type[Field]] = None,
                     allow_blank=True) -> str:
    while True:
        raw = console.input(prompt).strip()
        if not raw and allow_blank:
            return ""
        if factory is None:
            return raw
        try:
            factory(raw)
            return raw
        except ValueError as e:
            console.print(f"[red]{e}[/]")


def _panel_body(rec: Record, extra=""):
    phones = ", ".join(p.value for p in rec.phones) or "—"
    bday = rec.birthday.value.strftime("%d.%m.%Y") if rec.birthday else "—"
    notes_list = getattr(rec, "contact_notes", [])
    notes = " | ".join(notes_list) if notes_list else "—"
    body = (
        f"[b]📞[/b] {phones}\n"
        f"[b]📧[/b] {rec.email.value or '—'}\n"
        f"[b]📍[/b] {rec.address.value or '—'}\n"
        f"[b]🎂[/b] {bday}\n"
        f"[b]📝[/b] {notes}"
    )
    return body + (f"\n{extra}" if extra else "")


def show_records(recs: List[Record]):
    if not recs:
        console.print("[dim italic]No contacts.[/]")
        return
    console.print(Columns(
        [Panel(_panel_body(r),
               title=f"{r.name.value.upper()} {r.surname.value.upper()}".strip(), border_style="cyan")
         for r in recs],
        equal=True, expand=True))


def show_birthdays(book: AddressBook, matches):
    if not matches:
        console.print("[dim italic]No birthdays in this period.[/]\n")
        return

    ordered = sorted(matches.items(), key=lambda x: x[1][0])
    panels = []

    for key, (dt, age) in ordered:
        rec = book.data[key]
        full_name = f"{rec.name.value.title()} {rec.surname.value.title()}".strip()
        panels.append(
            Panel(
                _panel_body(rec,
                            extra=f"🎉 {dt.strftime('%d.%m.%Y')} / {age} years"),
                title=full_name,
                border_style="magenta"
            )
        )

    console.print(Columns(panels, equal=True, expand=True))



def help_msg(section="contacts"):
    mapping = CONTACT_DESC if section == "contacts" else NOTE_DESC

    table = Table(title="\n📘 Команди для роботи з нотатками", header_style="bold blue", style="bold bright_cyan")

    table.add_column("Команда", justify="center", style="bold deep_sky_blue1", no_wrap=True)
    table.add_column("Опис", justify="center", style="white")

    for cmd, desc in mapping.items():
        table.add_row(f"[green]{cmd}[/green]", desc)
    console.print(table)


def input_error(fn):
    def wrap(parts, *ctx):
        try:
            return fn(parts, *ctx)
        except (KeyError, IndexError):
            return "[red]Invalid command or args.[/]"
        except ValueError as e:
            return f"[red]{e}[/]"

    return wrap

def register(users):
    console.print("[bold yellow]===== New User Registration =====[/]")
    while True:
        username = input("Enter your login >>> ").strip()
        if username in users:
            print(f"User {username} already registered.")
        else:
            break
    password = getpass.getpass("Enter a password >>> ").strip()
    users[username] = password
    save_users(users)
    return username
def login(users):
    console.print("[bold blue]===== Login =====[/]")
    username = input("Login >>> ").strip()
    password = input("Password >>> ").strip()
    if users.get(username) == password:
        return username
    else:
        console.print(f"[dim italic]Invalid credentials. Check you login or password.[/]\n")
        return None

# ────────────────────────────────────────────────────────────────────────────
# Argument spec
# ────────────────────────────────────────────────────────────────────────────
ARG_SPEC = {
    "change_": 1, "remove-phone": 2, "phone": 1, "delete": 1,
    "add-birthday": 2, "show-birthday": 1, "add-contact-note": 2,
    "change-address": 2, "change-email": 2, "search": 1, "birthdays": 1,
    # notes
    "add-tag": 2, "search-tag": 1, "search-note": 1, "group-notes": 0
}
CONTACT_CMDS = list(CONTACT_DESC.keys())
NOTE_CMDS = list(NOTE_DESC.keys())


def collect_args(cmd):
    prompts = {
        "remove-phone": ["Contact name: ", "Phone: "],
        "phone": ["Contact name: "],
        "delete": ["Contact name: "],
        "add-birthday": ["Contact name: ", "Birthday DD.MM.YYYY: "],
        "show-birthday": ["Name or surname: "],
        "add-contact-note": ["Contact name: ", "Note: "],
        "search": ["Enter name | surname | phone | notes: "],
        "birthdays": ["Days from today (N): "],
        # notes
        "add-tag": ["Note index: ", "Tags (comma): "],
        "search-tag": ["Tag: "],
        "search-note": ["Phrase: "],
    }
    answers = [console.input(p).strip() for p in prompts.get(cmd, [])]
    if cmd == "add-tag" and len(answers) == 2:
        idx, tags = answers
        return [idx] + [t for t in re.split(r"[ ,]+", tags) if t]
    return answers