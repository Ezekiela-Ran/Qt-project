import hashlib
import hmac
import os


PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 390000


def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    secret = str(password or "")
    if not secret:
        raise ValueError("Le mot de passe est obligatoire.")

    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, int(iterations))
    return f"{PBKDF2_ALGORITHM}${int(iterations)}${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iteration_text, salt_hex, digest_hex = str(encoded_hash or "").split("$", 3)
    except ValueError:
        return False

    if algorithm != PBKDF2_ALGORITHM:
        return False

    try:
        iterations = int(iteration_text)
        salt = bytes.fromhex(salt_hex)
        digest = bytes.fromhex(digest_hex)
    except ValueError:
        return False

    candidate = hashlib.pbkdf2_hmac("sha256", str(password or "").encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, digest)