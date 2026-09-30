from fastapi import APIRouter, HTTPException

from ..config import load_test

router = APIRouter()


@router.get("/tests/{lang}")
def get_test(lang: str):
    if lang not in ("hi", "en"):
        raise HTTPException(404, "unknown test language")
    return load_test(lang)
