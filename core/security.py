import hashlib
import hmac
import secrets


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    password_salt = salt or secrets.token_bytes(16)
    password_hash = hashlib.scrypt(
        password.encode("utf-8"), salt=password_salt, n=2**14, r=8, p=1, dklen=64
    )
    return password_salt.hex(), password_hash.hex()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    try:
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hash_hex)
    except ValueError:
        return False
    _, actual_hex = hash_password(password, salt)
    return hmac.compare_digest(bytes.fromhex(actual_hex), expected)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def new_admin_invite_token() -> str:
    return secrets.token_urlsafe(32)


def constant_time_equal(first: str, second: str) -> bool:
    return hmac.compare_digest(first.encode("utf-8"), second.encode("utf-8"))
