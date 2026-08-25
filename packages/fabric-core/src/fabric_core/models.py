"""Canonical normalized schemas — the single boundary between clouds and engine (D-007)."""

from datetime import UTC, date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Domain(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    K8S = "k8s"
    NETWORK = "network"


class Status(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"


class ResourceSnapshot(BaseModel):
    resource_arn: str
    resource_type: str
    domain: Domain
    region: str
    instance_family: str | None = None
    hourly_cost: float = Field(ge=0)
    avg_cpu: float | None = Field(default=None, ge=0, le=100)
    avg_memory: float | None = Field(default=None, ge=0, le=100)
    p99_latency_ms: float | None = Field(default=None, ge=0)
    created_at: datetime
    collected_at: datetime
    status: Status = Status.OK
    parent_arn: str | None = None
    parent_state: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class MetricPoint(BaseModel):
    date: date
    avg_cpu: float = Field(ge=0, le=100)
    avg_memory: float = Field(ge=0, le=100)
    p99_latency_ms: float = Field(ge=0)
    requests_per_sec: float = Field(ge=0)


class BillingSummaryItem(BaseModel):
    domain: Domain
    service: str
    monthly_cost_usd: float = Field(ge=0)
    delta_vs_prev_pct: float


def utcnow() -> datetime:
    return datetime.now(UTC)
