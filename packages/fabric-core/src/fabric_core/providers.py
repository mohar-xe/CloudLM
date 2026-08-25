"""Provider protocol — the only seam between cloud reality and the engine (D-001)."""

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, Field

from fabric_core.models import BillingSummaryItem, Domain, MetricPoint, ResourceSnapshot


class ProviderCapabilityError(NotImplementedError):
    """Raised when a provider cannot serve a capability in this release."""


class Freshness(BaseModel):
    collected_at: datetime
    degraded_domains: list[Domain] = Field(default_factory=list)

    @property
    def degraded(self) -> bool:
        return bool(self.degraded_domains)


class FabricProvider(ABC):
    """Read-only view over one cloud account or dataset.

    Implementations must be deterministic for identical construction inputs
    so pagination walks are stable within a process.
    """

    name: str

    @abstractmethod
    def page(
        self,
        domain: Domain | None,
        offset: int,
        limit: int,
    ) -> tuple[list[ResourceSnapshot], int]:
        """Return (items, total_estimate) for one bounded page."""

    @abstractmethod
    def metrics(self, resource_arn: str, days: int = 14) -> list[MetricPoint]:
        """Daily metric series for one resource."""

    @abstractmethod
    def billing(self, days: int = 30) -> list[BillingSummaryItem]:
        """Monthly cost rollup grouped by domain + service."""

    @abstractmethod
    def freshness(self) -> Freshness:
        """Collection timestamp plus degraded-domain flags (flow Step 2.5)."""
