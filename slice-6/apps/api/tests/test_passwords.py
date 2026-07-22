from app.auth.passwords import hash_password, needs_rehash, verify_password


def test_hash_and_verify_roundtrip():
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h)
    assert not verify_password("wrong password", h)


def test_hashes_are_salted_and_unique():
    a = hash_password("samepassword")
    b = hash_password("samepassword")
    assert a != b  # different salts
    assert verify_password("samepassword", a)
    assert verify_password("samepassword", b)


def test_empty_password_rejected():
    import pytest
    with pytest.raises(ValueError):
        hash_password("")


def test_verify_handles_garbage():
    assert not verify_password("x", "not-a-valid-hash")
    assert not verify_password("x", "")


def test_needs_rehash_on_lower_iterations():
    weak = hash_password("pw", iterations=1000)
    assert needs_rehash(weak, iterations=240000)
    strong = hash_password("pw", iterations=240000)
    assert not needs_rehash(strong, iterations=240000)
