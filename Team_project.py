import re
import datetime
import pickle
from collections import UserDict
from typing import Optional, List, Tuple, Type

# ────────────────────────────────────────────────────────────────────────────
# Rich console
# ────────────────────────────────────────────────────────────────────────────
from rich.console import Console
from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table

console = Console()

# ────────────────────────────────────────────────────────────────────────────
# Optional OpenAI (autocorrect & semantic search); can work without key.txt
# ────────────────────────────────────────────────────────────────────────────
try:
    from openai import OpenAI

    with open("key.txt", "r", encoding="utf‑8") as f:
        _client = OpenAI(api_key=f.read().strip())
except (ImportError, FileNotFoundError):
    _client = None

# ────────────────────────────────────────────────────────────────────────────
# Command dictionaries – кратко; полный список по команде help внутри режима
# ────────────────────────────────────────────────────────────────────────────
CONTACT_DESC = {
    "add":              "add <Name> [Surname] [Phone] [Email] [Address]",
    "change":           "change <Name> – заменить основной телефон",
    "remove-phone":     "remove-phone <Name> <Phone>",
    "phone":            "phone <Name>",
    "delete":           "delete <Name>",
    "all":              "all – показать все контакты",
    "search":           "search <query> – имя/фамилия/телефон/заметки",
    "add-birthday":     "add-birthday <Name> <DD.MM.YYYY>",
    "show-birthday":    "show-birthday <Name|Surname>",
    "birthdays":        "birthdays <N> – ближайшие N дней",
    "add-contact-note": "add-contact-note <Name> <Text>",
    "change-address":   "change-address <Name> <New address>",
    "change-email":     "change-email <Name> <New email>",
    "back":  "back – главное меню",
    "exit":  "exit / close – сохранить и выйти",
    "hello": "hello / help – показать помощь",
    "help":  "help – то же самое",
}

NOTE_DESC = {
    "add-note":   "add new note",
    "list-notes": "view all notes",
    "add-tag":    "add new tags",
    "search-tag": "find a note by tag",
    "search-note":"find note by text",
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
            {"role": "user",   "content": user_input}
        ],
        temperature=0.0,
        max_tokens=6
    )
    guess = resp.choices[0].message.content.strip().strip("\"'")
    return guess if guess in desc_map else None

# ────────────────────────────────────────────────────────────────────────────
# Data model
# ────────────────────────────────────────────────────────────────────────────
class Field:
    def __init__(self, value):  self.value = value
    def __str__(self):          return str(self.value)


class Name(Field):
    def __init__(self, value: str):
        if not value.strip():
            raise ValueError("Name cannot be empty.")
        super().__init__(value.strip())


class Surname(Field):  pass
class Address(Field):  pass


class Email(Field):
    EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")
    def __init__(self, value: str):
        v = value.strip()
        if v and not Email.EMAIL_RE.fullmatch(v):
            raise ValueError("Invalid e‑mail format.")
        super().__init__(v)


class Phone(Field):
    def __init__(self, value: str):
        if not value.isdigit() or len(value) != 10:
            raise ValueError("Phone must contain exactly 10 digits.")
        super().__init__(value)


class Birthday(Field):
    def __init__(self, value: str):
        try:
            dt = datetime.datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError:
            raise ValueError("Date must be DD.MM.YYYY")
        if dt > datetime.date.today():
            raise ValueError("Birthday cannot be in the future.")
        super().__init__(dt)


class Record:
    def __init__(self, name: str, surname: str = "", address: str = "", email: str = ""):
        self.name = Name(name)
        self.surname = Surname(surname)
        self.address = Address(address)
        self.email = Email(email)
        self.phones: List[Phone] = []
        self.birthday: Optional[Birthday] = None
        self.contact_notes: List[str] = []

    # phone ops
    def add_phone(self, phone: str):           self.phones.append(Phone(phone))
    def remove_phone(self, phone: str):        self.phones = [p for p in self.phones if p.value != phone]
    def edit_phone(self, idx: int, new: str):  self.phones[idx] = Phone(new)

    # misc
    def add_birthday(self, date_str: str):
        if self.birthday:
            raise ValueError("Birthday already set.")
        self.birthday = Birthday(date_str)
    def add_contact_note(self, note: str):
        if not note.strip():
            raise ValueError("Note cannot be empty.")
        self.contact_notes.append(note.strip())
    def update_email(self, email: str):        self.email = Email(email)
    def update_address(self, addr: str):       self.address = Address(addr)


class AddressBook(UserDict):
    def add_record(self, rec: Record): self.data[rec.name.value.lower()] = rec
    def find(self, name: str) -> Record: return self.data[name.lower()]
    def delete(self, name: str): del self.data[name.lower()]

    # --- главное: ближайшие ДР ---
    def upcoming(self, days_ahead: int) -> dict[str, Tuple[datetime.date, int]]:
        """
        Вернуть {name: (next_date, age_turning)} для контактов,
        у которых ближайший ДР в интервале [0, days_ahead] от сегодня.
        """
        today = datetime.date.today()
        result: dict[str, Tuple[datetime.date, int]] = {}

        for rec in self.data.values():
            if not rec.birthday:
                continue
            month, day = rec.birthday.value.month, rec.birthday.value.day
            year = today.year
            # ближайшая дата ДР
            try:
                next_bd = datetime.date(year, month, day)
            except ValueError:                 # 29 фев на невисокосный
                next_bd = datetime.date(year, 2, 28)
            if next_bd < today:                # уже прошёл – берём след. год
                try:
                    next_bd = datetime.date(year + 1, month, day)
                except ValueError:
                    next_bd = datetime.date(year + 1, 2, 28)
            delta = (next_bd - today).days
            if 0 <= delta <= days_ahead:
                result[rec.name.value] = (next_bd, next_bd.year - rec.birthday.value.year)

        return result

# ────────────────────────────────────────────────────────────────────────────
# Notes
# ────────────────────────────────────────────────────────────────────────────
class GeneralNote:
    def __init__(self, text: str, tags: List[str]):
        self.text = text.strip()
        self.tags = tags
        self.created_at = datetime.date.today()
    def __str__(self):
        tags = ",".join(self.tags) or "no tags"
        return f"{self.created_at.isoformat()} [{tags}]: {self.text}"


class GeneralNoteBook:
    def __init__(self): self.notes: List[GeneralNote] = []
    def add_note(self, text: str, tags: List[str]): self.notes.append(GeneralNote(text, tags))
    def list_notes(self): return self.notes
    def search_by_tag(self, tag: str): return [n for n in self.notes if tag in n.tags]


# ────────────────────────────────────────────────────────────────────────────
# Persistence
# ────────────────────────────────────────────────────────────────────────────
DATA_FILE, NOTES_FILE = "addressbook.pkl", "notesbook.pkl"
def _save(obj, path): pickle.dump(obj, open(path, "wb"))
def _load(path, factory):
    try:    return pickle.load(open(path, "rb"))
    except (FileNotFoundError, pickle.PickleError): return factory()
def load_data():  return _load(DATA_FILE, AddressBook)
def load_notes(): return _load(NOTES_FILE, GeneralNoteBook)
def save_data(ab):  _save(ab, DATA_FILE)
def save_notes(nb): _save(nb, NOTES_FILE)


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
    body = f"[b]📞[/b] {phones}\n[b]📧[/b] {rec.email.value or '—'}\n[b]📍[/b] {rec.address.value or '—'}\n[b]🎂[/b] {bday}"
    return body + (f"\n{extra}" if extra else "")

def show_records(recs: List[Record]):
    if not recs:
        console.print("[dim]No contacts.[/]")
        return
    console.print(Columns(
        [Panel(_panel_body(r),
               title=f"{r.name.value.upper()} {r.surname.value.upper()}".strip(), border_style="cyan")
         for r in recs],
        equal=True, expand=True))

def show_birthdays(book: AddressBook, matches):
    if not matches:
        console.print("🎉 No birthdays in this period.")
        return
    ordered = sorted(matches.items(), key=lambda x: (x[1][0]))
    console.print(Columns([
        Panel(_panel_body(book.find(name),
                          extra=f"🎂 {dt.strftime('%d.%m.%Y')} / {age} y"),
              title=name, border_style="magenta")
        for name, (dt, age) in ordered],
        equal=True, expand=True))

def help_msg(section="contacts"):
    mapping = CONTACT_DESC if section == "contacts" else NOTE_DESC
    # console.print()
    # for cmd, desc in mapping.items():
    #     console.print(f"[cyan bold]{cmd}[/]  {desc}")

    table = Table(title="\n📘 Команди для роботи з нотатками", header_style="bold blue", style="bold bright_cyan")

    table.add_column("Команда", justify="center", style="bold deep_sky_blue1", no_wrap=True)
    table.add_column("Опис", justify="center", style="white")

    for cmd, desc in mapping.items():
        table.add_row(f"[green]{cmd}[/green]", desc)
    console.print(table)

def input_error(fn):
    def wrap(parts, *ctx):
        try:    return fn(parts, *ctx)
        except (KeyError, IndexError):
            return "[red]Invalid command or args.[/]"
        except ValueError as e:
            return f"[red]{e}[/]"
    return wrap


# ────────────────────────────────────────────────────────────────────────────
# Argument spec
# ────────────────────────────────────────────────────────────────────────────
ARG_SPEC = {
    "change": 1, "remove-phone": 2, "phone": 1, "delete": 1,
    "add-birthday": 2, "show-birthday": 1, "add-contact-note": 2,
    "change-address": 2, "change-email": 2, "search": 1, "birthdays": 1,
    # notes
    "add-tag": 2, "search-tag": 1, "search-note": 1,
}
CONTACT_CMDS = list(CONTACT_DESC.keys())
NOTE_CMDS = list(NOTE_DESC.keys())

def collect_args(cmd):
    prompts = {
        "change": ["Contact name: ", "New phone (10 digits): "],
        "remove-phone": ["Contact name: ", "Phone: "],
        "phone": ["Contact name: "],
        "delete": ["Contact name: "],
        "add-birthday": ["Contact name: ", "Birthday DD.MM.YYYY: "],
        "show-birthday": ["Name or surname: "],
        "add-contact-note": ["Contact name: ", "Note: "],
        "change-address": ["Contact name: ", "New address: "],
        "change-email": ["Contact name: ", "New email: "],
        "search": ["Query: "],
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


# ────────────────────────────────────────────────────────────────────────────
# Handlers
# ────────────────────────────────────────────────────────────────────────────
@input_error
def handle_contact(parts, ab: AddressBook):
    cmd, *args = parts
    if cmd in ("hello", "help"):
        return help_msg("contacts")

    # add/update
    if cmd == "add":
        if not args:
            name = prompt_validated("Enter name: ", allow_blank=False)
            surname = prompt_validated("Enter surname: ")
            phone = prompt_validated("Enter phone (10 digits): ", Phone)
            email = prompt_validated("Enter email: ", Email)
            address = prompt_validated("Enter address: ")
        else:
            name, *rest = args
            surname = rest[0] if rest else ""
            phone = rest[1] if len(rest) > 1 else ""
            email = rest[2] if len(rest) > 2 else ""
            address = " ".join(rest[3:]) if len(rest) > 3 else ""
        rec = ab.data.get(name.lower())
        if rec:
            if phone: rec.add_phone(phone)
            if surname: rec.surname = Surname(surname)
            if email: rec.email = Email(email)
            if address: rec.address = Address(address)
            return ok("Contact updated.")
        rec = Record(name, surname, address, email)
        if phone: rec.add_phone(phone)
        ab.add_record(rec)
        return ok("Contact added.")

    # phone change
    if cmd == "change":
        if len(args) == 1:
            name = args[0]
            new = prompt_validated("New phone (10 digits): ", Phone, allow_blank=False)
        else:
            name, new = args
        rec = ab.find(name)
        if not rec.phones:
            rec.add_phone(new)
            return ok("Phone added.")
        if len(rec.phones) == 1:
            rec.edit_phone(0, new)
            return ok("Phone updated.")
        console.print("Multiple phones:")
        for i, p in enumerate(rec.phones, 1):
            console.print(f"{i}. {p.value}")
        idx = int(console.input("Select index to replace: "))
        if not 1 <= idx <= len(rec.phones):
            raise ValueError("Invalid index.")
        rec.edit_phone(idx - 1, new)
        return ok("Phone updated.")

    if cmd == "remove-phone":
        name, phone = args
        ab.find(name).remove_phone(phone)
        return ok("Phone removed.")
    if cmd == "phone":
        name, = args
        return ", ".join(p.value for p in ab.find(name).phones) or "No phones."
    if cmd == "delete":
        name, = args
        ab.delete(name)
        return ok("Contact deleted.")

    # search/list
    if cmd == "all":
        show_records(list(ab.data.values()))
        return ""
    if cmd == "search":
        q, = args
        hits = [r for r in ab.data.values()
                if q.lower() in r.name.value.lower()
                or q.lower() in r.surname.value.lower()
                or any(q in p.value for p in r.phones)
                or any(q.lower() in note.lower() for note in r.contact_notes)]
        show_records(hits)
        return ""

    # birthdays
    if cmd == "add-birthday":
        name, date = args
        ab.find(name).add_birthday(date)
        return ok("Birthday added.")
    if cmd == "show-birthday":
        key, = args
        matches = [r for r in ab.data.values()
                   if key.lower() in (r.name.value.lower(), r.surname.value.lower())]
        if not matches:
            raise KeyError("Contact not found.")
        return "\n".join(f"{r.name.value} {r.surname.value}: "
                         f"{r.birthday.value.strftime('%d.%m.%Y') if r.birthday else '—'}"
                         for r in matches)
    if cmd == "birthdays":
        days, = args
        if not days.isdigit():
            raise ValueError("Enter non‑negative integer.")
        matches = ab.upcoming(int(days))
        show_birthdays(ab, matches)
        return ""

    # misc
    if cmd == "add-contact-note":
        name, *note = args
        ab.find(name).add_contact_note(" ".join(note))
        return ok("Note added.")
    if cmd == "change-address":
        name, *addr = args
        ab.find(name).update_address(" ".join(addr))
        return ok("Address updated.")
    if cmd == "change-email":
        name, email = args
        ab.find(name).update_email(email)
        return ok("Email updated.")

    if cmd in ("back", "exit", "close"):
        return "BACK"
    return "Unknown contact command."

@input_error
def handle_notes(parts, nb: GeneralNoteBook):
    cmd, *args = parts
    if cmd in ("hello", "help"):
        return help_msg("notes")
    if cmd == "add-note":
        text = " ".join(args) if args else console.input("Text: ")
        if not text.strip():
            raise ValueError("Empty note.")
        nb.add_note(text, [])
        if console.input("Add tags? (y/n): ").lower().startswith("y"):
            tags = re.split(r"[ ,]+", console.input("Tags: "))
            nb.notes[-1].tags.extend([t for t in tags if t])
        return ok("Note saved.")
    if cmd == "list-notes":
        console.print("\n".join(str(n) for n in nb.list_notes()) or "No notes.")
        return ""
    if cmd == "add-tag":
        idx, *tags = args
        nb.notes[int(idx)-1].tags.extend(tags)
        return ok("Tags added.")
    if cmd == "search-tag":
        tag = args[0] if args else console.input("Tag: ")
        res = nb.search_by_tag(tag)
        console.print("\n".join(str(n) for n in res) or f"No notes with tag '{tag}'.")
        return ""
    if cmd == "search-note":
        query = " ".join(args) if args else console.input("Query: ")
        if _client is None:
            return "Semantic search disabled."
        cat = [f"{i+1}: {n.text}" for i, n in enumerate(nb.notes)]
        sys_msg = "Notes:\n" + "\n".join(cat) + "\nReturn indices of best matches."
        resp = _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":sys_msg},
                      {"role":"user","content":query}],
            temperature=0.0,max_tokens=20)
        ids = [int(x) for x in re.findall(r"\d+", resp.choices[0].message.content)]
        console.print("\n".join(str(nb.notes[i-1]) for i in ids) if ids else "No matches.")
        return ""
    if cmd in ("back", "exit", "close"):
        return "BACK"
    return "Unknown note command."


# ────────────────────────────────────────────────────────────────────────────
# Main loop
# ────────────────────────────────────────────────────────────────────────────
def main():
    ab, nb, mode = load_data(), load_notes(), "main"
    console.print("\nWellcome to [bold yellow]SYTObook[/] – your personal contacts and notes assistant 🤖\n")

    if _client is None:
        console.print("[yellow]AI functions disabled (no key.txt).[/]")

    while True:
        try:
            # main menu
            if mode == "main":
                choice = console.input("\n[bold]Choose a mode > [orchid]contacts[/] | [navajo_white1]notes[/] or exit:[/] ").strip().lower()
                if choice in ("exit", "close"):
                    save_data(ab); save_notes(nb)
                    console.print(ok("Data saved. Bye!")); break
                if choice in ("contacts", "notes"):
                    mode = choice
                    help_msg(mode)
                    continue
                console.print("Unknown mode.")
                continue

            # contacts
            if mode == "contacts":
                raw = console.input("\n[bold italic][orchid]Contacts[/]>>> Command :[/]").strip()
                if raw in ("exit", "close"):
                    save_data(ab); save_notes(nb); console.print(ok("Data saved. Bye!")); break
                if raw == "back": mode = "main"; continue
                parts = raw.split()
                if not parts: continue
                cmd = parts[0]
                if cmd not in CONTACT_CMDS:
                    sug = suggest_correction(raw, CONTACT_DESC)
                    if sug and console.input(f"Did you mean '{sug}'? (y/n): ").lower().startswith("y"):
                        parts = [sug] + collect_args(sug)
                    else:
                        console.print("Unknown command."); continue
                need = ARG_SPEC.get(parts[0], 0)
                if len(parts) - 1 < need: parts += collect_args(parts[0])
                res = handle_contact(parts, ab)
                if res == "BACK": mode = "main"
                elif res: console.print(res)

            # notes
            if mode == "notes":
                raw = console.input("\n[italic][navajo_white1]Notes[/]>>> Command :[/]").strip()
                if raw in ("exit", "close"):
                    save_data(ab); save_notes(nb); console.print(ok("Data saved. Bye!")); break
                if raw == "back": mode = "main"; continue
                parts = raw.split()
                if not parts: continue
                cmd = parts[0]
                if cmd not in NOTE_CMDS:
                    sug = suggest_correction(raw, NOTE_DESC)
                    if sug and console.input(f"Did you mean '{sug}'? (y/n): ").lower().startswith("y"):
                        parts = [sug] + collect_args(sug)
                    else:
                        console.print("Unknown command."); continue
                need = ARG_SPEC.get(parts[0], 0)
                if len(parts) - 1 < need: parts += collect_args(parts[0])
                res = handle_notes(parts, nb)
                if res == "BACK": mode = "main"
                elif res: console.print(res)

        except KeyboardInterrupt:
            console.print("\nInterrupted. Saving …")
            save_data(ab); save_notes(nb); break


if __name__ == "__main__":
    main()
