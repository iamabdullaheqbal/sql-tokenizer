# SQL Tokenizer & Validator
### Compiler Construction Project — Lexical Analysis & Syntax Validation

---

## Project Structure

```
sql-tokenizer/
├── backend/
│   ├── main.py           ← FastAPI app (pure Python lexer + parser)
│   └── requirements.txt
└── frontend/
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx       ← Main UI
    │   └── globals.css
    ├── lib/
    │   └── api.ts         ← API helper functions
    ├── package.json
    ├── next.config.js
    ├── tailwind.config.ts
    └── tsconfig.json
```

---

## Setup & Run

### 1. Backend (FastAPI)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API is now live at: http://localhost:8000

### 2. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

App is now live at: http://localhost:3000

---

## How the Tokenizer Works (Lexical Analysis)

> **Rule strictly followed: No Python libraries used for lexical analysis.**
> The lexer is implemented as a hand-written character-by-character scanner.

### Token Types

| Type | Description | Example |
|------|-------------|---------|
| `KEYWORD` | Reserved SQL words | `SELECT`, `FROM`, `WHERE` |
| `AGGREGATE_FUNCTION` | Aggregate SQL functions | `COUNT`, `SUM`, `AVG`, `MIN`, `MAX` |
| `IDENTIFIER` | Table/column names | `students`, `age`, `id` |
| `STRING` | Quoted string literals | `'Alice'`, `'HR'` |
| `NUMBER` | Numeric constants | `18`, `75000`, `3.14` |
| `OPERATOR` | Comparison/arithmetic ops | `=`, `<>`, `>`, `<=` |
| `WILDCARD` | Star in SELECT context | `*` |
| `PUNCTUATION` | Structural characters | `(`, `)`, `,`, `;` |
| `UNKNOWN` | Unrecognized characters | `@`, `#` |

### Scanning Algorithm

```
i = 0
while i < length(query):
    skip whitespace
    if char is "'":     → scan STRING until closing quote
    if char is digit:   → scan NUMBER (integers + decimals)
    if char is letter:  → scan WORD → check against KEYWORDS set
    if char is operator char:
        check 2-char ops first (<>, !=, <=, >=)
        else single-char operator
    if char is punctuation: → emit PUNCTUATION token
    else: → emit UNKNOWN (lexical error)
```

---

## Validated Examples

### Example 1 — SELECT with WHERE and ORDER BY

```sql
SELECT id, name, age FROM students WHERE age > 18 ORDER BY name ASC
```

**Token Stream:**

| # | Value | Type |
|---|-------|------|
| 1 | SELECT | KEYWORD |
| 2 | id | IDENTIFIER |
| 3 | , | PUNCTUATION |
| 4 | name | IDENTIFIER |
| 5 | , | PUNCTUATION |
| 6 | age | IDENTIFIER |
| 7 | FROM | KEYWORD |
| 8 | students | IDENTIFIER |
| 9 | WHERE | KEYWORD |
| 10 | age | IDENTIFIER |
| 11 | > | OPERATOR |
| 12 | 18 | NUMBER |
| 13 | ORDER | KEYWORD |
| 14 | BY | KEYWORD |
| 15 | name | IDENTIFIER |
| 16 | ASC | KEYWORD |

**Validation:** ✅ VALID
- Lexer scans 16 tokens with no unknown characters
- Parser: SELECT → column list (id, name, age) → FROM → table (students) → WHERE → condition (age > 18) → ORDER BY → column (name) → direction (ASC)

---

### Example 2 — INSERT INTO with column list

```sql
INSERT INTO students (id, name, age) VALUES (1, 'Alice', 21)
```

**Token Stream:**

| # | Value | Type |
|---|-------|------|
| 1 | INSERT | KEYWORD |
| 2 | INTO | KEYWORD |
| 3 | students | IDENTIFIER |
| 4 | ( | PUNCTUATION |
| 5 | id | IDENTIFIER |
| 6 | , | PUNCTUATION |
| 7 | name | IDENTIFIER |
| 8 | , | PUNCTUATION |
| 9 | age | IDENTIFIER |
| 10 | ) | PUNCTUATION |
| 11 | VALUES | KEYWORD |
| 12 | ( | PUNCTUATION |
| 13 | 1 | NUMBER |
| 14 | , | PUNCTUATION |
| 15 | Alice | STRING |
| 16 | , | PUNCTUATION |
| 17 | 21 | NUMBER |
| 18 | ) | PUNCTUATION |

**Validation:** ✅ VALID
- Lexer identifies keywords, identifiers, punctuation, a string literal, and numbers
- Parser: INSERT → INTO → table → `(` column list `)` → VALUES → `(` value list `)`

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tokenize` | Returns list of tokens + type counts |
| POST | `/validate` | Returns validity + errors + parser trace |
| GET | `/examples` | Returns pre-built SQL examples |
| GET | `/health` | Health check |

### Request body (both POST endpoints):
```json
{ "query": "SELECT * FROM users WHERE id = 1" }
```

---

## Supported SQL Grammar

```
statement  → select | insert | update | delete

select     → SELECT [DISTINCT] [TOP n] col_list FROM identifier
             [WHERE condition] [GROUP BY col [HAVING cond]]
             [ORDER BY col [ASC|DESC]] [LIMIT n [OFFSET n]]

insert     → INSERT INTO identifier [(col_list)] VALUES (val_list)

update     → UPDATE identifier SET col=val [, col=val ...]
             [WHERE condition]

delete     → DELETE FROM identifier [WHERE condition]

condition  → value op value
           | value IS [NOT] NULL
           | value BETWEEN value AND value
           | value IN (val_list)
           | value LIKE value
           | condition AND|OR condition
```

---

## Tech Stack

- **Backend:** Python 3.10+ · FastAPI · Uvicorn
- **Frontend:** Next.js 14 · TypeScript · Tailwind CSS · Poppins font
- **Lexer:** Pure Python (no libraries) — hand-written character scanner
- **Parser:** Recursive-descent parser for SQL grammar

---

*Submission: June 29, 2026 — Compiler Construction*
