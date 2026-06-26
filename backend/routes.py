from fastapi import APIRouter

from models import TokenizeRequest, ValidateRequest
from parser import Parser, SyntaxError_
from tokenizer import tokenize

router = APIRouter()


@router.post("/tokenize")
def tokenize_query(req: TokenizeRequest):
    tokens = tokenize(req.query)
    token_dicts = [t.to_dict() for t in tokens]

    type_counts: dict[str, int] = {}
    for t in token_dicts:
        type_counts[t["type"]] = type_counts.get(t["type"], 0) + 1

    return {
        "tokens": token_dicts,
        "count": len(token_dicts),
        "type_counts": type_counts,
    }


@router.post("/validate")
def validate_query(req: ValidateRequest):
    tokens = tokenize(req.query)

    if not tokens:
        return {
            "valid": False,
            "errors": [{"message": "Empty query", "position": 0}],
            "steps": [],
            "tokens": [],
        }

    lex_errors = []
    clean_tokens = []
    for t in tokens:
        if t.type == "UNKNOWN":
            lex_errors.append({
                "message": f"Unknown character '{t.value}' at position {t.position} — this character is not valid in SQL.",
                "hint": f"Remove or replace the character '{t.value}'. SQL supports letters, numbers, operators like =, <, >, and quotes for strings.",
                "position": t.position,
                "error_type": "Lexical Error",
            })
        else:
            clean_tokens.append(t)

    if lex_errors:
        return {
            "valid": False,
            "errors": lex_errors,
            "steps": ["Lexical analysis failed — one or more invalid characters were found in the query."],
            "tokens": [t.to_dict() for t in tokens],
        }

    parser = Parser(clean_tokens)
    steps = [
        "Lexical analysis complete — no unknown characters found",
        "Starting syntax analysis...",
    ]
    try:
        parser.parse()
        steps += parser.steps
        return {
            "valid": True,
            "errors": [],
            "steps": steps,
            "tokens": [t.to_dict() for t in tokens],
        }
    except SyntaxError_ as e:
        steps += parser.steps
        return {
            "valid": False,
            "errors": [{
                "message": str(e),
                "hint": e.hint,
                "position": e.position,
                "error_type": e.error_type,
            }],
            "steps": steps,
            "tokens": [t.to_dict() for t in tokens],
        }
    except Exception as e:
        steps += parser.steps
        return {
            "valid": False,
            "errors": [{
                "message": f"An unexpected error occurred: {str(e)}",
                "hint": "This may be an internal error. Check that your query is a valid SQL SELECT, INSERT, UPDATE, or DELETE statement.",
                "position": -1,
                "error_type": "Internal Error",
            }],
            "steps": steps,
            "tokens": [t.to_dict() for t in tokens],
        }


@router.get("/examples")
def get_examples():
    return {
        "examples": [
            # ── Valid queries ──────────────────────────────────────────
            {
                "label": "Simple SELECT",
                "query": "SELECT id, name, age FROM students WHERE age > 18 ORDER BY name ASC",
            },
            {
                "label": "Aggregate Functions",
                "query": "SELECT COUNT(*), AVG(salary) FROM employees WHERE department = 'Engineering'",
            },
            {
                "label": "INSERT",
                "query": "INSERT INTO students (id, name, age) VALUES (1, 'Alice', 21)",
            },
            {
                "label": "UPDATE with WHERE",
                "query": "UPDATE employees SET salary = 75000, department = 'HR' WHERE id = 5",
            },
            {
                "label": "DELETE",
                "query": "DELETE FROM orders WHERE status = 'cancelled' AND total < 100",
            },
            {
                "label": "SELECT DISTINCT",
                "query": "SELECT DISTINCT department FROM employees ORDER BY department ASC",
            },
            {
                "label": "GROUP BY with HAVING",
                "query": "SELECT department, COUNT(*) FROM employees GROUP BY department HAVING COUNT(*) > 5",
            },
            {
                "label": "SELECT with BETWEEN",
                "query": "SELECT name, salary FROM employees WHERE salary BETWEEN 50000 AND 80000",
            },
            {
                "label": "SELECT with IN",
                "query": "SELECT name FROM students WHERE grade IN ('A', 'B', 'C')",
            },
            {
                "label": "SELECT with IS NULL",
                "query": "SELECT name FROM employees WHERE manager_id IS NULL",
            },
            # ── Error queries ──────────────────────────────────────────
            {
                "label": "❌ Missing FROM",
                "query": "SELECT name age WHERE id = 1",
            },
            {
                "label": "❌ Missing WHERE operator",
                "query": "SELECT * FROM students WHERE age",
            },
            {
                "label": "❌ Missing VALUES keyword",
                "query": "INSERT INTO students (id, name) (1, 'Bob')",
            },
            {
                "label": "❌ Missing SET in UPDATE",
                "query": "UPDATE employees salary = 5000 WHERE id = 3",
            },
            {
                "label": "❌ Unknown statement (SHOW)",
                "query": "SHOW TABLES FROM database",
            },
            {
                "label": "❌ Invalid character (@)",
                "query": "SELECT name FROM students WHERE email = @input",
            },
            {
                "label": "❌ Keyword used as table name",
                "query": "SELECT id FROM SELECT WHERE id = 1",
            },
            {
                "label": "❌ Incomplete BETWEEN",
                "query": "SELECT name FROM employees WHERE salary BETWEEN 1000",
            },
            {
                "label": "❌ Missing closing parenthesis",
                "query": "INSERT INTO orders (id, total VALUES (5, 200)",
            },
            {
                "label": "❌ Extra tokens after statement",
                "query": "DELETE FROM orders WHERE id = 1 ORDER name",
            },
        ]
    }


@router.get("/health")
def health():
    return {"status": "ok"}
