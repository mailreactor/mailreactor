"""Password encryption using Fernet + PBKDF2 key derivation.

Security Properties:
- Fernet: Authenticated encryption (AES-128-CBC + HMAC-SHA256)
- PBKDF2: 100,000 iterations to slow brute-force attacks
- Salt: Unique 32-byte salt per password prevents rainbow tables
- Master password: Never written to disk (env var or prompt only)
"""

import base64
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def generate_salt() -> bytes:
    """Generate 32-byte random salt for PBKDF2.

    Returns:
        32 bytes of cryptographically secure random data
    """
    return os.urandom(32)


def derive_key(master_password: str, salt: bytes) -> bytes:
    """Derive Fernet key from master password using PBKDF2-HMAC-SHA256.

    Uses 100,000 iterations (OWASP 2023 minimum recommendation) to make
    brute-force attacks computationally expensive.

    Args:
        master_password: User's master password
        salt: 32-byte random salt

    Returns:
        32-byte key suitable for Fernet (base64-encoded)
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,  # OWASP 2023 minimum
    )
    key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
    return key


def encrypt(plaintext: str, master_password: str) -> str:
    """Encrypt plaintext password with master password.

    Format: <base64-salt><fernet-token>
    - First 44 characters: Base64-encoded 32-byte salt
    - Remaining characters: Fernet-encrypted ciphertext

    Args:
        plaintext: Password to encrypt
        master_password: User's master password

    Returns:
        Single string combining salt and ciphertext for YAML storage

    Example:
        >>> encrypted = encrypt("myPassword", "masterSecret")
        >>> len(encrypted[:44])  # Salt is always 44 chars
        44
        >>> encrypted[:10] != encrypted[44:54]  # Salt differs from ciphertext
        True
    """
    salt = generate_salt()
    key = derive_key(master_password, salt)
    fernet = Fernet(key)

    ciphertext_bytes = fernet.encrypt(plaintext.encode())

    # Combine salt + ciphertext for storage
    salt_b64: str = base64.b64encode(salt).decode("utf-8")
    ciphertext_str: str = ciphertext_bytes.decode("utf-8")

    return salt_b64 + ciphertext_str


def decrypt(encrypted: str, master_password: str) -> str:
    """Decrypt encrypted value with master password.

    Args:
        encrypted: <base64-salt><fernet-token> string from encrypt()
        master_password: User's master password

    Returns:
        Decrypted plaintext password

    Raises:
        cryptography.fernet.InvalidToken: Wrong master password or corrupted data

    Example:
        >>> plaintext = "myPassword"
        >>> encrypted = encrypt(plaintext, "masterSecret")
        >>> decrypt(encrypted, "masterSecret") == plaintext
        True
        >>> decrypt(encrypted, "wrongPassword")  # doctest: +SKIP
        Traceback (most recent call last):
        ...
        cryptography.fernet.InvalidToken
    """
    # Split salt and ciphertext
    salt_b64 = encrypted[:44]  # Base64-encoded 32 bytes = 44 chars
    ciphertext_str = encrypted[44:]

    salt = base64.b64decode(salt_b64)
    key = derive_key(master_password, salt)
    fernet = Fernet(key)

    plaintext_bytes = fernet.decrypt(ciphertext_str.encode("utf-8"))
    plaintext: str = plaintext_bytes.decode("utf-8")
    return plaintext
