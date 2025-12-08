"""Performance tests for encryption module.

Verifies that key derivation meets performance requirements (AC-9).
"""

import time

from mailreactor.core.encryption import derive_key, generate_salt


class TestKeyDerivationPerformance:
    """Performance tests for PBKDF2 key derivation."""

    def test_key_derivation_completes_under_100ms(self):
        """Verify PBKDF2 key derivation meets performance requirement (AC-9).

        PBKDF2 with 100,000 iterations should complete in <100ms on modern hardware.
        This is acceptable startup delay for security benefit.
        """
        salt = generate_salt()
        master = "testMasterPassword"

        # Measure key derivation time
        start = time.perf_counter()
        key = derive_key(master, salt)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Verify result is valid key
        assert key is not None
        assert len(key) > 0

        # Verify performance requirement
        assert elapsed_ms < 100, (
            f"Key derivation took {elapsed_ms:.2f}ms (requirement: <100ms). "
            f"PBKDF2 with 100,000 iterations should complete faster."
        )

    def test_key_derivation_consistent_performance(self):
        """Verify key derivation performance is consistent across multiple runs."""
        salt = generate_salt()
        master = "testMasterPassword"

        # Measure multiple runs
        times = []
        for _ in range(10):
            start = time.perf_counter()
            derive_key(master, salt)
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)

        # All runs should be under 100ms
        assert all(t < 100 for t in times), f"Some key derivations exceeded 100ms: {times}"

        # Performance should be relatively consistent (no huge outliers)
        avg_time = sum(times) / len(times)
        max_time = max(times)

        assert max_time < avg_time * 2, (
            f"Performance inconsistent: max={max_time:.2f}ms, avg={avg_time:.2f}ms"
        )
