"""Read-only AWS adapter (D-001 opt-in). Partial by design in Layer 1.

Covers EC2 instances, EBS volumes/snapshots and Cost Explorer billing.
CloudWatch per-resource rollups are not wired yet and raise
ProviderCapabilityError with an explicit message.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fabric_core.models import BillingSummaryItem, Domain, MetricPoint, ResourceSnapshot, Status
from fabric_core.providers import FabricProvider, Freshness, ProviderCapabilityError

logger = logging.getLogger(__name__)

_EC2 = "arn:aws:ec2:{region}:{account}:{kind}/{id_}"


def _boto() -> Any:
    try:
        import boto3
    except ImportError as exc:
        raise ProviderCapabilityError(
            "FABRIC_PROVIDER=aws requires the aws extra: uv sync --extra aws"
        ) from exc
    return boto3


class AwsProvider(FabricProvider):
    name = "aws"

    def __init__(self, region: str = "us-east-1") -> None:
        self._region = region
        boto3 = _boto()
        self._ec2 = boto3.client("ec2", region_name=region)
        try:
            self._ce = boto3.client("ce", region_name=region)
        except Exception:
            self._ce = None
        self._cache: list[ResourceSnapshot] | None = None

    def _collect(self) -> list[ResourceSnapshot]:
        if self._cache is not None:
            return self._cache
        collected = datetime.now(UTC)
        out: list[ResourceSnapshot] = []
        paginator = self._ec2.get_paginator("describe_instances")
        for page in paginator.paginate():
            for reservation in page["Reservations"]:
                for inst in reservation["Instances"]:
                    cpu = self._tag_avg(inst, "cpu")
                    out.append(
                        ResourceSnapshot(
                            resource_arn=_EC2.format(
                                region=inst["Placement"]["AvailabilityZone"][:-1],
                                account=inst["OwnerId"],
                                kind="instance",
                                id_=inst["InstanceId"],
                            ),
                            resource_type="ec2_instance",
                            domain=Domain.COMPUTE,
                            region=inst["Placement"]["AvailabilityZone"][:-1],
                            instance_family=inst.get("InstanceType"),
                            hourly_cost=0.0,
                            avg_cpu=cpu,
                            created_at=inst.get("LaunchTime", collected),
                            collected_at=collected,
                            status=Status.OK,
                            parent_state=inst["State"]["Name"],
                            tags={t["Key"]: t["Value"] for t in inst.get("Tags", [])},
                        )
                    )
        vols = self._ec2.describe_volumes()
        for vol in vols["Volumes"]:
            out.append(
                ResourceSnapshot(
                    resource_arn=_EC2.format(
                        region=self._region, account="0", kind="volume", id_=vol["VolumeId"]
                    ),
                    resource_type="ebs_volume",
                    domain=Domain.STORAGE,
                    region=self._region,
                    hourly_cost=round(vol["Size"] * 0.00011, 5),
                    created_at=vol["CreateTime"],
                    collected_at=collected,
                    status=Status.OK,
                    parent_state=vol["State"],
                )
            )
        snaps = self._ec2.describe_snapshots(OwnerIds=["self"])
        for snap in snaps["Snapshots"]:
            out.append(
                ResourceSnapshot(
                    resource_arn=_EC2.format(
                        region=self._region, account="0", kind="snapshot", id_=snap["SnapshotId"]
                    ),
                    resource_type="ebs_snapshot",
                    domain=Domain.STORAGE,
                    region=self._region,
                    hourly_cost=round(snap["VolumeSize"] * 0.00005, 5),
                    created_at=snap["StartTime"],
                    collected_at=collected,
                    status=Status.OK,
                    parent_state="unknown",
                )
            )
        self._cache = out
        return out

    @staticmethod
    def _tag_avg(inst: dict[str, Any], metric: str) -> float | None:
        return None

    def page(
        self,
        domain: Domain | None,
        offset: int,
        limit: int,
    ) -> tuple[list[ResourceSnapshot], int]:
        pool = [r for r in self._collect() if domain is None or r.domain == domain]
        return pool[offset : offset + limit], len(pool)

    def metrics(self, resource_arn: str, days: int = 14) -> list[MetricPoint]:
        raise ProviderCapabilityError(
            "per-resource CloudWatch rollups are not implemented for the aws provider yet; "
            "use FABRIC_PROVIDER=synthetic"
        )

    def billing(self, days: int = 30) -> list[BillingSummaryItem]:
        if self._ce is None:
            raise ProviderCapabilityError("Cost Explorer client unavailable")
        end = datetime.now(UTC).date()
        start = end - timedelta(days=days)
        resp = self._ce.get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
        items: list[BillingSummaryItem] = []
        for group in resp["Groups"]:
            amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
            items.append(
                BillingSummaryItem(
                    domain=Domain.COMPUTE,
                    service=group["Keys"][0],
                    monthly_cost_usd=round(amount, 2),
                    delta_vs_prev_pct=0.0,
                )
            )
        return items

    def freshness(self) -> Freshness:
        return Freshness(collected_at=datetime.now(UTC))
