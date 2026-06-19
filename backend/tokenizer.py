

from typing import List


SQL_KEYWORDS = {
    "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES",
    "UPDATE", "SET", "DELETE", "AND", "OR", "NOT",
    "ORDER", "BY", "GROUP", "HAVING", "LIMIT", "OFFSET",
    "ASC", "DESC", "DISTINCT", "AS", "NULL", "IS",
    "IN", "LIKE", "BETWEEN", "COUNT", "SUM", "AVG",
    "MIN", "MAX", "ALL", "EXISTS", "CASE", "WHEN",
    "THEN", "ELSE", "END", "TOP"
}

AGGREGATE_FUNCTIONS = {"COUNT", "SUM", "AVG", "MIN", "MAX"}

OPERATORS = {
    "=", "<>", "!=", "<", ">", "<=", ">=", "+", "-", "*", "/"
}

PUNCTUATION = {"(", ")", ",", ";", "."}


class Token:
    def __init__(self, type: str, value: str, position: int):
        self.type = type
        self.value = value
        self.position = position

    def to_dict(self):
        return {"type": self.type, "value": self.value, "position": self.position}


def tokenize(query: str) -> List[Token]:
    tokens = []
    i = 0
    n = len(query)

    while i < n:
        # Skip whitespace
        if query[i] in (' ', '\t', '\n', '\r'):
            i += 1
            continue

        pos = i

        # String literal: 'value'
        if query[i] == "'":
            i += 1
            start = i
            while i < n and query[i] != "'":
                i += 1
            value = query[start:i]
            if i < n:
                i += 1  # skip closing quote
            tokens.append(Token("STRING", value, pos))
            continue

        # Number literal (integer or decimal, optional leading minus)
        if query[i].isdigit() or (query[i] == '-' and i + 1 < n and query[i + 1].isdigit()):
            start = i
            if query[i] == '-':
                i += 1
            while i < n and (query[i].isdigit() or query[i] == '.'):
                i += 1
            tokens.append(Token("NUMBER", query[start:i], pos))
            continue

        # Identifier or keyword
        if query[i].isalpha() or query[i] == '_':
            start = i
            while i < n and (query[i].isalnum() or query[i] == '_'):
                i += 1
            word = query[start:i]
            upper = word.upper()
            if upper in SQL_KEYWORDS:
                token_type = "AGGREGATE_FUNCTION" if upper in AGGREGATE_FUNCTIONS else "KEYWORD"
                tokens.append(Token(token_type, upper, pos))
            else:
                tokens.append(Token("IDENTIFIER", word, pos))
            continue

        # Two-character operators  (<>, !=, <=, >=)
        if i + 1 < n and query[i:i+2] in ("<>", "!=", "<=", ">="):
            tokens.append(Token("OPERATOR", query[i:i+2], pos))
            i += 2
            continue

        # Single-character operators
        if query[i] in OPERATORS:
            tok_type = "OPERATOR"
            if query[i] == "*":
                # Wildcard in SELECT * context — previous token is SELECT, DISTINCT, or a comma
                if tokens and tokens[-1].type == "KEYWORD" and tokens[-1].value in ("SELECT", "DISTINCT"):
                    tok_type = "WILDCARD"
                elif tokens and tokens[-1].value == ",":
                    tok_type = "WILDCARD"
            tokens.append(Token(tok_type, query[i], pos))
            i += 1
            continue

        # Punctuation
        if query[i] in PUNCTUATION:
            tokens.append(Token("PUNCTUATION", query[i], pos))
            i += 1
            continue

        # Unknown character (lexical error)
        tokens.append(Token("UNKNOWN", query[i], pos))
        i += 1

    return tokens
