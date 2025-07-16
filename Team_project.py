import os
import re
import datetime
import pickle
from collections import UserDict
from typing import Optional
from openai import OpenAI

# -------------------- OpenAI Client --------------------
# Initialize OpenAI client for GPT-based note searching
with open("key.txt", "r") as f:
    api_key = f.read().strip()

client = OpenAI(api_key=api_key)

# -------------------- Field Classes --------------------

class Field:
    """Base class for record fields."""
    def __init__(self, value):
        # Store the field value
        self.value = value

    def __str__(self):
        # Return string representation of the value
        return str(self.value)


class Name(Field):
    """Mandatory contact name field."""
    def __init__(self, value: str):
        # Ensure the name is not empty
        if not value.strip():
            raise ValueError("Name cannot be empty.")
        super().__init__(value)


class Phone(Field):
    """Phone number field: must be exactly 10 digits."""
    def __init__(self, value: str):
        # Validate that the string is digits only and length is 10
        if not (value.isdigit() and len(value) == 10):
            raise ValueError("Phone number must contain exactly 10 digits.")
        super().__init__(value)


class Birthday(Field):
    """Birthday field in DD.MM.YYYY format."""
    def __init__(self, value: str):
        try:
            # Parse string into a date object
            dt = datetime.datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError:
            # Raise error if format is invalid
            raise ValueError("Invalid date format. Use DD.MM.YYYY")
        super().__init__(dt)

# -------------------- Record & AddressBook --------------------

class Record:
    """Represents a contact record with name, phones, optional birthday, and notes."""
    def __init__(self, name: str):
        self.name = Name(name)
        self.phones: list[Phone] = []
        self.birthday: Optional[Birthday] = None
        # List of text notes
        self.notes: list[str] = []

    def add_phone(self, phone: str) -> None:
        self.phones.append(Phone(phone))

    def remove_phone(self, phone: str) -> None:
        """Remove a phone number, or raise an error if not found."""
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
            # If already passed this year, use next year
            next_bday = next_bday.replace(year=today.year + 1)
        return (next_bday - today).days

    def add_note(self, note: str) -> None:
        """Add a textual note to this contact."""
        if not note.strip():
            raise ValueError("Note cannot be empty.")
        self.notes.append(note)

    def __str__(self):
        phones = ", ".join(p.value for p in self.phones) or "no phones"
        bday = self.birthday.value.strftime("%d.%m.%Y") if self.birthday else "no birthday"
        notes = " | ".join(self.notes) if self.notes else "no notes"
        return f"{self.name.value}: phones[{phones}]; birthday[{bday}]; notes[{notes}]"

class AddressBook(UserDict):
    """Manages a collection of Record objects."""
    def add_record(self, record: Record) -> None:
        # Add or update a record by contact name
        self.data[record.name.value] = record

    def find(self, name: str) -> Record:
        # Retrieve a record by name, or raise KeyError
        return self.data[name]

    def delete(self, name: str) -> None:
        # Delete a record by name, or raise KeyError
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
    """Serialize the address book to disk using pickle."""
    with open(filename, "wb") as f:
        pickle.dump(book, f)

def load_data(filename: str = DATA_FILE) -> AddressBook:
    """Load the address book from disk, or return a new one if file not found."""
    try:
        with open(filename, "rb") as f:
            return pickle.load(f)
    except (FileNotFoundError, pickle.PickleError):
        return AddressBook()

# -------------------- Error Handling Decorator --------------------

def input_error(func):
    """Decorator to handle IndexError, KeyError, ValueError and return user-friendly messages."""
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
def change_contact(args, book: AddressBook) -> str:
    """Handle 'change' command: replace an existing phone number."""
    name, old, new, *_ = args
    rec = book.find(name)
    rec.edit_phone(old, new)
    return "Phone number updated."

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
    return "\n".join(f"{name}: {dt.strftime('%d.%m.%Y')}" for name, dt in upcoming.items())

@input_error
def add_note_handler(args, book: AddressBook) -> str:
    name, *note_parts = args
    rec = book.find(name)
    note_text = " ".join(note_parts)
    rec.add_note(note_text)
    return "Note added."

@input_error
def search_note_handler(args, book: AddressBook) -> str:
    """Handle 'search-note' command: find notes using GPT-4 semantic search."""
    query = " ".join(args)
    # Build list of all notes with contact identifiers
    notes_list = []
    for name, rec in book.data.items():
        for idx, note in enumerate(rec.notes, 1):
            notes_list.append(f"{name}#{idx}: {note}")
    system_prompt = (
        "You are a note search assistant. The existing notes are:\n" +
        "\n".join(notes_list) +
        "\nWhen the user queries, return the notes (with Name#Index) that best match their request."
    )
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Search query: {query}"}
        ],
        temperature=0.0,
        max_tokens=200
    )
    return response.choices[0].message.content.strip()

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
        elif cmd == "add-note":
            print(add_note_handler(args, book))
        elif cmd == "search-note":
            print(search_note_handler(args, book))
        else:
            print("Invalid command.")

if __name__ == "__main__":
    main()
