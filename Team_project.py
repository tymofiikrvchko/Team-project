import re
import datetime
import pickle
from collections import UserDict
from typing import Optional


# -------------------- Field Classes --------------------

class Field:
    """Базовий клас для полів запису."""
    def __init__(self, value):
        # Зберігаємо значення поля
        self.value = value

    def __str__(self):
        # Повертаємо строкове представлення значення
        return str(self.value)


class Name(Field):
    """Обов'язкове поле імені контакту."""
    def __init__(self, value: str):
        # Перевіряємо, що ім'я не порожнє
        if not value.strip():
            raise ValueError("Name cannot be empty.")
        super().__init__(value)


class Phone(Field):
    """Поле номера телефону: має бути рівно 10 цифр."""
    def __init__(self, value: str):
        # Перевірка: строка складається лише з цифр і має довжину 10
        if not value.isdigit() or len(value) != 10:
            raise ValueError("Phone number must contain exactly 10 digits.")
        super().__init__(value)


class Birthday(Field):
    """Поле дати народження у форматі DD.MM.YYYY."""
    def __init__(self, value: str):
        try:
            # Конвертуємо рядок в об'єкт date
            dt = datetime.datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError:
            # Викидаємо помилку, якщо формат неправильний
            raise ValueError("Invalid date format. Use DD.MM.YYYY")
        super().__init__(dt)


# -------------------- Record & AddressBook --------------------

class Record:
    """Клас, що зберігає Name, список Phone та опціонально Birthday."""
    def __init__(self, name: str):
        # Ініціалізуємо ім'я контакту
        self.name = Name(name)
        # Список телефонів (Phone)
        self.phones: list[Phone] = []
        # Поле дати народження (може бути None)
        self.birthday: Optional[Birthday] = None

    def add_phone(self, phone: str) -> None:
        """Додаємо новий номер телефону до контакту."""
        self.phones.append(Phone(phone))

    def remove_phone(self, phone: str) -> None:
        """Видаляємо номер телефону, якщо він є; інакше ValueError."""
        for i, p in enumerate(self.phones):
            if p.value == phone:
                del self.phones[i]
                return
        raise ValueError(f"Phone {phone} not found.")

    def edit_phone(self, old: str, new: str) -> None:
        """Замінюємо старий номер новим; якщо старий не знайдено – ValueError."""
        for i, p in enumerate(self.phones):
            if p.value == old:
                self.phones[i] = Phone(new)
                return
        raise ValueError(f"Phone {old} not found.")

    def add_birthday(self, bday_str: str) -> None:
        """Встановлюємо дату народження (лише одна, якщо вже є – ValueError)."""
        if self.birthday is not None:
            raise ValueError("Birthday already set.")
        self.birthday = Birthday(bday_str)

    def days_to_birthday(self) -> Optional[int]:
        """Повертає кількість днів до наступного дня народження чи None."""
        if not self.birthday:
            return None
        today = datetime.date.today()
        # Переносимо дату народження на поточний рік
        next_bday = self.birthday.value.replace(year=today.year)
        if next_bday < today:
            # Якщо вже був у цьому році, беремо наступний
            next_bday = next_bday.replace(year=today.year + 1)
        # Різниця в днях
        return (next_bday - today).days

    def __str__(self):
        # Формуємо строку з усіма телефонами та датою народження
        phones = ", ".join(p.value for p in self.phones) or "no phones"
        bday = (
            self.birthday.value.strftime("%d.%m.%Y")
            if self.birthday else "no birthday"
        )
        return f"{self.name.value}: phones[{phones}]; birthday[{bday}]"


class AddressBook(UserDict):
    """Клас для управління колекцією Record."""
    def add_record(self, record: Record) -> None:
        # Додаємо або оновлюємо запис за ключем = ім'я
        self.data[record.name.value] = record

    def find(self, name: str) -> Record:
        # Повертаємо запис за ім'ям або KeyError
        return self.data[name]

    def delete(self, name: str) -> None:
        # Видаляємо запис за ім'ям або KeyError
        del self.data[name]

    def get_upcoming_birthdays(self) -> dict[str, datetime.date]:
        """
        Повертає словник {ім'я: дата_наступного_дня_народження}
        для тих, у кого день народження протягом наступних 7 днів.
        """
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
    """Серіалізуємо адресну книгу у файл за допомогою pickle."""
    with open(filename, "wb") as f:
        pickle.dump(book, f)

def load_data(filename: str = DATA_FILE) -> AddressBook:
    """
    Завантажуємо адресну книгу з файлу; якщо файл не знайдено, повертаємо нову.
    """
    try:
        with open(filename, "rb") as f:
            return pickle.load(f)
    except (FileNotFoundError, pickle.PickleError):
        return AddressBook()


# -------------------- Error Handling Decorator --------------------

def input_error(func):
    """
    Декоратор для обробки KeyError, ValueError, IndexError
    і повернення дружніх повідомлень замість виключень.
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
    """Команда add: додає або оновлює контакт."""
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
    """Команда change: замінює старий телефон новим."""
    name, old, new, *_ = args
    rec = book.find(name)
    rec.edit_phone(old, new)
    return "Phone number updated."

@input_error
def phone_handler(args, book: AddressBook) -> str:
    """Команда phone: показує телефони контакту.""