"""Canonical SRD data access layer (the 'engine disposes' source of truth)."""

from .srd_repository import SRDRepository, SUPPORTED_EDITIONS

__all__ = ["SRDRepository", "SUPPORTED_EDITIONS"]
