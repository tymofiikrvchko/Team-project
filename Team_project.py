import re
import datetime
import pickle
from collections import UserDict
from typing import Optional, List

# ---- Rich UI ----
from rich.console import Console
from rich.columns import Columns
from rich.panel import Panel

console = Console()

# -------------------- Field Classes --------------------
class Field:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class Name(Field):
    def __init__(self, value: str):
        if not value.strip():
            raise ValueError("Name cannot be empty.")
        super().__init__(value.strip())


class Surname(Field):
    def __init__(self, value: str):
        super().__init__(value.strip())


class Address(Field):
    def __init__(self, value: str):
        super().__init__(value.strip())


class Email(Field):
    EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")

    def __init__(self, value: str):
        if value and not Email.EMAIL_RE.fullmatch(value.strip()):
            raise ValueError("Invalid e‑mail format.")
        super().__init__(value.strip())


class Phone(Field):
    def __init__(self, value: str):
        if not value.isdigit() or len(value) != 10:
            raise ValueError("Phone number must contain exactly 10 digits.")
        super().__init__(value)


class Birthday(Field):
    def __init__(self, value: str):
        try:
            dt = datetime.datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError:
            raise ValueError("Invalid date format. Use DD.MM.YYYY")
        super().__init__(dt)

# -------------------- Record & AddressBook --------------------
class Record:
    def __init__(
        self,
        name: str,
        surname: str = "",
        phone: str = "",
        email: str = "",
        address: str = "",
        birthday: str = "",
    ):
        self.name = Name(name)
        self.surname = Surname(surname)
        self.address = Address(address)
        self.email = Email(email)
        self.phones: List[Phone] = []
        if phone:
            self.add_phone(phone)
        self.birthday: Optional[Birthday] = None
        if birthday:
            self.add_birthday(birthday)

    # ---- phone helpers ----
    def add_phone(self, phone: str) -> None:
        self.phones.append(Phone(phone))

    def edit_phone(self, old: str, new: str) -> None:
        for i, p in enumerate(self.phones):
            if p.value == old:
                self.phones[i] = Phone(new)
                return
        raise ValueError(f"Phone {old} not found.")

    def remove_phone(self, phone: str) -> None:
        self.phones = [p for p in self.phones if p.value != phone]

    # ---- other helpers ----
    def add_birthday(self, bday_str: str) -> None:
        if self.birthday:
            raise ValueError("Birthday already set.")
        self.birthday = Birthday(bday_str)

    def days_to_birthday(self) -> Optional[int]:
        if not self.birthday:
            return None
        today = datetime.date.today()
        next_bday = self.birthday.value.replace(year=today.year)
        if next_bday < today:
            next_bday = next_bday.replace(year=today.year + 1)
        return (next_bday - today).days

    # ---- printable ----
    def __str__(self):
        phones = ", ".join(p.value for p in self.phones) or "—"
        bday = (
            self.birthday.value.strftime("%d.%m.%Y")
            if self.birthday else "—"
        )
        parts = [
            f"{self.name.value} {self.surname.value}".strip(),
            f"📞 {phones}",
            f"📧 {self.email.value or '—'}",
            f"📍 {self.address.value or '—'}",
            f"🎂 {bday}",
        ]
        return "; ".join(parts)


class AddressBook(UserDict):
    def add_record(self, record: Record) -> None:
        self.data[record.name.value.lower()] = record

    def find(self, name: str) -> Record:
        return self.data[name.lower()]

    def delete(self, name: str) -> None:
        del self.data[name.lower()]

    def get_upcoming_birthdays(self) -> dict[str, datetime.date]:
        today = datetime.date.today()
        upcoming: dict[str, datetime.date] = {}
        for rec in self.data.values():
            days = rec.days_to_birthday()
            if days is not None and 0 <= days < 7:
                next_bday = rec.birthday.value.replace(year=today.year)
                if next_bday < today:
                    next_bday = next_bday.replace(year=today.year + 1)
                upcoming[rec.name.value] = next_bday
        return upcoming

# -------------------- Persistence --------------------
DATA_FILE = "addressbook.pkl"

def save_data(book: AddressBook, filename: str = DATA_FILE) -> None:
    with open(filename, "wb") as f:
        pickle.dump(book, f)

def load_data(filename: str = DATA_FILE) -> AddressBook:
    try:
        with open(filename, "rb") as f:
            return pickle.load(f)
    except (FileNotFoundError, pickle.PickleError):
        return AddressBook()

# -------------------- Decorator --------------------
def input_error(func):
    def wrapper(args, book):
        try:
            return func(args, book)
        except IndexError:
            return "[italic red]❗ Not enough arguments.[/]"
        except KeyError:
            return "[italic red]❗ Contact not found.[/]"
        except ValueError as e:
            return f"[italic red]❗ {e}[/]"
    return wrapper

# -------------------- Helpers for Rich output --------------------
def display_contacts(records):
    if not records:
        console.print("[dim italic]📭 No contacts to display.[/]")
        return
    panels = []
    for rec in records:
        phones = ", ".join(p.value for p in rec.phones) or "—"
        bday = rec.birthday.value.strftime("%d.%m.%Y") if rec.birthday else "—"
        body = (
            f"[b]📞[/b] {phones}\n"
            f"[b]📧[/b] {rec.email.value if rec.email else '—'}\n"
            f"[b]📍[/b] {rec.address.value if rec.email else '—'}\n"
            f"[b]🎂[/b] {bday}"
        )
        title = f"👤 {rec.name.value.upper()} {rec.surname.value.upper()}"
        panels.append(Panel(body, title=title.strip(), border_style="cyan", expand=False))
    console.print(Columns(panels, equal=True, expand=True))

# -------------------- Command Handlers --------------------
@input_error
def add_contact(args, book: AddressBook):
    """
    add <Name> [Surname] [Phone] [Email] [Address]
    Если аргументов нет – запускается пошаговый ввод.
    """
    if not args:                          # interactive mode
        name = console.input("Name*: ").strip()
        surname = console.input("Surname: ").strip()
        phone = console.input("Phone (10 digits): ").strip()
        email = console.input("Email: ").strip()
        address = console.input("Address: ").strip()
    else:                                 # CLI mode
        name = args[0]
        surname = args[1] if len(args) > 1 else ""
        phone = args[2] if len(args) > 2 else ""
        email = args[3] if len(args) > 3 else ""
        address = " ".join(args[4:]) if len(args) > 4 else ""
    try:
        record = book.find(name)
        # обновляем существующий
        if phone:
            record.add_phone(phone)
        if surname:
            record.surname = Surname(surname)
        if email:
            record.email = Email(email)
        if address:
            record.address = Address(address)
        msg = "updated"
    except KeyError:
        record = Record(name, surname, phone, email, address)
        book.add_record(record)
        msg = "added"
    return f"[green]✔ Contact {msg}![/]"

@input_error
def change_contact(args, book: AddressBook):
    """
    change <Name> phone <old> <new>
    change <Name> email <new>
    change <Name> address <new address ...>
    change <Name> surname <new>
    """
    name = args[0]
    field = args[1].lower()
    record = book.find(name)
    if field == "phone":
        old, new = args[2], args[3]
        record.edit_phone(old, new)
        return "[green]✔ Phone updated.[/]"
    elif field == "email":
        record.email = Email(args[2])
        return "[green]✔ Email updated.[/]"
    elif field == "address":
        record.address = Address(" ".join(args[2:]))
        return "[green]✔ Address updated.[/]"
    elif field == "surname":
        record.surname = Surname(args[2])
        return "[green]✔ Surname updated.[/]"
    else:
        raise ValueError("Unknown field. Use phone / email / address / surname.")

@input_error
def delete_contact(args, book: AddressBook):
    name = args[0]
    book.delete(name)
    return f"[green]✔ Contact {name.upper()} deleted.[/]"

@input_error
def search_handler(args, book: AddressBook):
    query = args[0].lower()
    results = []
    for rec in book.data.values():
        if query in rec.name.value.lower() or any(query in p.value for p in rec.phones):
            results.append(rec)
    if not results:
        return "[italic]🔍 No matches.[/]"
    return results

@input_error
def show_all_handler(args, book: AddressBook):
    if not book.data:
        return "[italic]📭 Address book is empty.[/]"
    return list(book.data.values())

@input_error
def add_birthday(args, book: AddressBook):
    name, bday = args
    rec = book.find(name)
    rec.add_birthday(bday)
    return "[green]✔ Birthday added.[/]"

@input_error
def show_birthday(args, book: AddressBook):
    name = args[0]
    rec = book.find(name)
    if rec.birthday:
        return f"[bold]{rec.birthday.value.strftime('%d.%m.%Y')}[/]"
    return "[italic]🎂 Birthday not set.[/]"

@input_error
def birthdays(args, book: AddressBook):
    upcoming = book.get_upcoming_birthdays()
    if not upcoming:
        return "[italic]🎉 No birthdays this week.[/]"
    lines = [
        f"[bold]{n.upper()}[/] – {dt.strftime('%d.%m.%Y')}"
        for n, dt in upcoming.items()
    ]
    return "\n".join(lines)

def help_message():
    cmds = {
        "add": "add <Ім'я> [Прізвище] [Телефон] [Email] [Адреса] — додати / оновити контакт",
        "change": "change <Ім'я> <поле> ... — змінити phone / email / address / surname",
        "delete": "delete <Ім'я> — видалити контакт",
        "search": "search <рядок пошуку> — пошук за ім'ям або телефоном",
        "all": "all — показати всі контакти",
        "add-birthday": "add-birthday <Ім'я> <ДД.ММ.РРРР> — додати день народження контакту",
        "show-birthday": "show-birthday <Ім'я> — показати день народження контакту",
        "birthdays": "birthdays — найближчі дні народження (на тиждень вперед)",
        "help / hello": "список команд",
        "exit / close": "вийти та зберегти",
    }
    for c, d in cmds.items():
        console.print(f"[cyan]{c:15}[/] {d}")

# -------------------- Main Loop --------------------
def parse_input(text: str) -> List[str]:
    return text.strip().split()

def main():
    book = load_data()
    console.print("\n[bold yellow]SYTObook[/] – your personal contacts assistant 🤖\n")
    while True:
        raw = console.input("[bold]>>> [/]")
        parts = parse_input(raw)
        if not parts:
            continue
        cmd, *args = parts
        cmd = cmd.lower()

        # quick name detection for interactive change
        if cmd in book.data and not args:
            console.print("[italic]Detected contact – entering change wizard…[/]")
            console.print(help_message())
            continue

        if cmd in ("exit", "close"):
            save_data(book)
            console.print("[bold green]Good bye![/]")
            break
        elif cmd in ("hello", "help"):
            help_message()
        elif cmd == "add":
            console.print(add_contact(args, book))
        elif cmd == "change":
            console.print(change_contact(args, book))
        elif cmd == "delete":
            console.print(delete_contact(args, book))
        elif cmd == "search":
            res = search_handler(args, book)
            if isinstance(res, str):
                console.print(res)
            else:
                display_contacts(res)
        elif cmd == "all":
            res = show_all_handler(args, book)
            if isinstance(res, str):
                console.print(res)
            else:
                display_contacts(res)
        elif cmd == "add-birthday":
            console.print(add_birthday(args, book))
        elif cmd == "show-birthday":
            console.print(show_birthday(args, book))
        elif cmd == "birthdays":
            console.print(birthdays(args, book))
        else:
            console.print("[red]Unknown command. Type help[/]")

if __name__ == "__main__":
    main()
