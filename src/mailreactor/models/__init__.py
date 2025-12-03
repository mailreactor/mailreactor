"""Pydantic models for request/response validation.

This package contains all Pydantic models used throughout the application:
- responses: API response models (HealthResponse, etc.)
- Future: account, message models for Epic 2+
"""

from mailreactor.models.responses import HealthResponse

__all__ = ["HealthResponse"]
