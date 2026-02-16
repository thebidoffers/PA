from services.file_service import sha256_bytes


def test_sha256_bytes_is_deterministic():
    sample = b"prospectus-automation"
    assert sha256_bytes(sample) == sha256_bytes(sample)
