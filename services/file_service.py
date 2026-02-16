import hashlib
from pathlib import Path


def ensure_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_uploaded_file(uploaded_file, destination_dir: str | Path, destination_name: str | None = None):
    target_dir = ensure_dir(destination_dir)
    file_name = destination_name or uploaded_file.name
    file_bytes = uploaded_file.getvalue()
    target_path = target_dir / file_name
    target_path.write_bytes(file_bytes)
    return target_path, sha256_bytes(file_bytes)
