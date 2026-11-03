"""Pinned offline data preparation; no optional native engine needed here."""

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_meta_seed_harness.providers.tokenizer import (
    TokenizerUnavailable,
    load_glm53flash_text_encoder,
    tokenizer_lock,
    verify_tokenizer_asset,
)


ROOT = Path(__file__).resolve().parents[2]


def test_installed_lock_freezes_author_revision_and_real_encoding_vectors():
    lock = tokenizer_lock()
    assert lock["schema"] == "seed/local-tokenizer-lock/v1"
    assert lock["revision"] == "46a050bec13002ad29ee795c16e61cf4fa3c4a9c"
    assert lock["scope"] == "LOCAL_TEXT_ENCODING_ONLY"
    assert lock["gateway_template_equivalence_verified"] is False
    assert lock["files"]["tokenizer.json"]["bytes"] == 20217442
    assert set(lock["files"]) == {
        "LICENSE",
        "tokenizer.json",
        "tokenizer_config.json",
        "chat_template.jinja",
    }
    vectors = (
        ROOT / "tests/fixtures/provider-tokenizer/local-encoding-v1.json"
    ).read_bytes()
    assert hashlib.sha256(vectors).hexdigest() == lock["vectors_sha256"]
    cases = json.loads(vectors)["cases"]
    assert len(cases) == 7 and len(cases[-1]["ids"]) == 17
    assert len(cases[1]["ids"]) == 5
    lock["files"].clear()
    assert len(tokenizer_lock()["files"]) == 4


@pytest.mark.parametrize(
    "raw", [b"", b"unverified-tokenizer", bytearray(b"mutable"), None]
)
def test_invalid_tokenizer_data_fails_before_engine_selection(raw):
    with patch("importlib.metadata.version") as version:
        with pytest.raises(TokenizerUnavailable, match="differs from lock"):
            load_glm53flash_text_encoder(raw)
        version.assert_not_called()


def test_same_size_substitution_fails_before_native_parsing():
    raw = b"x" * tokenizer_lock()["files"]["tokenizer.json"]["bytes"]
    with patch("importlib.metadata.version") as version:
        with pytest.raises(TokenizerUnavailable, match="differs from lock"):
            load_glm53flash_text_encoder(raw)
        version.assert_not_called()


@pytest.mark.parametrize(
    "name",
    ["../tokenizer.json", "other.json", "https://example.invalid/tokenizer.json", None],
)
def test_preparation_has_no_implicit_path_model_or_network_fallback(name):
    with pytest.raises(TokenizerUnavailable, match="unsupported"):
        verify_tokenizer_asset(name, b"unverified")
