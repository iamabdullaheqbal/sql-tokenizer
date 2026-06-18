from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from tokenizer import Token, tokenize, AGGREGATE_FUNCTIONS

app = FastAPI(title="SQL Tokenizer & Validator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────

class TokenizeRequest(BaseModel):
    query: str

class ValidateRequest(BaseModel):
    query: str


# ─────────────────────────────────────────────
# SYNTAX VALIDATION
# ─────────────────────────────────────────────

class SyntaxError_(Exception):
    def __init__(self, message, position=None):
        super().__init__(message)
        self.position = position
        self.msg = message


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.errors = []
        self.steps = []

    def current(self) -> Optional[Token]:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def peek(self, offset=1) -> Optional[Token]:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return None

    def consume(self, expected_value=None, expected_type=None) -> Optional[Token]:
        tok = self.current()
        if tok is None:
            raise SyntaxError_(f"Unexpected end of query, expected {expected_value or expected_type}", -1)
        if expected_value and tok.value.upper() != expected_value.upper():
            raise SyntaxError_(
                f"Expected '{expected_value}' but found '{tok.value}' at position {tok.position}",
                tok.position
            )
        if expected_type and tok.type != expected_type:
            raise SyntaxError_(
                f"Expected {expected_type} but found {tok.type} '{tok.value}' at position {tok.position}",
                tok.position
            )
        self.pos += 1
        return tok

    def match(self, value=None, type_=None) -> bool:
        tok = self.current()
        if tok is None:
            return False
        if value and type_:
            return tok.value.upper() == value.upper() and tok.type == type_
        if value:
            return tok.value.upper() == value.upper()
        if type_:
            return tok.type == type_
        return False

    def add_step(self, msg):
        self.steps.append(msg)

    # ── Expression parsing ──

    def parse_value(self):
        """Parse a single value: identifier, number, string, or NULL."""
        tok = self.current()
        if tok is None:
            raise SyntaxError_("Expected value but reached end of query", -1)
        if tok.type in ("IDENTIFIER", "NUMBER", "STRING", "WILDCARD"):
            self.pos += 1
            return tok
        if tok.type == "KEYWORD" and tok.value == "NULL":
            self.pos += 1
            return tok
        # aggregate function
        if tok.type in ("KEYWORD", "AGGREGATE_FUNCTION") and tok.value in AGGREGATE_FUNCTIONS:
            self.pos += 1
            self.consume("(", "PUNCTUATION")
            if self.match("*", "OPERATOR") or self.match("*", "WILDCARD"):
                self.pos += 1
            else:
                self.parse_value()
            self.consume(")", "PUNCTUATION")
            return tok
        raise SyntaxError_(f"Unexpected token '{tok.value}' at position {tok.position}", tok.position)

    def parse_column_expr(self):
        """column [AS alias] | aggregate(...) [AS alias]"""
        tok = self.current()
        if tok is None:
            raise SyntaxError_("Expected column but reached end of query", -1)
        # Could be * (wildcard)
        if tok.type in ("OPERATOR", "WILDCARD") and tok.value == "*":
            self.pos += 1
            return
        self.parse_value()
        # optional dot notation: table.column
        if self.match(".", "PUNCTUATION"):
            self.pos += 1
            self.parse_value()
        # optional alias
        if self.match("AS"):
            self.pos += 1
            self.consume(expected_type="IDENTIFIER")

    def parse_column_list(self):
        """col1, col2, ..."""
        self.parse_column_expr()
        while self.match(",", "PUNCTUATION"):
            self.pos += 1
            self.parse_column_expr()

    def parse_condition(self):
        """Simple: col OP value | col IS [NOT] NULL | col BETWEEN val AND val | col IN (...)"""
        self.parse_value()

        tok = self.current()
        if tok is None:
            raise SyntaxError_("Expected operator in condition", -1)

        # IS NULL / IS NOT NULL
        if tok.value.upper() == "IS":
            self.pos += 1
            if self.match("NOT"):
                self.pos += 1
            self.consume("NULL")
            return

        # BETWEEN
        if tok.value.upper() == "BETWEEN":
            self.pos += 1
            self.parse_value()
            self.consume("AND")
            self.parse_value()
            return

        # IN (...)
        if tok.value.upper() == "IN":
            self.pos += 1
            self.consume("(", "PUNCTUATION")
            self.parse_value()
            while self.match(",", "PUNCTUATION"):
                self.pos += 1
                self.parse_value()
            self.consume(")", "PUNCTUATION")
            return

        # LIKE
        if tok.value.upper() == "LIKE":
            self.pos += 1
            self.parse_value()
            return

        # Standard comparison
        if tok.type == "OPERATOR":
            self.pos += 1
            self.parse_value()
            return

        raise SyntaxError_(f"Expected operator in condition but found '{tok.value}' at position {tok.position}", tok.position)

    def parse_where_clause(self):
        """WHERE condition [AND|OR condition ...]"""
        self.add_step("Parsing WHERE clause")
        self.consume("WHERE")
        self.parse_condition()
        while self.match("AND") or self.match("OR"):
            self.pos += 1
            self.parse_condition()

    def parse_order_by(self):
        self.add_step("Parsing ORDER BY clause")
        self.consume("ORDER")
        self.consume("BY")
        self.parse_value()
        if self.match("ASC") or self.match("DESC"):
            self.pos += 1
        while self.match(",", "PUNCTUATION"):
            self.pos += 1
            self.parse_value()
            if self.match("ASC") or self.match("DESC"):
                self.pos += 1

    def parse_group_by(self):
        self.add_step("Parsing GROUP BY clause")
        self.consume("GROUP")
        self.consume("BY")
        self.parse_value()
        while self.match(",", "PUNCTUATION"):
            self.pos += 1
            self.parse_value()
        if self.match("HAVING"):
            self.pos += 1
            self.parse_condition()

    def parse_limit(self):
        self.add_step("Parsing LIMIT clause")
        self.consume("LIMIT")
        self.consume(expected_type="NUMBER")
        if self.match("OFFSET"):
            self.pos += 1
            self.consume(expected_type="NUMBER")

    # ── Statement parsers ──

    def parse_select(self):
        self.add_step("Detected SELECT statement")
        self.consume("SELECT")
        if self.match("DISTINCT"):
            self.pos += 1
        if self.match("TOP"):
            self.pos += 1
            self.consume(expected_type="NUMBER")
        self.add_step("Parsing SELECT column list")
        self.parse_column_list()
        self.add_step("Parsing FROM clause")
        self.consume("FROM")
        self.consume(expected_type="IDENTIFIER")
        # optional table alias
        if self.current() and self.current().type == "IDENTIFIER":
            self.pos += 1
        if self.match("WHERE"):
            self.parse_where_clause()
        if self.match("GROUP"):
            self.parse_group_by()
        if self.match("ORDER"):
            self.parse_order_by()
        if self.match("LIMIT"):
            self.parse_limit()
        self.add_step("SELECT statement parsed successfully")

    def parse_insert(self):
        self.add_step("Detected INSERT statement")
        self.consume("INSERT")
        self.consume("INTO")
        self.consume(expected_type="IDENTIFIER")
        # optional column list
        if self.match("(", "PUNCTUATION"):
            self.pos += 1
            self.add_step("Parsing column list in INSERT")
            self.consume(expected_type="IDENTIFIER")
            while self.match(",", "PUNCTUATION"):
                self.pos += 1
                self.consume(expected_type="IDENTIFIER")
            self.consume(")", "PUNCTUATION")
        self.add_step("Parsing VALUES clause")
        self.consume("VALUES")

        self.consume("(", "PUNCTUATION")
        self.parse_value()
        while self.match(",", "PUNCTUATION"):
            self.pos += 1
            self.parse_value()
        self.consume(")", "PUNCTUATION")
        self.add_step("INSERT statement parsed successfully")

    def parse_update(self):
        self.add_step("Detected UPDATE statement")
        self.consume("UPDATE")
        self.consume(expected_type="IDENTIFIER")
        self.add_step("Parsing SET clause")
        self.consume("SET")
        # col = val
        self.consume(expected_type="IDENTIFIER")
        self.consume("=", "OPERATOR")
        self.parse_value()
        while self.match(",", "PUNCTUATION"):
            self.pos += 1
            self.consume(expected_type="IDENTIFIER")
            self.consume("=", "OPERATOR")
            self.parse_value()
        if self.match("WHERE"):
            self.parse_where_clause()
        self.add_step("UPDATE statement parsed successfully")

    def parse_delete(self):
        self.add_step("Detected DELETE statement")
        self.consume("DELETE")
        self.consume("FROM")
        self.consume(expected_type="IDENTIFIER")
        if self.match("WHERE"):
            self.parse_where_clause()
        self.add_step("DELETE statement parsed successfully")

    def parse(self):
        tok = self.current()
        if tok is None:
            raise SyntaxError_("Empty query", 0)
        kw = tok.value.upper()
        if kw == "SELECT":
            self.parse_select()
        elif kw == "INSERT":
            self.parse_insert()
        elif kw == "UPDATE":
            self.parse_update()
        elif kw == "DELETE":
            self.parse_delete()
        else:
            raise SyntaxError_(f"Unknown statement type '{tok.value}'. Expected SELECT, INSERT, UPDATE, or DELETE.", tok.position)
        # Check trailing content (ignoring optional semicolon)
        remaining = self.current()
        if remaining and not (remaining.type == "PUNCTUATION" and remaining.value == ";"):
            raise SyntaxError_(
                f"Unexpected token '{remaining.value}' at position {remaining.position} after statement end.",
                remaining.position
            )


# ─────────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────────

@app.post("/tokenize")
def tokenize_query(req: TokenizeRequest):
    tokens = tokenize(req.query)
    token_dicts = [t.to_dict() for t in tokens]

    # Build token type counts
    type_counts = {}
    for t in token_dicts:
        type_counts[t["type"]] = type_counts.get(t["type"], 0) + 1

    return {
        "tokens": token_dicts,
        "count": len(token_dicts),
        "type_counts": type_counts
    }


@app.post("/validate")
def validate_query(req: ValidateRequest):
    # Step 1: Tokenize
    tokens = tokenize(req.query)

    if not tokens:
        return {
            "valid": False,
            "errors": [{"message": "Empty query", "position": 0}],
            "steps": [],
            "tokens": []
        }

    # Filter out unknowns as lexical errors
    lex_errors = []
    clean_tokens = []
    for t in tokens:
        if t.type == "UNKNOWN":
            lex_errors.append({
                "message": f"Lexical error: Unknown character '{t.value}' at position {t.position}",
                "position": t.position
            })
        else:
            clean_tokens.append(t)

    if lex_errors:
        return {
            "valid": False,
            "errors": lex_errors,
            "steps": ["Lexical analysis failed — unknown characters found"],
            "tokens": [t.to_dict() for t in tokens]
        }

    # Step 2: Parse
    parser = Parser(clean_tokens)
    steps = ["Lexical analysis complete — no unknown characters found", "Starting syntax analysis..."]
    try:
        parser.parse()
        steps += parser.steps
        return {
            "valid": True,
            "errors": [],
            "steps": steps,
            "tokens": [t.to_dict() for t in tokens]
        }
    except SyntaxError_ as e:
        steps += parser.steps
        return {
            "valid": False,
            "errors": [{"message": str(e), "position": e.position}],
            "steps": steps,
            "tokens": [t.to_dict() for t in tokens]
        }
    except Exception as e:
        steps += parser.steps
        return {
            "valid": False,
            "errors": [{"message": f"Unexpected error: {str(e)}", "position": -1}],
            "steps": steps,
            "tokens": [t.to_dict() for t in tokens]
        }


@app.get("/examples")
def get_examples():
    return {
        "examples": [
            {
                "label": "Simple SELECT",
                "query": "SELECT id, name, age FROM students WHERE age > 18 ORDER BY name ASC"
            },
            {
                "label": "SELECT with aggregate",
                "query": "SELECT COUNT(*), AVG(salary) FROM employees WHERE department = 'Engineering'"
            },
            {
                "label": "INSERT",
                "query": "INSERT INTO students (id, name, age) VALUES (1, 'Alice', 21)"
            },
            {
                "label": "UPDATE with WHERE",
                "query": "UPDATE employees SET salary = 75000, department = 'HR' WHERE id = 5"
            },
            {
                "label": "DELETE",
                "query": "DELETE FROM orders WHERE status = 'cancelled' AND total < 100"
            },
            {
                "label": "SELECT DISTINCT",
                "query": "SELECT DISTINCT department FROM employees ORDER BY department ASC"
            }
        ]
    }


@app.get("/health")
def health():
    return {"status": "ok"}
