"""
Temporary debug router for testing Cloud Sync.

POST /test-cloud-sync triggers a manual sync with mock FSRS logs.
Remove or gate behind feature flag before production.
"""

import os
from typing import Any

from fastapi import APIRouter

from ..services.cloud_sync import CloudSyncService

router = APIRouter(tags=["debug"])


def _mock_fsrs_logs() -> list[dict[str, Any]]:
    """Mock FSRS review logs for testing."""
    return [
        {
            "card_id": "mock-card-001",
            "review_log_id": "log-001",
            "rating": 4,
            "state": "review",
            "elapsed_days": 1,
            "scheduled_days": 3,
            "ts": "2025-03-18T10:00:00Z",
        },
        {
            "card_id": "mock-card-002",
            "review_log_id": "log-002",
            "rating": 3,
            "state": "review",
            "elapsed_days": 2,
            "scheduled_days": 5,
            "ts": "2025-03-18T10:05:00Z",
        },
        {
            "card_id": "mock-card-003",
            "review_log_id": "log-003",
            "rating": 5,
            "state": "review",
            "elapsed_days": 0,
            "scheduled_days": 7,
            "ts": "2025-03-18T10:10:00Z",
        },
    ]


@router.post("/test-cloud-sync")
async def test_cloud_sync() -> dict[str, Any]:
    """
    Trigger a manual telemetry sync to the cloud for testing.

    Uses credentials from env: CLOUD_SYNC_EMAIL, CLOUD_SYNC_PASSWORD,
    CLOUD_SYNC_DEVICE_ID, CLOUD_BASE_URL.
    Falls back to test account (user@example.com / stringst) if not set.
    """
    email = os.getenv("CLOUD_SYNC_EMAIL", "user@example.com")
    password = os.getenv("CLOUD_SYNC_PASSWORD", "stringst")
    client_device_id = os.getenv("CLOUD_SYNC_DEVICE_ID", "fat-client-test-device")
    cloud_base_url = os.getenv("CLOUD_BASE_URL", "http://localhost:8080")

    sync_service = CloudSyncService(
        cloud_base_url=cloud_base_url,
        email=email,
        password=password,
        client_device_id=client_device_id,
    )

    mock_logs = _mock_fsrs_logs()
    success = await sync_service.sync_telemetry(mock_logs)

    return {
        "status": "Sync triggered",
        "success": success,
        "logs_count": len(mock_logs),
    }
