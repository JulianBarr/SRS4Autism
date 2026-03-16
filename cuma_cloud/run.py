"""Explicit entry point for the Cuma Cloud Control Plane server.

Uses CLOUD_PORT from config to avoid collision with the Local-First
FastAPI app (port 8000). Run with: python -m cuma_cloud.run
"""

if __name__ == "__main__":
    import uvicorn

    from cuma_cloud.core.config import settings

    uvicorn.run(
        "cuma_cloud.main:app",
        host="0.0.0.0",
        port=settings.cloud_port,
        reload=True,
    )
