# CUMA (Curious Mario) 端云一体化架构指北
> **版本:** 1.0 (基建落地版)
> **状态:** Production Ready (端云闭环已打通)

## 1. 核心设计哲学：Local-First (胖客户端 + 瘦云端)
CUMA 采用极致的 Local-First 架构，旨在提供“断网可用、极致丝滑”的心流体验，同时利用公网云端实现数据备份与多端同步。

* **Fat Client (本地胖客户端):** 承担 99% 的计算负荷。包含完整的图形界面、FSRS 核心调度算法、SQLite 状态存储以及 Oxigraph 本地知识图谱库。确保在无网络环境下的绝对健壮性。
* **Thin Cloud (公网瘦控制面):** 仅作为数据汇聚中心（Telemetry / Logs / 账号同步）。不承担任何抽卡算法的实时计算，最大程度降低由于网络延迟（跨洋访问）带来的 UX 卡顿。

## 2. 拓扑与流量全景图

```text
[ 本地环境 (Mac) ]                               [ 公网环境 (BWH VPS - Rocky Linux) ]
                                      |
┌────────────────────────┐            |            ┌────────────────────────────────────────┐
│                        │            |            │  1. 操作系统守护与安全层               │
│  [ React / Electron ]  │            |            │     - 彻底禁用 Root 密码登录           │
│           │            │            |            │     - 纯 SSH Key 认证 (deploy 账户)    │
│           ▼            │            |            │                                        │
│  [ FastAPI 后端 ]      │━━(HTTP)━━▶ │ ━━(CDN)━━▶ │  2. 流量网关层 (Caddy)                 │
│    (Port: 8000)        │ cloud_sync | Cloudflare │     - 监听 80 / 443 端口               │
│           │            │   /tele    | (Flexible) │     - api.autrenative.com ─▶ Xray(VPN) │
│           ▼            │            |            │     - cuma.autrenative.com ─▶ Docker   │
│ ┌────────┴──────────┐  │            |            │           │                            │
│ │ SQLite (复习状态) │  │            |            │           ▼                            │
│ │ Oxigraph (图谱库) │  │            |            │  3. 容器编排层 (Docker Compose)        │
│ └───────────────────┘  │            |            │     ┌────────────────────────────────┐ │
└────────────────────────┘            |            │     │ [ cuma-api ] (FastAPI)         │ │
                                      |            │     │   - 内部映射 127.0.0.1:8080    │ │
                                      |            │     │   - 负责 JWT 鉴权与日志接收    │ │
                                      |            │     │           │                    │ │
                                      |            │     │           ▼                    │ │
                                      |            │     │ [ cuma-db ] (PostgreSQL 15)    │ │
                                      |            │     │   - 持久化 Volume 挂载         │ │
                                      |            │     └────────────────────────────────┘ │
                                      |            └────────────────────────────────────────┘
```

## 3. 云端基建配置手册 (Cheat Sheet)

### 3.1 账号与权限护栏
为防止被扫描器爆破，服务器摒弃了 Root 密码直连，采用非特权账户隔离运行：
* **业务执行账户:** `deploy` (隶属 `wheel` 与 `docker` 用户组)。
* **免密配置:** * 密钥存放于 `~/.ssh/authorized_keys`。
  * 必须保证极严苛的权限 (`chmod 700 ~/.ssh`, `chmod 600 ~/.ssh/authorized_keys`)。
* **防护锁定:** `/etc/ssh/sshd_config` 中已强行开启 `PasswordAuthentication no`。

### 3.2 Caddy 反向代理网关
Caddy 完美接管了宿主机的核心 Web 端口，实现了科学上网流量与 CUMA 业务流量的优雅共存。
**配置文件位置:** `/etc/caddy/Caddyfile`
**核心路由规则:**
```caddyfile
# 旁路：现有 VPN 伪装流量保持不变
api.autrenative.com {
    reverse_proxy /ray localhost:8443 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
    }
}

# 主路：CUMA 云端控制面
# 采用 http:// 声明，完美兼容 Cloudflare Flexible 模式
http://cuma.autrenative.com {
    reverse_proxy localhost:8080
}
```
*平滑重载命令:* `sudo systemctl reload caddy`

### 3.3 Docker 容器化部署
业务代码被包裹在高度一致的隔离环境中。
* **部署目录:** `/home/deploy/SRS4Autism/cuma_cloud/`
* **网络隔离:** FastAPI 仅在宿主机环回地址 (`127.0.0.1:8080`) 暴露，杜绝公网直连绕过 Caddy。
* **常用运维指令:**
  * 点火构建: `docker compose up --build -d`
  * 查看日志: `docker compose logs --tail 100 -f api`
  * 强制刷表 (越过 Alembic): 
    ```bash
    docker compose exec -w /app/cuma_cloud api python -c "
    import asyncio
    from core.database import engine, Base
    import models

    async def init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            print('✅ Database tables created successfully!')

    asyncio.run(init_db())
    "
    ```

## 4. 端云同步链路 (Cloud Sync)

端到端闭环的实现依赖于动态注入的环境变量。本地不再存在硬编码的脏逻辑。

### 4.1 环境变量规范
在本地胖客户端的 `.env` 中，需显式声明生产环境入口：
```env
CLOUD_BASE_URL=http://cuma.autrenative.com
```

### 4.2 触发机制
`CloudSyncService` (`cloud_sync.py`) 会在以下情况激活：
1. **鉴权阶段:** 利用配置的凭证向 `/auth/login` 发起请求，获取 JWT Token。
2. **静默同步:** 将本地 SQLite 中新产生的 `telemetry_sync_logs`（复习动作、UI 交互），以 Batch 形式打包 `POST` 到云端 `/sync/telemetry` 接口。
3. **容错机制:** 若出现网络断开或 50x 错误，捕获 `httpx.HTTPStatusError`，终止本次同步并保留本地日志标志位，等待网络恢复后自动愈合重试。

