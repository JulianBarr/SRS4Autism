"""Telemetry sync routes. Clients batch logs and push when online; cloud ingests as raw JSONB."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from cuma_cloud.api.dependencies import get_current_user
from cuma_cloud.api.schemas import TelemetrySyncRequest, TelemetrySyncResponse
from cuma_cloud.core.database import get_db
from cuma_cloud.models import CloudAccount, TelemetrySyncLog

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/telemetry", response_model=TelemetrySyncResponse, status_code=status.HTTP_201_CREATED)
async def sync_telemetry(
    sync_data: TelemetrySyncRequest,
    current_user: CloudAccount = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TelemetrySyncLog:
    """
    Receive batched telemetry from a Local-First client.

    The cloud acts as a high-throughput receiver. No validation of payload items;
    data is stored as raw JSONB for future stream processing or federated learning.
    """
    try:
        log = TelemetrySyncLog(
            account_id=current_user.id,
            client_device_id=sync_data.client_device_id,
            event_type="telemetry_batch",
            payload=sync_data.payload,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return log
    except Exception as e:
        logger.error("Telemetry sync failed: %s", e, exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist telemetry",
        ) from e
