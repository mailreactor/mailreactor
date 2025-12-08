"""YAML configuration file operations with custom !encrypted tag.

This module handles project-local mailreactor.yaml config files with
encrypted passwords. Follows patterns similar to docker-compose.yaml
and git config (project-local, single file, human-readable structure).
"""

from pathlib import Path
from typing import Any

import yaml

from mailreactor.core.encryption import encrypt
from mailreactor.models.account import AccountConfig


class EncryptedValue:
    """Wrapper for encrypted values parsed from YAML !encrypted tags.

    Splits the combined salt+ciphertext string into separate fields
    for easier handling during decryption.

    Attributes:
        salt: Base64-encoded 32-byte salt (44 characters)
        ciphertext: Fernet token (remaining characters)

    Example:
        >>> value = "dGhpcyBpcyBhIDMyLWJ5dGUgc2FsdCBzdHJpbmc=gAAAAABhqK8s..."
        >>> encrypted = EncryptedValue(value)
        >>> len(encrypted.salt)
        44
        >>> encrypted.salt + encrypted.ciphertext == value
        True
    """

    def __init__(self, value: str):
        """Initialize from combined salt+ciphertext string.

        Args:
            value: <base64-salt><fernet-token> from encrypt()
        """
        # Base64-encoded 32 bytes = 44 characters
        self.salt = value[:44]
        self.ciphertext = value[44:]


def encrypted_constructor(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> EncryptedValue:
    """Parse !encrypted YAML tag into EncryptedValue object.

    This custom constructor is registered with PyYAML's SafeLoader to
    handle the !encrypted tag while maintaining safe_load security.

    Args:
        loader: YAML loader instance
        node: YAML scalar node with !encrypted tag

    Returns:
        EncryptedValue object with separated salt and ciphertext

    Example YAML:
        password: !encrypted dGhpc...gAAAAA...

    Parsed as:
        EncryptedValue(salt="dGhpc...", ciphertext="gAAAAA...")
    """
    value = str(loader.construct_scalar(node))
    return EncryptedValue(value)


# Register custom tag with SafeLoader to maintain security
yaml.add_constructor("!encrypted", encrypted_constructor, Loader=yaml.SafeLoader)  # type: ignore[arg-type]


def load_config(path: Path = Path("mailreactor.yaml")) -> dict[str, Any]:
    """Load mailreactor.yaml with custom !encrypted tag support.

    Reads the YAML file and parses !encrypted values into EncryptedValue
    objects. Does NOT decrypt passwords - that happens later when
    AccountConfig.from_yaml() is called with the master password.

    Args:
        path: Path to config file (default: ./mailreactor.yaml)

    Returns:
        Config dict with EncryptedValue objects for password fields

    Raises:
        FileNotFoundError: Config file doesn't exist

    Example:
        >>> config = load_config(Path("mailreactor.yaml"))  # doctest: +SKIP
        >>> config["email"]  # doctest: +SKIP
        'user@gmail.com'
        >>> isinstance(config["imap"]["password"], EncryptedValue)  # doctest: +SKIP
        True
    """
    if not path.exists():
        raise FileNotFoundError(f"Configuration not found: {path}")

    with path.open("r") as f:
        config: dict[str, Any] = yaml.safe_load(f)

    return config


class EncryptedString(str):
    """String subclass to mark values that should use !encrypted tag in YAML."""

    pass


def encrypted_representer(dumper: yaml.Dumper, data: EncryptedString) -> yaml.Node:
    """Represent EncryptedString as !encrypted YAML tag.

    This custom representer ensures that encrypted passwords are written
    with the !encrypted tag instead of as quoted strings.

    Args:
        dumper: YAML dumper instance
        data: EncryptedString to represent

    Returns:
        YAML scalar node with !encrypted tag
    """
    return dumper.represent_scalar("!encrypted", str(data))


# Register custom representer for writing !encrypted tags
yaml.add_representer(EncryptedString, encrypted_representer)


def save_config(path: Path, config: AccountConfig, master_password: str) -> None:
    """Save AccountConfig to YAML with encrypted passwords.

    Encrypts IMAP and SMTP passwords using the master password and writes
    a project-local mailreactor.yaml file. Each password gets a unique
    random salt. File permissions are set to 0600 (user read/write only).

    Args:
        path: Path to write config file
        config: Account configuration to save
        master_password: Password for encrypting credentials

    Example:
        >>> from mailreactor.models.account import AccountConfig, IMAPConfig, SMTPConfig  # doctest: +SKIP
        >>> config = AccountConfig(  # doctest: +SKIP
        ...     email="test@gmail.com",
        ...     imap=IMAPConfig(host="imap.gmail.com", username="test@gmail.com", password="secret"),
        ...     smtp=SMTPConfig(host="smtp.gmail.com", username="test@gmail.com", password="secret")
        ... )
        >>> save_config(Path("mailreactor.yaml"), config, "master")  # doctest: +SKIP
    """
    # Encrypt passwords with unique salts
    imap_encrypted = EncryptedString(encrypt(config.imap.password, master_password))
    smtp_encrypted = EncryptedString(encrypt(config.smtp.password, master_password))

    # Build YAML structure
    yaml_data = {
        "email": config.email,
        "imap": {
            "host": config.imap.host,
            "port": config.imap.port,
            "ssl": config.imap.ssl,
            "username": config.imap.username,
            "password": imap_encrypted,
        },
        "smtp": {
            "host": config.smtp.host,
            "port": config.smtp.port,
            "starttls": config.smtp.starttls,
            "username": config.smtp.username,
            "password": smtp_encrypted,
        },
    }

    # Write to file
    with path.open("w") as f:
        yaml.dump(yaml_data, f, default_flow_style=False)

    # Set file permissions to 0600 (user read/write only)
    # Prevents casual reading by other users on shared systems
    path.chmod(0o600)
