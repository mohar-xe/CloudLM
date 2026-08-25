"""Shared test constants."""

from datetime import UTC, datetime

FROZEN_NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=UTC)

SMALL_COUNTS = {
    "compute": 57,
    "volumes": 23,
    "snapshots": 41,
    "pods": 33,
    "network": 12,
}
