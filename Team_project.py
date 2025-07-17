import os
import re
import datetime
import pickle
from collections import UserDict
from typing import Optional, List
from openai import OpenAI

# -------------------- Configuration --------------------

API_KEY_FILE = "key.txt"
DATA_FILE    = "addressbook.pkl"
NOTES_FILE   = "notesbook.pkl"

# -------------------- OpenAI Client --------------------

def load_api_key(path: str = API_KEY_FILE) -> str:
    """Read the OpenAI API key from a text file."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()

client = OpenAI(api_key=load_api_key())

# -------------------- Command Definitions --------------------

MAIN_COMMANDS    = ["contacts", "notes", "exit", "close"]
CONTACT_COMMANDS = [
    "hello", "add", "change", "phone", "all",
    "add-birthday", "show-birthday", "birthdays",
    "add-contact-note", "back", "exit", "close"
]
NOTE_COMMANDS    = [
    "add-note", "list-notes", "add-tag",
    "search-tag", "search-note", "back", "exit", "close"
]

# -------------------- Suggestion Logic --------------------

def suggest_correction(user_input: str, valid_cmds: List[str]) -> Optional[str]:
    """
    Use GPT-4 to map a free-form user input (Russian or English)
    to one of the exact valid command identifiers.
    """
    system_prompt = (
        "You are a CLI assistant. Supported commands are exactly:\n"
        + "\n".join(f"- {c}" for c in valid_cmds)
        + "\nThe user may phrase commands in Russian or English."
        + " If the input doesn't match exactly, return ONLY the best matching identifier."
        + " If it already exactly matches a command, return an empty string."
    )
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": f"User input: {user_input}"}
        ],
        temperature=0.0,
        max_tokens=5
    )
    suggestion = response.choices[0].message.content.strip().strip("\"'")
    return suggestion if suggestion in valid_cmds else None

# -------------------- Data Models --------------------

class Field:
    """Base class for record fields."""
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return str(self.value)

class Name(Field):
    """Mandatory contact name."""
    def __init__(self, value: str):
        if not value.strip():
            raise ValueError("Name cannot be empty.")
        super().__init__(value)

class Phone(Field):
    """Phone: exactly 10 digits."""
    def __init__(self, value: str):
        if not (value.isdigit() and len(value) == 10):
            raise ValueError("Phone must be exactly 10 digits.")
        super().__init__(value)

class Birthday(Field):
    """Birthday in DD.MM.YYYY."""
    def __init__(self, value: str):
        try:
            dt = datetime.datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError:
            raise ValueError("Invalid date format. Use DD.MM.YYYY")
        super().__init__(dt)

class Record:
    """Contact record: name, phones, birthday, and personal notes."""
    def __init__(self, name: str):
        self.name = Name(name)
        self.phones: List[Phone] = []
        self.birthday: Optional[Birthday] = None
        self.contact_notes: List[str] = []

    def add_phone(self, phone: str):
        self.phones.append(Phone(phone))

    def edit_phone(self, old: str, new: str):
        for i, p in enumerate(self.phones):
            if p.value == old:
                self.phones[i] = Phone(new)
                return
        raise ValueError(f"Phone {old} not found.")

    def add_birthday(self, bday: str):
        if self.birthday:
            raise ValueError("Birthday already set.")
        self.birthday = Birthday(bday)

    def days_to_birthday(self) -> Optional[int]:
        if not self.birthday:
            return None
        today = datetime.date.today()
        next_bd = self.birthday.value.replace(year=today.year)
        if next_bd < today:
            next_bd = next_bd.replace(year=today.year + 1)
        return (next_bd - today).days

    def add_contact_note(self, note: str):
        if not note.strip():
            raise ValueError("Note cannot be empty.")
        self.contact_notes.append(note)

    def __str__(self):
        phones = ", ".join(p.value for p in self.phones) or "no phones"
        bd     = self.birthday.value.strftime("%d.%m.%Y") if self.birthday else "no birthday"
        notes  = " | ".join(self.contact_notes) or "no contact notes"
        return f"{self.name.value}: phones[{phones}]; birthday[{bd}]; notes[{notes}]"

class AddressBook(UserDict):
    """Holds all contact Records."""
    def add_record(self, rec: Record):
        self.data[rec.name.value] = rec
    def find(self, name: str) -> Record:
        return self.data[name]
    def delete(self, name: str):
        del self.data[name]
    def get_upcoming_birthdays(self) -> dict[str, datetime.date]:
        today = datetime.date.today()
        out = {}
        for rec in self.data.values():
            d = rec.days_to_birthday()
            if d is not None and 0 <= d < 7:
                nb = rec.birthday.value.replace(year=today.year)
                if nb < today:
                    nb = nb.replace(year=today.year + 1)
                out[rec.name.value] = nb
        return out

class GeneralNote:
    """Global note with text, creation date, and tags."""
    def __init__(self, text: str, tags: List[str]):
        self.text       = text
        self.tags       = tags
        self.created_at = datetime.date.today()
    def __str__(self):
        tg = ",".join(self.tags) or "no tags"
        return f"{self.created_at.isoformat()} [{tg}]: {self.text}"

class GeneralNoteBook:
    """Holds all global (unlinked) notes."""
    def __init__(self):
        self.notes: List[GeneralNote] = []
    def add_note(self, text: str, tags: List[str]):
        self.notes.append(GeneralNote(text, tags))
    def list_notes(self) -> List[GeneralNote]:
        return self.notes
    def search_by_tag(self, tag: str) -> List[GeneralNote]:
        return [n for n in self.notes if tag in n.tags]

# -------------------- Persistence --------------------

def save_data(book: AddressBook):
    with open(DATA_FILE, "wb") as f:
        pickle.dump(book, f)

def load_data() -> AddressBook:
    try:
        with open(DATA_FILE, "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        return AddressBook()

def save_notes(gn: GeneralNoteBook):
    with open(NOTES_FILE, "wb") as f:
        pickle.dump(gn, f)

def load_notes() -> GeneralNoteBook:
    try:
        with open(NOTES_FILE, "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        return GeneralNoteBook()

# -------------------- Error Decorator --------------------

def input_error(func):
    def wrapper(parts, *args):
        try:
            return func(parts, *args)
        except ValueError as e:
            return str(e)
        except (IndexError, KeyError):
            return "Invalid command."
    return wrapper

# -------------------- Command Handlers --------------------

@input_error
def handle_contact_commands(parts, book: AddressBook):
    cmd, *args = parts
    if cmd == "hello":
        return "How can I help you with contacts?"
    if cmd == "add":
        name, phone = args
        try:
            book.find(name).add_phone(phone)
            return "Phone added to existing contact."
        except KeyError:
            rec = Record(name)
            rec.add_phone(phone)
            book.add_record(rec)
            return "New contact created."
    if cmd == "change":
        name, old, new = args
        book.find(name).edit_phone(old, new)
        return "Phone changed."
    if cmd == "phone":
        return ", ".join(p.value for p in book.find(args[0]).phones) or "No phones"
    if cmd == "all":
        return "\n".join(str(r) for r in book.data.values()) or "No contacts"
    if cmd == "add-birthday":
        name, bday = args
        book.find(name).add_birthday(bday)
        return "Birthday added."
    if cmd == "show-birthday":
        return book.find(args[0]).birthday.value.strftime("%d.%m.%Y")
    if cmd == "birthdays":
        ups = book.get_upcoming_birthdays()
        return "\n".join(f"{n}: {d.strftime('%d.%m.%Y')}" for n, d in ups.items()) or "No upcoming birthdays"
    if cmd == "add-contact-note":
        name, *note = args
        book.find(name).add_contact_note(" ".join(note))
        return "Contact note added."
    if cmd in ("back", "exit", "close"):
        return "BACK"
    return "Invalid command for contacts."

@input_error
def handle_global_notes(parts, gnbook: GeneralNoteBook):
    cmd, *args = parts
    if cmd == "add-note":
        text = args[0] if args else input("Enter note text: ")
        if not text.strip():
            raise ValueError("Note cannot be empty.")
        gnbook.add_note(text, [])
        note = gnbook.notes[-1]
        if input("Add tags? (yes/no): ").lower().startswith("y"):
            tags = [t.strip() for t in input("Tags (comma-separated): ").split(",") if t.strip()]
            note.tags.extend(tags)
            return f"Global note added with tags: {', '.join(tags)}"
        return "Global note added."
    if cmd == "list-notes":
        return "\n".join(str(n) for n in gnbook.list_notes()) or "No global notes"
    if cmd == "add-tag":
        idx, *tags = args
        gnbook.notes[int(idx) - 1].tags.extend(tags)
        return "Tags added."
    if cmd == "search-tag":
        tag = args[0] if args else input("Enter tag to search: ")
        results = gnbook.search_by_tag(tag)
        if results:
            return "\n".join(str(n) for n in results)
        return f"No notes with tag '{tag}'"
    if cmd == "search-note":
        query = args[0] if args else input("Enter search query: ")
        notes_list = [f"{i+1}: {n.text}" for i, n in enumerate(gnbook.list_notes())]
        system = (
            "You are a note search assistant. Here are the notes with indices:\n"
            + "\n".join(notes_list)
            + "\nWhen the user queries, return a comma-separated list of indices (1-based) of the best matches."
        )
        resp = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": query}
            ],
            temperature=0.0,
            max_tokens=50
        )
        idxs = [int(x) for x in re.findall(r"\d+", resp.choices[0].message.content)]
        return "\n".join(str(gnbook.notes[i - 1]) for i in idxs)
    if cmd in ("back", "exit", "close"):
        return "BACK"
    return "Invalid command for notes."

# -------------------- Main Loop --------------------

def main():
    book = load_data()
    gnbook = load_notes()
    mode = "main"

    while True:
        if mode == "main":
            choice = input("Choose mode [contacts/notes/exit]: ").strip().lower()
            if choice in ("exit", "close"):
                save_data(book)
                save_notes(gnbook)
                print("Good bye!")
                break
            if choice in ("contacts", "notes"):
                mode = choice
                continue

        if mode == "contacts":
            raw = input("Contacts> ").strip()
            if raw in ("exit", "close"):
                save_data(book); save_notes(gnbook)
                print("Good bye!")
                break
            if raw == "back":
                mode = "main"
                continue

            parts = raw.split()
            cmd = parts[0]
            if cmd not in CONTACT_COMMANDS:
                sug = suggest_correction(raw, CONTACT_COMMANDS)
                if sug and input(f"Did you mean '{sug}'? (yes/no): ").lower().startswith("y"):
                    # Prompt for required args
                    if sug == "add":
                        name = input("Enter contact name: ")
                        phone = input("Enter phone number: ")
                        parts = [sug, name, phone]
                    elif sug == "change":
                        name = input("Enter contact name: ")
                        old  = input("Enter old phone number: ")
                        new  = input("Enter new phone number: ")
                        parts = [sug, name, old, new]
                    elif sug == "phone":
                        name = input("Enter contact name: ")
                        parts = [sug, name]
                    elif sug == "all":
                        parts = [sug]
                    elif sug == "add-birthday":
                        name = input("Enter contact name: ")
                        bday = input("Enter birthday (DD.MM.YYYY): ")
                        parts = [sug, name, bday]
                    elif sug == "show-birthday":
                        name = input("Enter contact name: ")
                        parts = [sug, name]
                    elif sug == "birthdays":
                        parts = [sug]
                    elif sug == "add-contact-note":
                        name = input("Enter contact name: ")
                        note = input("Enter note for contact: ")
                        parts = [sug, name, note]
                    else:
                        parts = [sug] + parts[1:]
                else:
                    print("Invalid contacts command.")
                    continue

            res = handle_contact_commands(parts, book)
            if res == "BACK":
                mode = "main"
            else:
                print(res)

        if mode == "notes":
            raw = input("Notes> ").strip()
            if raw in ("exit", "close"):
                save_data(book); save_notes(gnbook)
                print("Good bye!")
                break
            if raw == "back":
                mode = "main"
                continue

            parts = raw.split()
            cmd = parts[0]
            if cmd not in NOTE_COMMANDS:
                sug = suggest_correction(raw, NOTE_COMMANDS)
                if sug and input(f"Did you mean '{sug}'? (yes/no): ").lower().startswith("y"):
                    if sug == "add-note":
                        text = input("Enter note text: ")
                        parts = [sug, text]
                    elif sug == "search-note":
                        query = input("Enter search query: ")
                        parts = [sug, query]
                    elif sug == "search-tag":
                        tag = input("Enter tag to search: ")
                        parts = [sug, tag]
                    else:
                        parts = [sug] + parts[1:]
                else:
                    print("Invalid notes command.")
                    continue

            res = handle_global_notes(parts, gnbook)
            if res == "BACK":
                mode = "main"
            else:
                print(res)

if __name__ == "__main__":
    main()
