"""Cuma Cloud Control Plane - FastAPI application entry point."""

from fastapi import FastAPI

from cuma_cloud.api.routers import auth
from cuma_cloud.api.routers import children as children_router
from cuma_cloud.api.routers import policies as policies_router
from cuma_cloud.api.routers import sync as sync_router

app = FastAPI(
    title="Cuma Cloud Control Plane",
    description="Lightweight 4A architecture for Cuma Local-First App",
)

app.include_router(auth.router, prefix="/auth")
app.include_router(policies_router.router, prefix="/policies")
app.include_router(sync_router.router, prefix="/sync", tags=["Auditing & Telemetry"])
app.include_router(children_router.router, prefix="/api/v1")
