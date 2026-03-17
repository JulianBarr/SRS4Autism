"""
Cloud Sync Service for Fat Client → Thin Cloud Control Plane.

Handles authentication and telemetry sync to the CUMA cloud.
Follows Harness Engineering: cohesive, heavily typed, strictly asynchronous.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class CloudSyncService:
    """
    Async service for authenticating and syncing telemetry logs to the cloud.
    """

    def __init__(
        self,
        *,
        cloud_base_url: str = "http://localhost:8080",
        email: str,
        password: str,
        client_device_id: str,
    ) -> None:
        self.cloud_base_url = cloud_base_url.rstrip("/")
        self.email = email
        self.password = password
        self.client_device_id = client_device_id
        self._access_token: str | None = None

    async def _authenticate(self) -> None:
        """
        POST to /auth/login (OAuth2 form-urlencoded), store access_token.
        Raises httpx.HTTPStatusError on auth failure.
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.post(
                f"{self.cloud_base_url}/auth/login",
                data={"username": self.email, "password": self.password},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            body = response.json()
            token = body.get("access_token")
            if not token:
                raise ValueError("Cloud auth response missing access_token")
            self._access_token = token
            logger.info("Cloud auth successful for %s", self.email)

    async def sync_telemetry(self, local_logs: list[dict[str, Any]]) -> bool:
        """
        Sync batched telemetry logs to the cloud.

        Authenticates if needed, then POSTs to /sync/telemetry.
        Returns True on success, False on failure (errors are logged).
        """
        if not self._access_token:
            try:
                await self._authenticate()
            except httpx.HTTPStatusError as e:
                logger.error("Cloud auth failed: %s - %s", e.response.status_code, e.response.text)
                return False
            except Exception as e:
                logger.error("Cloud auth error: %s", e, exc_info=True)
                return False

        payload = {
            "client_device_id": self.client_device_id,
            "payload": local_logs,
        }

        async with httpx.AsyncClient(trust_env=False) as client:
            try:
                response = await client.post(
                    f"{self.cloud_base_url}/sync/telemetry",
                    json=payload,
                    headers={"Authorization": f"Bearer {self._access_token}"},
                )
                response.raise_for_status()
                logger.info("Telemetry sync succeeded: %d logs", len(local_logs))
                return True
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Telemetry sync failed: %s - %s",
                    e.response.status_code,
                    e.response.text,
                )
                return False
            except Exception as e:
                logger.error("Telemetry sync error: %s", e, exc_info=True)
                return False
