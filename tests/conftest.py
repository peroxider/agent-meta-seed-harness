"""Offline Seed tests must never contact a remote Provider."""

import socket
from contextvars import ContextVar
import pytest


@pytest.fixture(autouse=True)
def deny_internet(monkeypatch):
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_socketpair = socket.socketpair
    internal_pair = ContextVar("seed_stdlib_socketpair", default=False)

    def permitted_self_pipe(address):
        return internal_pair.get() and isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1")

    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6) and not permitted_self_pipe(address):
            raise AssertionError("offline Seed suite forbids Internet sockets")
        return original_connect(sock, address)

    def connect_ex(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6) and not permitted_self_pipe(address):
            raise AssertionError("offline Seed suite forbids Internet sockets")
        return original_connect_ex(sock, address)

    def socketpair(*args, **kwargs):
        # Windows CPython implements asyncio's wakeup socketpair with a scoped
        # loopback connection. This is not a Runtime transport fallback. General
        # loopback and Internet connections remain forbidden outside this call.
        token = internal_pair.set(True)
        try:
            return original_socketpair(*args, **kwargs)
        finally:
            internal_pair.reset(token)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "socketpair", socketpair)
