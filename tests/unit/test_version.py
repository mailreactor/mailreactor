"""Unit tests for version utility.

Tests cover:
- Version retrieval from package metadata
- Fallback behavior when package not installed
"""

from unittest.mock import patch

from mailreactor.utils.version import get_app_version


class TestGetAppVersion:
    """Test version utility."""

    def test_get_app_version_returns_string(self):
        """Test get_app_version returns a string."""
        version = get_app_version()
        assert isinstance(version, str)
        assert len(version) > 0

    def test_get_app_version_has_valid_format(self):
        """Test version follows semantic versioning pattern."""
        version = get_app_version()
        # Should be in format X.Y.Z or X.Y.Z-suffix
        assert version[0].isdigit()
        assert "." in version

    def test_get_app_version_fallback_on_package_not_found(self):
        """Test fallback to dev version when package not installed."""
        with patch(
            "mailreactor.utils.version.get_version",
            side_effect=Exception("Package not found"),
        ):
            version = get_app_version()
            assert version == "0.1.0-dev"
