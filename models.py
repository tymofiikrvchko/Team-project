import datetime
import datetime
import re
from typing import Optional, List, Tuple, Type
from collections import UserDict

__all__ = [
    'Field', 'Name', 'Surname', 'Address', 'Email', 'Phone', 'Birthday',
    'Record', 'AddressBook', 'GeneralNote', 'GeneralNoteBook',
    'get_record_key', 'make_key', 'make_key_from_input', 'group_notes_by_tag'
]

def make_key(name: str, surname: str = "") -> str:
    return f"{name} {surname}".strip().lower()


def make_key_from_input(fullname: str) -> str:
    parts = fullname.strip().split(maxsplit=1)
    return make_key(*parts)


def get_record_key(name: str, book: 'AddressBook') -> Optional[str]:
    name_parts = name.strip().split(maxsplit=1)
    if not name_parts:
        return None

    matches = [k for k in book.data if all(part.lower() in k for part in name_parts)]
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        print("Multiple matches found:")
        for i, k in enumerate(matches, 1):
            print(f"{i}. {k.title()}")
        idx = input("Select number >>> ").strip()
        if idx.isdigit() and 1 <= int(idx) <= len(matches):
            return matches[int(idx) - 1]
    return None



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
        self.address = address if isinstance(address, Address) else Address(address)
        self.email = email if isinstance(email, Email) else Email(email)
        self.phones: List[Phone] = []
        self.birthday: Optional[Birthday] = None
        self.contact_notes: List[str] = []

    # phone ops
    def add_phone(self, phone: str):
        self.phones.append(Phone(phone))

    def remove_phone(self, phone: str):
        self.phones = [p for p in self.phones if p.value != phone]

    def edit_phone(self, idx: int, new: str):
        self.phones[idx] = Phone(new)

    # misc
    def add_birthday(self, date_str: str):
        if self.birthday:
            raise ValueError("Birthday already set.")
        self.birthday = Birthday(date_str)

    def add_contact_note(self, note: str):
        if not note.strip():
            raise ValueError("Note cannot be empty.")
        self.contact_notes.append(note.strip())

    def update_email(self, email: str):
        self.email = Email(email)

    def update_address(self, addr: str):
        self.address = Address(addr)


class AddressBook(UserDict):
    def add_record(self, rec: Record):
        key = make_key(rec.name.value, rec.surname.value)
        self.data[key] = rec

    def find(self, name: str) -> Record:
        key = get_record_key(name, self)
        if key is None:
            raise KeyError("Contact not found.")
        return self.data[key]

    def delete(self, name: str):
        del self.data[make_key_from_input(name)]

    def upcoming(self, days_ahead: int) -> dict[str, tuple[datetime.date, int]]:

        today = datetime.date.today()
        result = {}

        for key, rec in self.data.items():
            if not rec.birthday:
                continue

            month, day = rec.birthday.value.month, rec.birthday.value.day
            year = today.year
            try:
                next_bd = datetime.date(year, month, day)
            except ValueError:
                next_bd = datetime.date(year, 2, 28)
            if next_bd < today:
                try:
                    next_bd = datetime.date(year + 1, month, day)
                except ValueError:
                    next_bd = datetime.date(year + 1, 2, 28)

            delta = (next_bd - today).days
            if 0 <= delta <= days_ahead:
                result[key] = (next_bd, next_bd.year - rec.birthday.value.year)

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
        tags = ", ".join(self.tags) if self.tags else "—"
        return f"{self.created_at.isoformat()}   [{tags}]   {self.text}"


class GeneralNoteBook:
    def __init__(self): self.notes: List[GeneralNote] = []

    def add_note(self, text: str, tags: List[str]): self.notes.append(GeneralNote(text, tags))

    def list_notes(self): return self.notes

    def search_by_tag(self, tag: str): return [n for n in self.notes if tag in n.tags]

def group_notes_by_tag(notes: list["GeneralNote"]) -> dict[str, list["GeneralNote"]]:
    from collections import defaultdict
    groups: dict[str, list[GeneralNote]] = defaultdict(list)
    for n in notes:
        if n.tags:
            for t in n.tags:
                groups[t.lower()].append(n)
        else:
            groups["—"].append(n)
    return dict(sorted(groups.items()))