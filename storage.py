import os
import pickle
from logic import *
from models import *


# ────────────────────────────────────────────────────────────────────────────
# user‑scoped storage
# ────────────────────────────────────────────────────────────────────────────
def user_path(username: str, base: str) -> str:
    root = os.path.join("data", username.lower())
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, base)

# ────────────────────────────────────────────────────────────────────────────
# Persistence
# ────────────────────────────────────────────────────────────────────────────

DATA_FILE, NOTES_FILE = "addressbook.pkl", "notesbook.pkl"


def _save(obj, path):
    with open(path, "wb") as f:
        pickle.dump(obj, f)

def _load(path, factory):
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except (FileNotFoundError, pickle.PickleError):
        return factory()

def load_data(username: str):
    return _load(user_path(username, DATA_FILE), AddressBook)

def load_notes(username: str):
    return _load(user_path(username, NOTES_FILE), GeneralNoteBook)

def save_data(username: str, ab):
    _save(ab, user_path(username, DATA_FILE))

def save_notes(username: str, nb):
    _save(nb, user_path(username, NOTES_FILE))


USERS_FILE = "users.pkl"


def load_users():
    try:
        with open(USERS_FILE, "rb") as f:
            return pickle.load(f)
    except (FileNotFoundError, pickle.PickleError):
        return {}


def save_users(users):
    with open(USERS_FILE, "wb") as f:
        pickle.dump(users, f)