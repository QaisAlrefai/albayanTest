
import hashlib

def calculate_sha256(file_path: str, chunk_size: int = 65536) -> str:
    """
    Calculate the SHA-256 hash of a file.

    Args:
        file_path (str): Path to the file.
        chunk_size (int): Number of bytes to read at a time (default 64 KB).

    Returns:
        str: Hexadecimal SHA-256 hash of the file.
    """
    sha256_hash = hashlib.sha256()

    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                sha256_hash.update(chunk)
    except FileNotFoundError:
        raise FileNotFoundError(f"❌ File not found: {file_path}")
    except Exception as e:
        raise Exception(f"❌ Failed to calculate SHA-256: {e}")

    return sha256_hash.hexdigest()
