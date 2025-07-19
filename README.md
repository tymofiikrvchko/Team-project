# 🧠 SYTObook — CLI-помічник для контактів і нотаток

**SYTObook** — це інтелектуальний консольний асистент для зберігання контактної інформації, нотаток і управління ними. Працює локально, підтримує інтеграцію з OpenAI для семантичного пошуку та автокорекції команд.

---

## 🔧 Встановлення

### 1. Клонування репозиторію
```bash
git clone https://github.com/yourname/sytobook.git
cd sytobook
```

### 2. Створення та активація віртуального середовища
```bash
python -m venv venv
source venv/bin/activate         # Linux/macOS
venv\Scripts\activate          # Windows
```

### 3. Встановлення залежностей
```bash
pip install -r requirements.txt
```

### 4. [Опційно] Додай API-ключ OpenAI

1. Зареєструйся на https://platform.openai.com
2. Згенеруй API-ключ
3. Створи файл `key.txt` у корені проєкту та встав туди ключ.

---

## 🚀 Запуск

```bash
python main.py
```

---

## 📋 Команди (режим contact)

- `add`, `change`, `remove-phone`, `delete`, `phone`, `all`, `search`, `add-birthday`, `show-birthday`, `birthdays`, `add-contact-note`, `change-address`, `change-email`

## 🗒️ Команди (режим notes)

- `add-note`, `list-notes`, `add-tag`, `search-tag`, `search-note`

## 💾 Збереження даних

- `addressbook.pkl` — всі контакти
- `notesbook.pkl` — всі нотатки

---

## 🧠 AI-можливості

- Автокорекція команд
- Семантичний пошук (при наявності `key.txt`)

---

## 🤝 Автор

**SYTObook** — зроблено з любов’ю до структури, чистоти та Python.
