"""Abstract digester contract for Stage 2a."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import CoverageKitConfig
from ..model import SurfaceSnapshot


class CoverageDigester(ABC):
    """Parse one collector family’s on-disk artifacts into zero or more surfaces."""

    @abstractmethod
    def digest(self, config: CoverageKitConfig) -> list[SurfaceSnapshot]:
        """Return snapshots (empty when artifacts are missing)."""
