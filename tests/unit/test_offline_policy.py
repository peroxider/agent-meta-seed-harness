"""Offline guard permits only CPython's scoped local wakeup socketpair."""

import socket

import pytest


def test_stdlib_socketpair_works_without_granting_general_network_access():
    first, second = socket.socketpair()
    try:
        first.sendall(b"wake")
        assert second.recv(4) == b"wake"
    finally:
        first.close()
        second.close()
    for address in (("127.0.0.1", 9), ("192.0.2.1", 443)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as channel:
            with pytest.raises(AssertionError, match="offline Seed suite"):
                channel.connect(address)


def test_connect_ex_cannot_bypass_offline_guard():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as channel:
        with pytest.raises(AssertionError, match="offline Seed suite"):
            channel.connect_ex(("127.0.0.1", 9))
