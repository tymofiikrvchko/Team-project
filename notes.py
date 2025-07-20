import datetime
from typing import List

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