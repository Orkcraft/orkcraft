"""Data models for orkcraft."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class QuotaStatus:
    provider: str
    group: str
    window: str
    remaining_fraction: Optional[float]
    reset_time: Optional[datetime]
    error: Optional[str] = None
