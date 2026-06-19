from typing import List, Optional

from tokenizer import Token, AGGREGATE_FUNCTIONS


class SyntaxError_(Exception):
    def __init__(self, message: str, position: Optional[int] = None):
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

    def peek(self, offset: int = 1) -> Optional[Token]:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return None

    def consume(self, expected_value=None, expected_type=None) -> Optional[Token]:
        tok = self.current()
        if tok is None:
            raise SyntaxError_(
                f"Unexpected end of query, expected {expected_value or expected_type}", -1
            )
        if expected_value and tok.value.upper() != expected_value.upper():
            raise SyntaxError_(
                f"Expected '{expected_value}' but found '{tok.value}' at position {tok.position}",
                tok.position,
            )
        if expected_type and tok.type != expected_type:
            raise SyntaxError_(
                f"Expected {expected_type} but found {tok.type} '{tok.value}' at position {tok.position}",
                tok.position,
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

    def add_step(self, msg: str):
        self.steps.append(msg)

    # ── Expression parsing ──────────────────────────────────────────────────

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
        # aggregate function call
        if tok.type in ("KEYWORD", "AGGREGATE_FUNCTION") and tok.value in AGGREGATE_FUNCTIONS:
            self.pos += 1
            self.consume("(", "PUNCTUATION")
            if self.match("*", "OPERATOR") or self.match("*", "WILDCARD"):
                self.pos += 1
            else:
                self.parse_value()
            self.consume(")", "PUNCTUATION")
            return tok
        raise SyntaxError_(
            f"Unexpected token '{tok.value}' at position {tok.position}", tok.position
        )

    def parse_column_expr(self):
        """column [AS alias] | aggregate(...) [AS alias]"""
        tok = self.current()
        if tok is None:
            raise SyntaxError_("Expected column but reached end of query", -1)
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
        """col OP value | col IS [NOT] NULL | col BETWEEN val AND val | col IN (...)"""
        self.parse_value()

        tok = self.current()
        if tok is None:
            raise SyntaxError_("Expected operator in condition", -1)

        if tok.value.upper() == "IS":
            self.pos += 1
            if self.match("NOT"):
                self.pos += 1
            self.consume("NULL")
            return

        if tok.value.upper() == "BETWEEN":
            self.pos += 1
            self.parse_value()
            self.consume("AND")
            self.parse_value()
            return

        if tok.value.upper() == "IN":
            self.pos += 1
            self.consume("(", "PUNCTUATION")
            self.parse_value()
            while self.match(",", "PUNCTUATION"):
                self.pos += 1
                self.parse_value()
            self.consume(")", "PUNCTUATION")
            return

        if tok.value.upper() == "LIKE":
            self.pos += 1
            self.parse_value()
            return

        if tok.type == "OPERATOR":
            self.pos += 1
            self.parse_value()
            return

        raise SyntaxError_(
            f"Expected operator in condition but found '{tok.value}' at position {tok.position}",
            tok.position,
        )

    def parse_where_clause(self):
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

    # ── Statement parsers ───────────────────────────────────────────────────

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
            raise SyntaxError_(
                f"Unknown statement type '{tok.value}'. Expected SELECT, INSERT, UPDATE, or DELETE.",
                tok.position,
            )
        # Trailing content check (allow optional semicolon)
        remaining = self.current()
        if remaining and not (remaining.type == "PUNCTUATION" and remaining.value == ";"):
            raise SyntaxError_(
                f"Unexpected token '{remaining.value}' at position {remaining.position} after statement end.",
                remaining.position,
            )
