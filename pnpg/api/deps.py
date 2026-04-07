"""Shared FastAPI dependency helpers."""

from fastapi import Request


def get_db_pool(request: Request):
    return request.app.state.db_pool


def get_config(request: Request) -> dict:
    return request.app.state.config


def get_detector_state(request: Request):
    return request.app.state.detector_state


def get_ws_manager(request: Request):
    return getattr(request.app.state, "ws_manager", None)
