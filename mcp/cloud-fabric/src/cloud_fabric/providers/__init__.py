"""Provider factory — the single place a provider implementation is chosen."""

from cloud_fabric.config import FabricSettings
from fabric_core.models import Domain
from fabric_core.providers import FabricProvider

_VALID_DOMAINS = {d.value for d in Domain}


def get_provider(settings: FabricSettings) -> FabricProvider:
    if settings.provider == "synthetic":
        from cloud_fabric.providers.synthetic import SyntheticProvider

        return SyntheticProvider(
            seed=settings.seed,
            degraded_domains=tuple(Domain(d) for d in settings.degraded_domain_list),
        )
    if settings.provider == "aws":
        from cloud_fabric.providers.aws import AwsProvider

        return AwsProvider(region=settings.aws_region)
    raise ValueError(f"unknown FABRIC_PROVIDER {settings.provider!r}; expected synthetic|aws")


def normalize_domain(domain: str | None) -> Domain | None:
    if domain is None or domain == "":
        return None
    if domain not in _VALID_DOMAINS:
        raise ValueError(f"domain must be one of {sorted(_VALID_DOMAINS)} or omitted")
    return Domain(domain)
