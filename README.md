# SQL Tokenizer & Validator
### Compiler Construction Project — Lexical Analysis & Syntax Validation

A full-stack educational tool that processes SQL queries through a hand-written lexer and recursive-descent parser — demonstrating the front-end phases of compiler construction. No external parsing libraries are used.

---

## Project Structure

```
sql-tokenizer/
├── backend/
│   ├── main.py           ← FastAPI app entry point & CORS setup
│   ├── tokenizer.py      ← Hand-written lexer (character-by-character scanner)
│   ├── parser.py         ← Recursive-descent syntax parser
│   ├── routes.py         ← API route handlers
│   ├── models.py         ← Pydantic request models
│   └── pyproject.toml    ← Python dependencies (managed by uv)
└── frontend/
    ├── app/
    │   ├── layout.tsx     ← Root layout
    │   ├── page.tsx       ← Main UI (single-page app)
    │   └── globals.css    ← Global styles & CSS variables
    ├── lib/
    │   └── api.ts         ← Typed API client functions
    ├── package.json
    ├── next.config.js
    ├── tailwind.config.ts
    └── tsconfig.json
```

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **uv** — Python package manager (replaces pip + venv)

### Install uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip (if you already have Python)
pip install uv
```

After installing, restart your terminal so the `uv` command is available.

---

## Setup & Run

### 1. Backend (FastAPI + Python)

```bash
cd backend

# Install all dependencies into a local virtual environment
uv sync

# Start the development server
uv run uvicorn main:app --reload --port 8000
```

API is now live at: **http://localhost:8000**

> `uv sync` reads `pyproject.toml`, creates a `.venv` folder automatically, and installs all dependencies. You do not need to manually create a virtual environment or run `pip install`.

---

### 2. Frontend (Next.js)

```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

App is now live at: **http://localhost:3000**

> Make sure the backend is running on port 8000 before using the frontend, otherwise API calls will fail.

---

## How the Tokenizer Works (Lexical Analysis)

> **Rule strictly followed: No Python libraries used for lexical analysis.**
> The lexer is implemented as a hand-written character-by-character scanner in `tokenizer.py`.

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
| `UNKNOWN` | Unrecognized / invalid input | `@`, `#`, unclosed `'string` |

### Scanning Algorithm

```
i = 0
while i < length(query):
    skip whitespace
    if char is "'":
        scan STRING until closing quote
        if no closing quote found → emit UNKNOWN (lexical error)
    if char is digit:        → scan NUMBER (integers + decimals)
    if char is letter/underscore: → scan WORD → check against KEYWORDS set
    if char is operator:
        check 2-char ops first (<>, !=, <=, >=)
        else single-char operator
        special case: '*' after SELECT/DISTINCT/comma → WILDCARD
    if char is punctuation:  → emit PUNCTUATION token
    else:                    → emit UNKNOWN (lexical error)
```

---

## How the Parser Works (Syntax Analysis)

The parser in `parser.py` is a **recursive-descent parser** — each SQL clause has its own dedicated method that consumes tokens in order and raises a `SyntaxError_` if the sequence is wrong.

Every parsing step is recorded in a `steps` list and returned to the frontend, so users can see exactly how the parser walked through their query.

### Error Reporting

Errors include four fields designed for educational display:

| Field | Description |
|-------|-------------|
| `message` | What went wrong |
| `position` | Character offset in the original query string |
| `hint` | How to fix it |
| `error_type` | Category: `Syntax Error`, `Lexical Error`, `Incomplete Query`, etc. |

---

## Validated Examples

### Example 1 — SELECT with WHERE and ORDER BY

```sql
SELECT id, name, age FROM students WHERE age > 18 ORDER BY name ASC
```

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

**Result:** ✅ Valid — 16 tokens, no errors

---

### Example 2 — INSERT INTO with column list

```sql
INSERT INTO students (id, name, age) VALUES (1, 'Alice', 21)
```

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

**Result:** ✅ Valid — 18 tokens, no errors

---

### Example 3 — Lexical Error (unclosed string)

```sql
SELECT name FROM students WHERE city = 'Karachi
```

**Result:** ❌ Lexical Error
- The tokenizer reaches end of input without finding a closing `'`
- Error: *"Unclosed string literal at position 39 — the opening quote has no matching closing quote."*
- Hint: *"Add a closing single quote (') at the end of your string value."*
- The parser never runs — lexical errors are caught first

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/tokenize` | Returns token list + per-type counts |
| `POST` | `/validate` | Returns validity, errors, parser trace steps, and tokens |
| `GET` | `/examples` | Returns 20 curated examples (10 valid, 10 errors) |
| `GET` | `/health` | Health check |

### Request body (POST endpoints)

```json
{ "query": "SELECT * FROM users WHERE id = 1" }
```

### Validate response shape

```json
{
  "valid": true,
  "errors": [],
  "steps": ["Lexical analysis complete", "Parsed SELECT", "..."],
  "tokens": [{ "type": "KEYWORD", "value": "SELECT", "position": 0 }]
}
```

---

## Supported SQL Grammar

```
statement  → select | insert | update | delete

select     → SELECT [DISTINCT] [TOP n] col_list FROM identifier
             [WHERE condition] [GROUP BY col [HAVING condition]]
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

op         → = | <> | != | < | > | <= | >=
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend language | Python 3.11+ |
| Backend framework | FastAPI |
| Backend server | Uvicorn |
| Backend validation | Pydantic v2 |
| Package manager | uv |
| Frontend framework | Next.js 14 |
| Frontend language | TypeScript |
| Frontend styling | Tailwind CSS |
| Lexer | Pure Python — hand-written, no libraries |
| Parser | Recursive-descent — hand-written, no libraries |

---

## Known Limitations

These are intentional scope boundaries for this educational project:

- No `JOIN` support in SELECT
- No subqueries (nested SELECT)
- No `NOT IN` / `NOT LIKE` conditions
- Single statement only — no semicolon-separated batch queries
- No database connection or query execution

---

*Compiler Construction — Submission: June 29, 2026*
