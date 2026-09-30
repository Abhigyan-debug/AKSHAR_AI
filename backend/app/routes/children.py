from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db import Child
from .deps import get_db

router = APIRouter()


class ChildIn(BaseModel):
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")  # child codes, no names (privacy)
    grade: int = Field(ge=1, le=8)
    home_lang: str = Field(min_length=1, max_length=40)


def child_view(c: Child) -> dict:
    return {"id": c.id, "code": c.code, "grade": c.grade, "home_lang": c.home_lang, "created_at": c.created_at.isoformat()}


@router.post("/children", status_code=201)
def create_child(body: ChildIn, db: Session = Depends(get_db)):
    code = body.code.upper()
    if db.exec(select(Child).where(Child.code == code)).first():
        raise HTTPException(409, f"child code {code} already exists")
    child = Child(code=code, grade=body.grade, home_lang=body.home_lang.strip())
    db.add(child)
    db.commit()
    db.refresh(child)
    return child_view(child)


@router.get("/children")
def list_children(db: Session = Depends(get_db)):
    return [child_view(c) for c in db.exec(select(Child).order_by(Child.code))]


@router.get("/children/{child_id}")
def get_child(child_id: int, db: Session = Depends(get_db)):
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "child not found")
    return child_view(child)
