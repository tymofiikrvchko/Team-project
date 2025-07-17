import re
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



class Surname(Field):
    """optional"""
    def __init__(self, value: str):
        
            
        super().__init__(value.strip())


 

class Address(Field):
    """optional"""
    def __init__(self, value: str):
        
            
        super().__init__(value.strip())


 
class Email(Field):
    """Email validation."""
    def __init__(self, value: str):
        if value and not re.match(r"[^@]+@[^@]+\.[^@]+", value):
            raise ValueError("Invalid email format.")
        super().__init__(value.strip())
              
       



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
    """Holds name, surname, Address, phones list, and optional birthday."""
    def __init__(self, name: str, surname: str, address: str, email: str):
        self.name = Name(name)
        self.surname = Surname(surname)
        self.address = Address(address)
        self.email = Email(email)
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
        return f"{self.name.value} {self.surname.value}, Address: {self.address.value or "no address"},Email:{self.email.value or "no email"}, phones[{phones}]; birthday[{bday}]"


class AddressBook(UserDict):
    """Manages multiple Record objects."""
    def add_record(self, record: Record) -> None:
        self.data[record.name.value] = record

    def find(self, name: str) -> Record:
        return self.data[name]  # KeyError if missing

    def delete(self, name: str) -> None:
        del self.data[name]  # KeyError if missing

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
    # name, surname, Helloaddress, phone, *_ = args
    name = input("Enter name (required): ").strip()
    if not name:
        return "Name is required."

    surname = input("Enter surname(optional) ").strip()

    while True:
       phone = input("Enter phone number (10 digits, optional): ").strip()
       if not phone:
           break 
       try:
           Phone(phone)  
           break
       except ValueError as e:
           print(f"Invalid phone: {e}") 

    while True:
        email = input("Enter email(optional): ").strip()
        if not email:
            break
        try:
            Email(email)  
            break
        except ValueError as e:
            print(f"Invalid email: {e}") 

    
    address = input("Enter address(optional): ").strip()
    while True:
        bday_input = input("Enter birthday (DD.MM.YYYY, optional: )").strip()
        if not bday_input:
            bday = None
            break
        try:
            bday = Birthday(bday_input)
            break
        except ValueError as e:
            print (f"Invalid birthday: {e}")        



    try:
        rec = book.find(name)
        if phone:
         rec.add_phone(phone)
        return "Contact exists - added new phone if provided."
    except KeyError:
        rec = Record(name, surname, address,email)
        if phone:
         rec.add_phone(phone)
        if bday:
          rec.birthday = bday  
        book.add_record(rec)
    
        return "New contact added"




@input_error
def change_contact(args, book: AddressBook) -> str:
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
    return "\n".join(f"{name}: {dt.strftime('%d.%m.%Y')}"
                     for name, dt in upcoming.items())

@input_error
def change_address(args, book: AddressBook) -> str:
    if len(args) < 2:
        return "Usage: change-address <name> <new address>"
    name, *address_parts = args
    new_adress = " ".join(address_parts)

    rec = book.find(name)
    rec.address = Address(new_adress)
    return "Address uodated."


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
        elif cmd =="change-address":  
            print(change_address(args, book))
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
        else:
            print("Invalid command.")

if __name__ == "__main__":
    main()
