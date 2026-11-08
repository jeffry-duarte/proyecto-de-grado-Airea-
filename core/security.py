import hashlib
import hmac
import secrets
import time
from typing import Any

import bcrypt
import jwt


from core.config import JWT_SECRET, SESSION_LIFETIME_SECONDS


def hash_scrypt_password(
    password: str, salt: bytes | None = None
) -> tuple[str, str]:
    password_salt = salt or secrets.token_bytes(16)
    password_hash = hashlib.scrypt(
        password.encode("utf-8"), salt=password_salt, n=2**14, r=8, p=1, dklen=64
    )
    return password_salt.hex(), password_hash.hex()


def verify_scrypt_password(
    password: str, salt_hex: str, expected_hash_hex: str
) -> bool:
    try:
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hash_hex)
    except ValueError:
        return False
    _, actual_hex = hash_scrypt_password(password, salt)
    return hmac.compare_digest(bytes.fromhex(actual_hex), expected)


def _bcrypt_input(password: str) -> bytes:
    digest = hashlib.sha256(
        b"AIREA bcrypt password v1\x00" + password.encode("utf-8")
    ).hexdigest()
    return digest.encode("ascii")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_bcrypt_input(password), bcrypt.gensalt()).decode("ascii")


def verify_password(
    password: str, scheme: str, salt_hex: str, expected_hash: str
) -> bool:
    if scheme == "bcrypt":
        try:
            return bcrypt.checkpw(
                _bcrypt_input(password), expected_hash.encode("ascii")
            )
        except (ValueError, TypeError, UnicodeEncodeError):
            return False
    if scheme == "scrypt":
        return verify_scrypt_password(password, salt_hex, expected_hash)
    return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def validate_jwt_secret() -> None:
    if len(JWT_SECRET.encode("utf-8")) < 32:
        raise RuntimeError(
            "AIREA_JWT_SECRET debe contener al menos 32 bytes aleatorios."
        )


def create_access_token(user_id: str, role: str) -> str:
    validate_jwt_secret()
    issued_at = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "role": role,
            "iat": issued_at,
            "exp": issued_at + SESSION_LIFETIME_SECONDS,
            "jti": secrets.token_urlsafe(16),
        },
        JWT_SECRET,
        algorithm="HS256",
    )


def decode_access_token(token: str) -> dict[str, Any]:
    validate_jwt_secret()
    if len(token) > 4096:
        raise ValueError("El token excede el tamaño permitido.")
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            options={"require": ["sub", "role", "iat", "exp", "jti"]},
        )
    except jwt.InvalidTokenError as error:
        raise ValueError("El token no es válido.") from error
    if not all(
        isinstance(payload.get(key), str) and payload[key]
        for key in ("sub", "role", "jti")
    ):
        raise ValueError("El token no es válido.")
    return payload


def new_admin_invite_token() -> str:
    return secrets.token_urlsafe(32)


def constant_time_equal(first: str, second: str) -> bool:
    return hmac.compare_digest(first.encode("utf-8"), second.encode("utf-8"))
