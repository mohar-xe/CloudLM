"""Deterministic seeded fabric generator (D-001 default provider).

Coherence requirements baked in on purpose so later layers have learnable
structure: idle compute is rare and visibly idle, p99 latency rises sharply
with CPU saturation, some EBS snapshots outlive terminated parents (zombies),
and a slice of K8s pods over-request by 5x+. Data volume ~12k resources.
"""

import hashlib
import math
from collections import defaultdict
from datetime import datetime, timedelta
from random import Random

from fabric_core.models import (
    BillingSummaryItem,
    Domain,
    MetricPoint,
    ResourceSnapshot,
    Status,
    utcnow,
)
from fabric_core.providers import FabricProvider, Freshness

REGIONS = ("us-east-1", "us-west-2", "eu-west-1", "ap-south-1")

FAMILY_SIZES: dict[str, tuple[str, ...]] = {
    "m5": ("large", "xlarge", "2xlarge"),
    "c5": ("large", "xlarge", "2xlarge"),
    "r5": ("large", "xlarge"),
    "t3": ("medium", "large"),
}

HOURLY_COST: dict[tuple[str, str], float] = {
    ("m5", "large"): 0.096,
    ("m5", "xlarge"): 0.192,
    ("m5", "2xlarge"): 0.384,
    ("c5", "large"): 0.085,
    ("c5", "xlarge"): 0.17,
    ("c5", "2xlarge"): 0.34,
    ("r5", "large"): 0.126,
    ("r5", "xlarge"): 0.252,
    ("t3", "medium"): 0.0416,
    ("t3", "large"): 0.0832,
}


def _instance_arn(region: str, i: int) -> str:
    return f"arn:aws:ec2:{region}:111122223333:instance/i-{seed_hex(i, 'i')}"


def _latency_for(cpu_pct: float, family: str) -> float:
    saturation = (cpu_pct / 100.0) ** 1.8
    family_floor = {"t3": 55.0, "m5": 40.0, "c5": 32.0, "r5": 44.0}.get(family, 40.0)
    return round(family_floor + 880.0 * saturation, 1)


class SyntheticProvider(FabricProvider):
    name = "synthetic"

    def __init__(
        self,
        seed: int = 42,
        counts: dict[str, int] | None = None,
        now: datetime | None = None,
        degraded_domains: tuple[Domain, ...] = (),
    ) -> None:
        self._rng = Random(seed)
        self._now = now or utcnow()
        self._degraded_domains = list(degraded_domains)
        n_compute = (counts or {}).get("compute", 4200)
        n_volumes = (counts or {}).get("volumes", 3200)
        n_snapshots = (counts or {}).get("snapshots", 2600)
        n_pods = (counts or {}).get("pods", 1600)
        n_network = (counts or {}).get("network", 380)
        self._resources: list[ResourceSnapshot] = []
        self._resources += self._gen_compute(n_compute)
        self._resources += self._gen_volumes(n_volumes)
        self._resources += self._gen_snapshots(n_snapshots)
        self._resources += self._gen_pods(n_pods)
        self._resources += self._gen_network(n_network)
        self._by_arn = {r.resource_arn: r for r in self._resources}
        self._index: dict[Domain | None, list[ResourceSnapshot]] = defaultdict(list)
        for r in self._resources:
            self._index[r.domain].append(r)

    def _region(self) -> str:
        return self._rng.choices(REGIONS, weights=(45, 20, 22, 13))[0]

    def _tags(self) -> dict[str, str]:
        team = f"team-{self._rng.randint(1, 9)}"
        env = self._rng.choices(("prod", "staging", "dev"), weights=(50, 25, 25))[0]
        return {"team": team, "env": env}

    def _created(self) -> datetime:
        days = self._rng.randint(10, 700)
        return self._now - timedelta(days=days)

    def _gen_compute(self, n: int) -> list[ResourceSnapshot]:
        out = []
        for i in range(n):
            family = self._rng.choice(list(FAMILY_SIZES))
            size = self._rng.choice(FAMILY_SIZES[family])
            region = self._region()
            arn = _instance_arn(region, i)
            idle = self._rng.random() < 0.12
            cpu = (
                self._rng.uniform(0.8, 4.9)
                if idle
                else min(96.0, self._rng.lognormvariate(math.log(38), 0.45))
            )
            mem = max(3.0, min(95.0, cpu * self._rng.uniform(0.7, 1.3)))
            out.append(
                ResourceSnapshot(
                    resource_arn=arn,
                    resource_type="ec2_instance",
                    domain=Domain.COMPUTE,
                    region=region,
                    instance_family=f"{family}.{size}",
                    hourly_cost=HOURLY_COST[(family, size)],
                    avg_cpu=round(cpu, 2),
                    avg_memory=round(mem, 2),
                    p99_latency_ms=_latency_for(cpu, family),
                    created_at=self._created(),
                    collected_at=self._collected(),
                    status=Status.DEGRADED
                    if Domain.COMPUTE in self._degraded_domains
                    else Status.OK,
                    tags=self._tags(),
                )
            )
        return out

    def _gen_volumes(self, n: int) -> list[ResourceSnapshot]:
        out = []
        for i in range(n):
            region = self._region()
            gb = self._rng.choice((8, 20, 50, 100, 200, 500, 1000))
            attached = self._rng.random() < 0.86
            out.append(
                ResourceSnapshot(
                    resource_arn=f"arn:aws:ec2:{region}:111122223333:volume/vol-{seed_hex(i, 'v')}",
                    resource_type="ebs_volume",
                    domain=Domain.STORAGE,
                    region=region,
                    hourly_cost=round(gb * 0.00011, 5),
                    created_at=self._created(),
                    collected_at=self._collected(),
                    status=Status.OK,
                    parent_arn=None
                    if not attached
                    else _instance_arn(region, self._rng.randrange(4200)),
                    parent_state="running" if attached else "detached",
                    tags=self._tags(),
                )
            )
        return out

    def _gen_snapshots(self, n: int) -> list[ResourceSnapshot]:
        out = []
        for i in range(n):
            region = self._region()
            parent_state = self._rng.choices(("in-use", "terminated"), weights=(72, 28))[0]
            age_days = self._rng.randint(1, 420)
            out.append(
                ResourceSnapshot(
                    resource_arn=f"arn:aws:ec2:{region}:111122223333:snapshot/snap-{seed_hex(i, 's')}",  # noqa: E501
                    resource_type="ebs_snapshot",
                    domain=Domain.STORAGE,
                    region=region,
                    hourly_cost=round(self._rng.uniform(0.005, 0.05), 5),
                    created_at=self._now - timedelta(days=age_days),
                    collected_at=self._collected(),
                    status=Status.OK,
                    parent_arn=_instance_arn(region, self._rng.randrange(4200)),
                    parent_state=parent_state,
                    tags={"age_days": str(age_days), **self._tags()},
                )
            )
        return out

    def _gen_pods(self, n: int) -> list[ResourceSnapshot]:
        out = []
        for i in range(n):
            region = self._region()
            ratio = self._rng.choices((1.2, 3.0, 6.0), weights=(68, 22, 10))[0]
            usage_cpu = self._rng.uniform(4, 70)
            requested_cpu = usage_cpu * ratio * self._rng.uniform(0.9, 1.1)
            out.append(
                ResourceSnapshot(
                    resource_arn=f"arn:aws:eks:{region}:111122223333:pod/pod-{seed_hex(i, 'p')}",
                    resource_type="k8s_pod",
                    domain=Domain.K8S,
                    region=region,
                    instance_family=None,
                    hourly_cost=round(requested_cpu * 0.0009 + self._rng.uniform(0.001, 0.01), 5),
                    avg_cpu=round(min(requested_cpu / max(ratio, 1.0), 100.0), 2),
                    avg_memory=round(self._rng.uniform(10, 80), 2),
                    created_at=self._created(),
                    collected_at=self._collected(),
                    status=Status.DEGRADED if Domain.K8S in self._degraded_domains else Status.OK,
                    tags={
                        "request_mcpu": str(int(requested_cpu * 10)),
                        "usage_mcpu": str(int(usage_cpu * 10)),
                        **self._tags(),
                    },
                )
            )
        return out

    def _gen_network(self, n: int) -> list[ResourceSnapshot]:
        out = []
        for i in range(n):
            is_nat = i % 2 == 0
            region = self._region()
            rtype = "nat_gateway" if is_nat else "alb"
            cpu = self._rng.uniform(2, 85)
            out.append(
                ResourceSnapshot(
                    resource_arn=f"arn:aws:ec2:{region}:111122223333:{rtype}/{seed_hex(i, 'n')}",
                    resource_type=rtype,
                    domain=Domain.NETWORK,
                    region=region,
                    hourly_cost=self._rng.uniform(0.032, 0.065)
                    if is_nat
                    else self._rng.uniform(0.0225, 0.045),
                    avg_cpu=round(cpu, 2),
                    p99_latency_ms=_latency_for(cpu, "c5"),
                    created_at=self._created(),
                    collected_at=self._collected(),
                    status=Status.OK,
                    tags=self._tags(),
                )
            )
        return out

    def _collected(self) -> datetime:
        return self._now

    def page(
        self,
        domain: Domain | None,
        offset: int,
        limit: int,
    ) -> tuple[list[ResourceSnapshot], int]:
        pool = self._resources if domain is None else self._index[domain]
        items = pool[offset : offset + limit]
        return items, len(pool)

    def metrics(self, resource_arn: str, days: int = 14) -> list[MetricPoint]:
        res = self._by_arn.get(resource_arn)
        if res is None or res.avg_cpu is None:
            return []
        stream_seed = int(hashlib.sha256(resource_arn.encode()).hexdigest()[:12], 16)
        rng = Random(stream_seed)
        points = []
        for d in range(days, 0, -1):
            wave = math.sin((d / days) * math.pi * 2 + rng.uniform(0, 1))
            cpu = max(0.5, min(99.0, res.avg_cpu + wave * res.avg_cpu * 0.25 + rng.gauss(0, 2)))
            req = max(
                0.0, (res.avg_memory or 30) * 12 * (cpu / max(res.avg_cpu, 1)) + rng.gauss(0, 8)
            )
            points.append(
                MetricPoint(
                    date=(self._now - timedelta(days=d - 1)).date(),
                    avg_cpu=round(cpu, 2),
                    avg_memory=round(max(1.0, (res.avg_memory or 30) + rng.gauss(0, 3)), 2),
                    p99_latency_ms=_latency_for(
                        cpu, (res.instance_family or "m5.c5").split(".")[0]
                    ),
                    requests_per_sec=round(req, 1),
                )
            )
        return points

    def billing(self, days: int = 30) -> list[BillingSummaryItem]:
        totals: dict[tuple[Domain, str], float] = defaultdict(float)
        for r in self._resources:
            totals[(r.domain, r.resource_type)] += r.hourly_cost * 24 * (days if days <= 31 else 30)
        items = [
            BillingSummaryItem(
                domain=domain,
                service=service,
                monthly_cost_usd=round(cost, 2),
                delta_vs_prev_pct=round(
                    ((int(hashlib.sha256(service.encode()).hexdigest(), 16) % 41) - 20), 1
                ),
            )
            for (domain, service), cost in sorted(totals.items())
        ]
        return items

    def freshness(self) -> Freshness:
        return Freshness(collected_at=self._now, degraded_domains=list(self._degraded_domains))


def seed_hex(i: int, prefix: str) -> str:
    digest = hashlib.sha256(f"{prefix}{i}".encode()).hexdigest()
    return digest[:17]
