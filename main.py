from openai import OpenAI
from rich.console import Console
from logic import *
from handlers import *
from storage import *

# ────────────────────────────────────────────────────────────────────────────
# Optional OpenAI (autocorrect & semantic search); can work without key.txt
# ────────────────────────────────────────────────────────────────────────────
try:
    from openai import OpenAI

    with open("key.txt", "r", encoding="utf‑8") as f:
        _client = OpenAI(api_key=f.read().strip())
except (ImportError, FileNotFoundError):
    _client = None

def main():
    users = load_users()
    console.print("\n[bold blue]Wellcome to [yellow]SYTObook[/] – your personal contacts and notes assistant[/] 🤖\n")

    while True:
        choice = input("Do you want to (l)ogin or (r)egister? >>> ").strip()
        if choice == "r":
            username = register(users)
            break
        elif choice == "l":
            username = login(users)
            if username:
                break
        elif choice == "exit":
            console.print("[dim italic]We are very sorry that you are leaving us. Bye![/]\n")
            exit(0)
        else:
            console.print("[dim italic]Incalid input. Please enter 'l' for login or 'r' for register.[/]\n" )

    console.print(f"\n[bold]Hello, [blue]{username.capitalize()}[/], glad to see you![/]")
    ab = load_data(username)
    nb = load_notes(username)
    mode = "main"

    if _client is None:
        console.print("[yellow]AI functions disabled (no key.txt).[/]")

    while True:
        try:
            # main menu
            if mode == "main":
                choice = console.input(
                    "\n[bold]Choose a mode > [orchid]contacts[/] | [navajo_white1]notes[/] or exit:[/] ").strip().lower()
                if choice in ("exit", "close"):
                    save_data(username, ab)
                    save_notes(username, nb)
                    console.print(ok("Data saved. Bye!"))
                    break
                if choice in ("contacts", "notes"):
                    mode = choice
                    help_msg(mode)
                    continue
                console.print("Unknown mode.")
                continue

            # contacts
            if mode == "contacts":
                raw = console.input("\n[bold italic][orchid]Contacts[/]>>> Command: [/]").strip()
                if raw in ("exit", "close"):
                    save_data(username, ab)
                    save_notes(username, nb)
                    console.print(ok("Data saved. Bye!"));
                    break
                if raw == "back": mode = "main"; continue
                parts = raw.split()
                if not parts: continue
                cmd = parts[0]
                if cmd not in CONTACT_CMDS:
                    sug = suggest_correction(raw, CONTACT_DESC)
                    if sug and console.input(f"Did you mean '{sug}'? (y/n): ").lower().startswith("y"):
                        parts = [sug] + collect_args(sug)
                    else:
                        console.print("[dim italic]Unknown command.[/]\n");
                        continue
                need = ARG_SPEC.get(parts[0], 0)
                if len(parts) - 1 < need: parts += collect_args(parts[0])
                res = handle_contact(parts, ab)
                if res == "BACK":
                    mode = "main"
                elif res:
                    console.print(res)

            # notes
            if mode == "notes":
                raw = console.input("\n[italic][navajo_white1]Notes[/]>>> Command: [/]").strip()
                if raw in ("exit", "close"):
                    save_data(username, ab)
                    save_notes(username, nb)
                    console.print(ok("Data saved. Bye!"));
                    break
                if raw == "back": mode = "main"; continue
                parts = raw.split()
                if not parts: continue
                cmd = parts[0]
                if cmd not in NOTE_CMDS:
                    sug = suggest_correction(raw, NOTE_DESC)
                    if sug and console.input(f"Did you mean '{sug}'? (y/n): ").lower().startswith("y"):
                        parts = [sug] + collect_args(sug)
                    else:
                        console.print("[dim italic]Unknown command.[/]\n");
                        continue
                need = ARG_SPEC.get(parts[0], 0)
                if len(parts) - 1 < need: parts += collect_args(parts[0])
                res = handle_notes(parts, nb)
                if res == "BACK":
                    mode = "main"
                elif res:
                    console.print(res)

        except KeyboardInterrupt:
            console.print("\nInterrupted. Saving …")
            save_data(username, ab)
            save_notes(username, nb)
            break


if __name__ == "__main__":
    main()