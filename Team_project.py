import re
import datetime
import pickle
from collections import UserDict
from typing import Optional


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
        self.email = None
        self.address = None


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
    
    def update_email(self, email):
        self.email = email.strip()

    def update_address(self, address):
        self.address = address.strip()

    def __str__(self):
        phones = ", ".join(p.value for p in self.phones) or "no phones"
        bday = (
            self.birthday.value.strftime("%d.%m.%Y")
            if self.birthday else "no birthday"
        )
        email = f", email: {self.email}" if self.email else ""
        address = f", address: {self.address}" if self.address else ""
        return f"{self.name.value}: phones[{phones}]; birthday[{bday}] {email} {address}"


class AddressBook(UserDict):
    """Manages multiple Record objects."""
    def add_record(self, record: Record) -> None:
        self.data[record.name.value] = record

    def find(self, name: str) -> Record:
        return self.data[name]  # KeyError if missing

    def delete(self, name: str) -> None:
        name = name.strip()
        if name not in self.data:
            raise KeyError("No such contact in you address book")
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
        message = "Contact updated."
    except KeyError:
        rec = Record(name)
        book.add_record(rec)
        message = "Contact added."
    if phone:
        rec.add_phone(phone)
    return message

@input_error
def change_contact(args, book):
    name_input = input("Which contact do you want to change? >>> ").strip()
    normalized_name = get_record_key(name_input, book)
    if not normalized_name:
        return "Ooops. Contact not found :-("
    
    record = book.data[normalized_name]
    
    field = input("What do you want to change in this contact? (phone / email / address) >>> ").strip().lower()


    if field == "phone":
        new_phone = input("Enter new phone >>> ").strip()
        record.phones = []
        record.add_phone(new_phone)
        return f"Phone updated for {normalized_name.capitalize()}"
    
    elif field == "email":
        new_email = input("Enter new email >>> ").strip()
        record.update_email(new_email)
        return f"Email updated for {normalized_name.capitalize()}"
    
    elif field == "address":
        new_address = input("Enter new address >>> ").strip()
        record.update_address(new_address)
        return f"Address updated for {normalized_name.capitalize()}"
    
    else:
        return "Unknown command. Choose from: phone / email / address"
    
@input_error
def delete_contact(args, book):
    name_input = input("Which contact do you want to delete? >>> ").strip()
    normalized_name = get_record_key(name_input, book)
    if not normalized_name :
        return "Ooops. Contact not found :-("
    
    del book.data[normalized_name]
    return f"Contact {normalized_name} was deleted"


def get_record_key(name: str, book: AddressBook) -> Optional[str]:
    name_lower = name.strip().lower()
    return next((key for key in book.data if key.lower() == name_lower), None)

@input_error
def phone_handler(args, book: AddressBook) -> str:
    name = args[0]
    rec = book.find(name)
    if not rec.phones:
        return "No phones for this contact."
    return ", ".join(p.value for p in rec.phones)

@input_error
def show_all_handler(args, book: AddressBook) -> str:
    if not book.data:
        return "Address book is empty."
    return "\n".join(str(rec) for rec in book.data.values())

@input_error
def add_birthday(args, book: AddressBook) -> str:
    name, bday = args
    rec = book.find(name)
    rec.add_birthday(bday)
    return "Birthday added."

@input_error
def show_birthday(args, book: AddressBook) -> str:
    name = args[0]
    rec = book.find(name)
    if rec.birthday:
        return rec.birthday.value.strftime("%d.%m.%Y")
    return "Birthday not set."

@input_error
def birthdays(args, book: AddressBook) -> str:
    upcoming = book.get_upcoming_birthdays()
    if not upcoming:
        return "No birthdays in the next week."
    return "\n".join(f"{name}: {dt.strftime('%d.%m.%Y')}"
                     for name, dt in upcoming.items())


# -------------------- CLI Utility --------------------

def parse_input(user_input: str) -> list[str]:
    """Split user input into command and arguments."""
    return user_input.strip().split()


# -------------------- Main Loop --------------------

def main():
    book = load_data()
    print("Welcome to the assistant bot!")
    while True:
        user_input = input("Enter a command: ")
        parts = parse_input(user_input)
        if not parts:
            continue
        command, *args = parts
        cmd = command.lower()

        if len(parts) == 1 and get_record_key(cmd, book):
            print(f"Detected contact name: '{cmd}'. Launching change mode...")
            print(change_contact([], book))
            continue

        if cmd in ("exit", "close"):
            save_data(book)
            print("Good bye!")
            break
        elif cmd == "hello":
            print("How can I help you?")
        elif cmd == "add":
            print(add_contact(args, book))
        elif cmd == "change":
            print(change_contact(args, book))
        elif cmd == "phone":
            print(phone_handler(args, book))
        elif cmd == "all":
            print(show_all_handler(args, book))
        elif cmd == "add-birthday":
            print(add_birthday(args, book))
        elif cmd == "show-birthday":
            print(show_birthday(args, book))
        elif cmd == "birthdays":
            print(birthdays(args, book))
        elif cmd == "delete":
            print(delete_contact(args, book))
        else:
            print("Invalid command.")

if __name__ == "__main__":
    main()
