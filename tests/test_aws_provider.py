from cloud_fabric.providers.aws import AwsProvider, _service_domain
from fabric_core.models import Domain


def test_service_domain_known_storage() -> None:
    assert _service_domain("Amazon Elastic Block Store") == Domain.STORAGE
    assert _service_domain("Amazon Simple Storage Service (S3)") == Domain.STORAGE
    assert _service_domain("Amazon FSx") == Domain.STORAGE


def test_service_domain_known_network() -> None:
    assert _service_domain("Amazon Virtual Private Cloud") == Domain.NETWORK
    assert _service_domain("AWS Elastic Load Balancing") == Domain.NETWORK
    assert _service_domain("Amazon CloudFront") == Domain.NETWORK
    assert _service_domain("AWS Data Transfer") == Domain.NETWORK


def test_service_domain_known_k8s() -> None:
    assert _service_domain("Amazon Elastic Kubernetes Service") == Domain.K8S


def test_service_domain_fallback_compute() -> None:
    assert _service_domain("Amazon Elastic Compute Cloud - Compute (EC2)") == Domain.COMPUTE
    assert _service_domain("AWSCostExplorer") == Domain.COMPUTE


def test_billing_aggregates_across_periods() -> None:
    resp = {
        "ResultsByTime": [
            {
                "Groups": [
                    {"Keys": ["EC2"], "Metrics": {"UnblendedCost": {"Amount": "10.5"}}},
                    {"Keys": ["S3"], "Metrics": {"UnblendedCost": {"Amount": "2.0"}}},
                ]
            },
            {
                "Groups": [
                    {"Keys": ["EC2"], "Metrics": {"UnblendedCost": {"Amount": "4.5"}}},
                ]
            },
        ]
    }
    totals = AwsProvider._aggregate_billing(resp)
    assert totals == {"EC2": 15.0, "S3": 2.0}


def test_billing_aggregation_empty_periods() -> None:
    assert AwsProvider._aggregate_billing({"ResultsByTime": [{"Groups": []}]}) == {}
