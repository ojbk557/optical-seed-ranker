from .base import PatentDocument, PatentProvider, PatentQuery, PatentRecord
from .epo_ops import EpoOpsError, EpoOpsProvider

__all__ = [
    "EpoOpsError",
    "EpoOpsProvider",
    "PatentDocument",
    "PatentProvider",
    "PatentQuery",
    "PatentRecord",
]
