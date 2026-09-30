"""Shared route dependencies. create_app() sets these on app.state."""

from fastapi import Request


def get_db(request: Request):
    yield from request.app.state.get_db()


def transcriber(request: Request):
    return request.app.state.transcriber


def llm_client(request: Request):
    return request.app.state.llm_client


def storage_dir(request: Request):
    return request.app.state.storage_dir
