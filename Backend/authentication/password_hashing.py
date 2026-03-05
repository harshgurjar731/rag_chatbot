import bcrypt

MAX_BCRYPT_BYTES = 72


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    bcrypt has a hard 72-byte limit. We truncate the UTF-8-encoded
    password to 72 bytes before hashing to stay within that limit.
    """
    password_bytes = password.encode("utf-8")[:MAX_BCRYPT_BYTES]
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    plain_bytes = plain.encode("utf-8")[:MAX_BCRYPT_BYTES]
    return bcrypt.checkpw(plain_bytes, hashed.encode("utf-8"))