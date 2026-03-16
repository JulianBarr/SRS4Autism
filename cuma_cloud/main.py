"""Cuma Cloud Control Plane - FastAPI application entry point."""

from fastapi import FastAPI

from cuma_cloud.api.routers import auth

app = FastAPI(
    title="Cuma Cloud Control Plane",
    description="Lightweight 4A architecture for Cuma Local-First App",
)

app.include_router(auth.router, prefix="/auth")
