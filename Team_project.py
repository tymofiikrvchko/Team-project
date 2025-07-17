import re
import datetime
import pickle
from collections import UserDict
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from rich.columns import Columns
from rich.panel import Panel


# -------------------- Field Classes --------------------

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
    """Phone number: exactly 10 digits."""
    def __init__(self, value: str):
        if not value.isdigit() or len(value) != 10:
            raise ValueError("Phone number must contain exactly 10 digits.")
        super().__init__(value)


class Birthday(Field):
    """Birthday date in DD.MM.YYYY format."""
    def __init__(self, value: str):
        try:
            dt = datetime.datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError:
            raise ValueError("Invalid date format. Use DD.MM.YYYY")
        super().__init__(dt)


# -------------------- Record & AddressBook --------------------

class Record:
    """Holds name, phones list, and optional birthday."""
    def __init__(self, name: str):
        self.name = Name(name)
        self.phones: list[Phone] = []
        self.birthday: Optional[Birthday] = None

    def add_phone(self, phone: str) -> None:
        self.phones.append(Phone(phone))

    def remove_phone(self, phone: str) -> None:
        for i, p in enumerate(self.phones):
            if p.value == phone:
                del self.phones[i]
                return
        raise ValueError(f"Phone {phone} not found.")

    def edit_phone(self, old: str, new: str) -> None:
        for i, p in enumerate(self.phones):
            if p.value == old:
                self.phones[i] = Phone(new)
                return
        raise ValueError(f"Phone {old} not found.")

    def add_birthday(self, bday_str: str) -> None:
        if self.birthday is not None:
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

    def __str__(self):
        phones = ", ".join(p.value for p in self.phones) or "no phones"
        bday = (
            self.birthday.value.strftime("%d.%m.%Y")
            if self.birthday else "no birthday"
        )
        return f"{self.name.value}: phones[{phones}]; birthday[{bday}]"


class AddressBook(UserDict):
    """Manages multiple Record objects."""
    def add_record(self, record: Record) -> None:
        self.data[record.name.value] = record

    def delete(self, name: str) -> None:
        del self.data[name]

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
    """Serialize the address book to disk."""
    with open(filename, "wb") as f:
        pickle.dump(book, f)

def load_data(filename: str = DATA_FILE) -> AddressBook:
    """
    Attempt to load the address book from disk.
    If the file does not exist, return a new AddressBook.
    """
    try:
        with open(filename, "rb") as f:
            return pickle.load(f)
    except (FileNotFoundError, pickle.PickleError):
        return AddressBook()

# -------------------- Error Handling Decorator --------------------

def input_error(func):
    """
    Decorator to catch KeyError, ValueError, IndexError
    and return user-friendly messages instead of tracebacks.
    """
    def wrapper(args, book):
        try:
            return func(args, book)
        except IndexError:
            return "Enter name (and other args) please."
        except KeyError:
            return "Contact not found."
        except ValueError as e:
            return str(e)
    return wrapper


# -------------------- Command Handlers --------------------

@input_error
def add_contact(args, book: AddressBook) -> str:
    name, phone, *_ = args
    try:
        rec = book.find(name)
        message = "[dim italic bold]\nContact updated!\n[/dim italic bold]"
    except KeyError:
        rec = Record(name)
        book.add_record(rec)
        message = "[dim italic bold]\nContact added!\n[/dim italic bold]"
    if phone:
        rec.add_phone(phone)
    return message

@input_error
def change_contact(args, book: AddressBook) -> str:
    name, old, new, *_ = args
    rec = book.find(name)
    rec.edit_phone(old, new)
    return "[dim italic bold]\nPhone number updated!\n[/dim italic bold]"

@input_error
def search_handler(args, book: AddressBook) -> str:
    query = args[0].lower()
    results = []
    for record in book.data.values():
        name_search = query in record.name.value.lower()
        phone_search = any(query in phone.value for phone in record.phones)
        if name_search or phone_search:
            results.append(record)
    if not results:
        return "[dim italic bold]\nNo matching contacts found.\n[/dim italic bold]"
    return results

@input_error
def show_all_handler(args, book: AddressBook) -> str:
    if not book.data:
        return "[dim italic bold]\nAddress book is empty.\n[/dim italic bold]"
    return book.data.values()

@input_error
def add_birthday(args, book: AddressBook) -> str:
    name, bday = args
    rec = book.find(name)
    rec.add_birthday(bday)
    return "[dim italic bold]\nBirthday added!\n[/dim italic bold]"

@input_error
def show_birthday(args, book: AddressBook) -> str:
    name = args[0]
    rec = book.find(name)
    if rec.birthday:
        return rec.birthday.value.strftime("%d.%m.%Y")
    return "[dim italic bold]\nBirthday not set.\n[/dim italic bold]"

@input_error
def birthdays(args, book: AddressBook) -> str:
    upcoming = book.get_upcoming_birthdays()
    if not upcoming:
        return "[dim italic bold]\nNo birthdays in the next week.[/dim italic bold]"
    return "\n".join(f"{name}: {dt.strftime('%d.%m.%Y')}" for name, dt in upcoming.items())



# ------------------Output Contacts--------------------

def show_contacts_markdown(contacts):
    console = Console()
    if not contacts:
        console.print("[dim italic bold]\nСписок контактів порожній.\n[/dim italic bold]")
        return

    contacts_sorted = sorted(
        contacts,
        key=lambda c: c.name.value.lower() if hasattr(c.name, "value") else str(c.name).lower()
    )

    contact_panels = []

    for contact in contacts_sorted:
        name = contact.name.value if hasattr(contact.name, "value") else str(contact.name)
        phones = getattr(contact, "phones", [])
        emails = getattr(contact, "emails", [])
        address = getattr(contact, "address", None)
        notes = getattr(contact, "notes", None)
        birthday = getattr(contact, "birthday", None)
        # favorite = getattr(contact, "favorite", False)

        phones_str = ", ".join(p.value if hasattr(p, "value") else str(p) for p in phones) or "—"
        emails_str = ", ".join(str(e) for e in emails) or "—"
        birthday_str = birthday.value.strftime("%d.%m.%Y") if birthday else "—"
        address_str = address or "—"
        notes_str = notes or "—"
        # fav_str = "⭐ Так" if favorite else "—"

        contact_text = (
            f"[b]📞 Телефони:[/b] {phones_str}\n"
            f"[b]📧 Email:[/b] {emails_str}\n"
            f"[b]🎂 День народження:[/b] {birthday_str}\n"
            f"[b]📍 Адреса:[/b] {address_str}\n"
            f"[b]📝 Нотатки:[/b] {notes_str}\n"
            # f"[b]⭐ Улюблений:[/b] {fav_str}"
        )

        panel = Panel(contact_text, title=f"👤 {name.upper()}", border_style="cyan", expand=False)
        contact_panels.append(panel)

    console.print(Columns(contact_panels, equal=True, expand=True))

# -------------------- CLI Utility --------------------

def parse_input(user_input: str) -> list[str]:
    """Split user input into command and arguments."""
    return user_input.strip().split()


# -------------------- Main Loop --------------------



def main():
    console = Console()
    book = load_data()
    console.print("\nWelcome to [yellow]SYTObook[/yellow] - your personal contacts and notes assistant!", style="bold red")
    while True:
        user_input = console.input("[bold]Enter a command: [/bold]")
        parts = parse_input(user_input)
        if not parts:
            continue
        command, *args = parts
        cmd = command.lower()

        if cmd in ("exit", "close"):
            save_data(book)
            print("Good bye!")
            break
        elif cmd in ("hello", "help"):
            if cmd == "hello":
                console.print("\n[bold red]Hello! How can I help you?[/bold red]\n\n[bold underline cyan]📋 Команди бота[/bold underline cyan]")
            else:
                console.print("\n[bold red]How can I help you?[/bold red]\n\n[bold underline cyan]📋 Команди бота[/bold underline cyan]")
            commands = [
                ("[bold green]add[/bold green]", "➕ Add new contact"),
                ("[bold green]change[/bold green]", "🔄 Change contact"),
                ("[bold green]delete[/bold green]", "🗑️ Delete contact"),
                ("[bold green]all[/bold green]", "📇 Show all contacts"),
                ("[bold green]birthdays[/bold green]", "🎂 Show birthdays within a specified period"),
                ("[bold green]help[/bold green]", "❓ Show list of commands"),
                ("[bold green]exit[/bold green] or [bold green]close[/bold green]", "🔚 Show list of commands\n")
            ]
            for cmd, desc in commands:
                console.print(f"{cmd} – {desc}")
        elif cmd == "add":
            console.print(add_contact(args, book))
        elif cmd == "change":
            console.print(change_contact(args, book))
            # Changed the command "phone" to the command "search"
        elif cmd == "search":
            result = search_handler(args, book)
            if isinstance(result, str):
                console.print(result)
            else:
                show_contacts_markdown(result)

        elif cmd == "all":
            show_contacts_markdown((show_all_handler(args, book)))
        elif cmd == "add-birthday":
            print(add_birthday(args, book))
        elif cmd == "show-birthday":
            # show_contacts_markdown(show_birthday(args, book))
            print(show_birthday(args, book))
        elif cmd == "birthdays":
            # show_contacts_markdown(birthdays(args, book))
            print(birthdays(args, book))
        else:
            print("Invalid command.")

if __name__ == "__main__":
    main()
