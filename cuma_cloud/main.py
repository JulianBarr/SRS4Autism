"""Cuma Cloud Control Plane - FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # 🌟 1. 导入 CORS 中间件

from cuma_cloud.api.routers import auth
from cuma_cloud.api.routers import admin as admin_router
from cuma_cloud.api.routers import institutions as institutions_router
from cuma_cloud.api.routers import users as users_router
from cuma_cloud.api.routers import children as children_router
from cuma_cloud.api.routers import iep_logs as iep_logs_router
from cuma_cloud.api.routers import policies as policies_router
from cuma_cloud.api.routers import sync as sync_router

app = FastAPI(
    title="Cuma Cloud Control Plane",
    description="Lightweight 4A architecture for Cuma Local-First App",
)

# 🌟 2. 注册 CORS 中间件 (必须在 include_router 之前！)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许您的 localhost:3000 访问
    allow_credentials=True,
    allow_methods=["*"],  # 🌟 放行 OPTIONS 请求，解决 405 报错
    allow_headers=["*"],  # 🌟 放行咱们自定义的 x-mock-user-id 鉴权头
)

app.include_router(auth.router, prefix="/auth")
app.include_router(policies_router.router, prefix="/policies")
app.include_router(sync_router.router, prefix="/sync", tags=["Auditing & Telemetry"])
app.include_router(children_router.router, prefix="/api/v1")
app.include_router(iep_logs_router.router, prefix="/api/v1")
app.include_router(admin_router.router, prefix="/api/v1")
app.include_router(institutions_router.router, prefix="/api/v1")
app.include_router(users_router.router, prefix="/api/v1")
