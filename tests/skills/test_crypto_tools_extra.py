"""Pure crypto encode/decode operations."""

from __future__ import annotations

from vulnclaw.skills.crypto_tools import execute, list_operations


def test_base_encodings_round_trip():
    cases = {
        "base64": ("hello", "base64_encode", "base64_decode"),
        "base32": ("hello", "base32_encode", "base32_decode"),
        "base58": ("hello", "base58_encode", "base58_decode"),
        "hex": ("hello", "hex_encode", "hex_decode"),
        "url": ("a b&c", "url_encode", "url_decode"),
        "html": ("<b>&", "html_encode", "html_decode"),
        "unicode": ("hello", "unicode_encode", "unicode_decode"),
    }
    for label, (text, enc, dec) in cases.items():
        encoded = execute(enc, text)
        assert encoded["success"], label
        decoded = execute(dec, encoded["result"])
        assert decoded["success"], label
        if label != "html":
            assert text in decoded["result"]


def test_rot13_caesar_and_morse():
    assert execute("rot13_decode", "hello")["result"] == "uryyb"
    assert execute("caesar_encode", "abc", shift=2)["result"] == "cde"
    assert execute("caesar_decode", "cde", shift=2)["result"] == "abc"
    assert "shift=3" in execute("caesar_decode", "abc")["result"]
    morse = execute("morse_encode", "sos")["result"]
    assert execute("morse_decode", morse)["result"].lower() == "sos"


def test_hashes_and_jwt():
    assert execute("md5_hash", "hello")["result"].startswith("5d41402a")
    assert execute("sha1_hash", "hello")["result"].startswith("aaf4c61d")
    assert execute("sha256_hash", "hello")["result"].startswith("2cf24dba")
    assert execute("sha512_hash", "hello")["result"].startswith("9b71d224")
    token = execute(
        "jwt_encode",
        '{"sub":"1"}',
        secret="secret",
    )
    assert token["success"]
    decoded = execute("jwt_decode", token["result"])
    assert decoded["success"]


def test_aes_round_trip():
    encrypted = execute("aes_encrypt", "hello", key="0123456789abcdef", iv="abcdef0123456789")
    assert encrypted["success"], encrypted
    decrypted = execute(
        "aes_decrypt", encrypted["result"], key="0123456789abcdef", iv="abcdef0123456789"
    )
    assert decrypted["success"]


def test_invalid_inputs_and_unknown_operation():
    assert execute("base64_decode", "!!!")["success"] is False
    assert execute("base32_decode", "!!!")["success"] is False
    assert execute("base58_decode", "!!!")["success"] is False
    assert execute("hex_decode", "zz")["success"] is False
    assert execute("missing-op", "x")["success"] is False
    assert execute("auto_decode", "aGVsbG8=")["success"] is True
    assert list_operations()
