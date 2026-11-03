"""Pinned local GLM text encoding for offline Provider preparation.

This is not a Host tokenizer or a counter for an Anthropic request. Gateway
message conversion, templates and hidden tokens require a separate verified
contract. No network, remote Python code, credentials or Task dispatch occur.
"""

from dataclasses import dataclass, field
import hashlib
from importlib import metadata
from importlib.resources import files
import json


LOCK_RESOURCE = "data/provider-tokenizers/glm-5.3-flash-v1.json"
MAX_TEXT_BYTES = 1024 * 1024


class TokenizerUnavailable(ValueError):
    """Preparation cannot establish the pinned local implementation."""


def tokenizer_lock():
    """Return a fresh copy of the installed, versioned preparation inputs."""
    return json.loads(
        files("agent_meta_seed_harness").joinpath(LOCK_RESOURCE).read_bytes()
    )


def verify_tokenizer_asset(name, raw):
    """Verify an explicit local input; never discover a cache or fetch a URL."""
    lock = tokenizer_lock()
    if type(name) is not str or name not in lock["files"]:
        raise TokenizerUnavailable("unsupported tokenizer preparation input")
    expected = lock["files"][name]
    if (
        type(raw) is not bytes
        or len(raw) != expected["bytes"]
        or hashlib.sha256(raw).hexdigest() != expected["sha256"]
    ):
        raise TokenizerUnavailable("tokenizer preparation input differs from lock")
    return raw


@dataclass(frozen=True, slots=True)
class LocalTextEncoder:
    """An offline native utility, never an ordinary Host DTO or authority."""

    tokenizer_id: str
    _engine: object = field(repr=False, compare=False)

    def encode(self, text):
        if type(text) is not str or len(text) > MAX_TEXT_BYTES:
            raise ValueError("tokenizer text requires a bounded Unicode string")
        try:
            size = len(text.encode("utf-8"))
        except UnicodeError:
            raise ValueError("tokenizer text requires valid Unicode") from None
        if size > MAX_TEXT_BYTES:
            raise ValueError("tokenizer text exceeds byte ceiling")
        try:
            encoded = tuple(self._engine.encode(text, add_special_tokens=False).ids)
        except Exception:
            raise TokenizerUnavailable("local tokenizer encoding failed") from None
        if len(encoded) > MAX_TEXT_BYTES or any(
            type(item) is not int or not 0 <= item < 2**31 for item in encoded
        ):
            raise TokenizerUnavailable("local tokenizer returned invalid token IDs")
        return encoded

    def count(self, text):
        return len(self.encode(text))


def load_glm53flash_text_encoder(tokenizer_json):
    """Use only hash-verified data and the explicitly pinned native engine.

    The optional dependency is loaded only here. Package installation/build and
    minimal execution do not require it. The model template is not executed.
    """
    raw = verify_tokenizer_asset("tokenizer.json", tokenizer_json)
    lock = tokenizer_lock()
    try:
        if metadata.version("tokenizers") != lock["engine"]["version"]:
            raise TokenizerUnavailable("pinned tokenizer engine version unavailable")
        from tokenizers import Tokenizer

        engine = Tokenizer.from_str(raw.decode("utf-8"))
        if engine.padding is not None or engine.truncation is not None:
            raise TokenizerUnavailable("local tokenizer may not pad or truncate")
    except TokenizerUnavailable:
        raise
    except Exception:
        raise TokenizerUnavailable("pinned tokenizer engine unavailable") from None
    return LocalTextEncoder(lock["tokenizer_id"], engine)
