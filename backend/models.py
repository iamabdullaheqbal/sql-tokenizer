from pydantic import BaseModel


class TokenizeRequest(BaseModel):
    query: str


class ValidateRequest(BaseModel):
    query: str
