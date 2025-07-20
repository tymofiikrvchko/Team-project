from rich.console import Console
from typing import Optional
from models import GeneralNote, Field, Record, AddressBook, group_notes_by_tag
from logic import *
from logic import input_error, help_msg, simple_match 
from main import _client

console = Console()

# ────────────────────────────────────────────────────────────────────────────
# GPT semantic prompt
# ────────────────────────────────────────────────────────────────────────────
SEM_PROMPT = """You are a semantic search assistant.
Below is a numbered list of notes. Each note has the format
<index>: <text>  [tags: <tag1>, <tag2>, ...]

User will send a search query in Russian, Ukrainian or English.
Return ONLY the indices (space‑separated) of up to five notes
that are truly relevant. If nothing fits, return an empty string.
"""

def make_key(name: str, surname: str = "") -> str:
    return f"{name} {surname}".strip().lower()


def make_key_from_input(fullname: str) -> str:
    parts = fullname.strip().split(maxsplit=1)
    return make_key(*parts)


def get_record_key(name: str, book: AddressBook) -> Optional[str]:
    name_parts = name.strip().split(maxsplit=1)
    if not name_parts:
        return None

    matches = [k for k in book.data if all(part.lower() in k for part in name_parts)]
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        console.print("[yellow]Multiple matches found:[/]")
        for i, k in enumerate(matches, 1):
            console.print(f"{i}. {k.title()}")
        idx = console.input("Select number >>> ").strip()
        if idx.isdigit() and 1 <= int(idx) <= len(matches):
            return matches[int(idx) - 1]
    return None


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
        key = make_key(name, surname)
        rec = ab.data.get(key)
        if rec:
            if phone: rec.add_phone(phone)
            if surname: rec.surname = Surname(surname)
            if email: rec.email = Email(email)
            if address: rec.address = Address(address)
            return ok("Contact updated.")
        rec = Record(name, surname, Address(address) if address else "", Email(email) if email else "")
        if phone: rec.add_phone(phone)
        ab.data[key] = rec
        return ok("Contact added.")

    # phone change
    if cmd == "change":
        name_input = input("Which contact do you want to change? >>> ").strip()
        normalized_name = get_record_key(name_input, ab)
        if not normalized_name:
            return "Ooops. Contact not found :-("

        record = ab.data[normalized_name]

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
            return "[dim italic]Unknown command. Choose from: phone / email / address[/]\n"

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
            raise ValueError("Enter a positive integer for the number of days")
        matches = ab.upcoming(int(days))
        show_birthdays(ab, matches)
        return ""

    # misc
    if cmd == "add-contact-note":
        name, *note = args
        ab.find(name).add_contact_note(" ".join(note))
        return ok("Note added.")

    if cmd in ("back", "exit", "close"):
        return "BACK"
    return "Unknown contact command."


@input_error
def handle_notes(parts, nb: GeneralNoteBook):
    cmd, *args = parts
    if cmd in ("hello", "help"):
        return help_msg("notes")
    if cmd == "group-notes":
        tag_filter = args[0].lower() if args else None

        groups = group_notes_by_tag(nb.notes)
        if tag_filter:
            groups = {tag_filter: groups.get(tag_filter, [])}

        if not groups or all(not lst for lst in groups.values()):
            return f"[dim italic]No notes with tag '{tag_filter}'.[/]" if tag_filter else "[dim italic]No notes.[/]\n"

        for tag, lst in groups.items():
            console.print(f"\n[bold blue]🏷️  {tag.upper()}[/] ({len(lst)})")
            for i, n in enumerate(lst, 1):
                console.print(f"  {i}. {n.text}  [dim italic]{n.created_at}[/]")
        return ""
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
        notes = nb.list_notes()
        if not notes:
            console.print("[dim italic]No notes.[/]")
            return ""

        table = Table(show_header=True, header_style="bold blue",
                      box=None, expand=True)
        table.add_column("#", justify="right", style="bold cyan", no_wrap=True)
        table.add_column("Date", style="bright_cyan", no_wrap=True)
        table.add_column("Tags", style="green")
        table.add_column("Text", style="white")

        for i, n in enumerate(notes, 1):
            tags = ", ".join(n.tags) if n.tags else "—"
            table.add_row(str(i), n.created_at.isoformat(), tags, n.text)

        console.print(table)
        return ""

    if cmd == "add-tag":
        idx, *tags = args
        nb.notes[int(idx) - 1].tags.extend(tags)
        return ok("Tags added.")
    if cmd == "search-tag":
        tag = args[0] if args else console.input("Tag: ")
        res = nb.search_by_tag(tag)
        console.print("\n".join(str(n) for n in res) or f"No notes with tag '{tag}'.")
        return ""
    if cmd == "search-note":
        if not nb.notes:
            return "[dim italic]No notes to search.[/]"
        query = " ".join(args) if args else console.input("Query: ")

        # ---------- 1) быстрый keyword‑фильтр ----------
        hits = [i for i, n in enumerate(nb.notes)
                if simple_match(query, n)]
        if hits:
            console.print("[green]Keyword match:[/]")
            console.print("\n".join(f"{i + 1}. {nb.notes[i]}" for i in hits))
            return ""

        # ---------- 2) GPT‑семантика (если ключами не получилось) ----------
        if _client is None:
            return "[yellow]AI search disabled (no key.txt).[/]"

        catalog = "\n".join(
            f"{idx + 1}: {n.text}  [tags: {', '.join(n.tags) or '—'}]"
            for idx, n in enumerate(nb.notes)
        )
        sys_msg = SEM_PROMPT + "\n" + catalog
        resp = _client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.0,
            top_p=0.1,
            max_tokens=20,
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": query}
            ]
        )
        idxs = [int(x) for x in re.findall(r"\d+", resp.choices[0].message.content)]
        if not idxs:
            console.print("[dim italic]No semantic matches.[/]")
            return ""
        console.print("[magenta]Semantic match:[/]")
        console.print("\n".join(f"{i}. {nb.notes[i - 1]}" for i in idxs))
        return ""