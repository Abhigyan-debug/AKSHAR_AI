from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..security import client_id

router = APIRouter()


class LoginIn(BaseModel):
    pin: str = Field(min_length=1, max_length=64)


@router.post("/auth/login")
def login(body: LoginIn, request: Request):
    auth = request.app.state.auth
    if not auth.check_pin(body.pin, client_id(request)):
        raise HTTPException(401, "Wrong PIN")
    token, exp = auth.issue_token()
    return {"token": token, "expires_at": exp}
