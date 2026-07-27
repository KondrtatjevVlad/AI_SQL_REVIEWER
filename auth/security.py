import base64
import hashlib
import hmac
import os


SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
KEY_LENGTH = 64
SALT_LENGTH = 16


def hash_password(password: str) -> str:
    """Create a secure scrypt hash for a password."""
    if not password:
        raise ValueError("Password cannot be empty.")

    salt = os.urandom(SALT_LENGTH)

    password_hash = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=KEY_LENGTH,
    )

    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(password_hash).decode("ascii")

    return (
        f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}"
        f"${salt_b64}${hash_b64}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a password against the stored scrypt hash."""
    try:
        algorithm, n, r, p, salt_b64, hash_b64 = stored_hash.split("$")

        if algorithm != "scrypt":
            return False

        salt = base64.b64decode(salt_b64)
        expected_hash = base64.b64decode(hash_b64)

        actual_hash = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected_hash),
        )

        return hmac.compare_digest(actual_hash, expected_hash)

    except (ValueError, TypeError):
        return False