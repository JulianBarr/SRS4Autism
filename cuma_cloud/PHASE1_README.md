# Cuma Cloud Control Plane - Phase 1

## 1. Alembic 初始化（若尚未执行）

若您尚未初始化 Alembic，在项目根目录执行：

```bash
cd cuma_cloud
alembic init -t async migrations
```

**注意**：本仓库已预置 `migrations/` 与 `env.py`，可直接使用。若您自行执行 `alembic init`，请用本仓库的 `env.py` 覆盖生成的版本。

## 2. 环境变量

在 `cuma_cloud/` 目录下创建 `.env`（配置仅从此文件加载，不会读取项目根目录的 `.env`）：

```bash
cd cuma_cloud
cp .env.example .env
# 编辑 .env 填写以下变量
```

必填变量：
- `DATABASE_URL`：`postgresql+asyncpg://user:password@host:port/dbname`
- `JWT_SECRET`：JWT 签名密钥
- `ENVIRONMENT`：`dev` 或 `prod`

## 3. 依赖安装

```bash
cd cuma_cloud
pip install -r requirements.txt
```

或从项目根目录（若 cuma_cloud 在 PYTHONPATH 中）：

```bash
pip install -r cuma_cloud/requirements.txt
```

## 4. 生成并执行迁移

从**项目根目录**（SRS4Autism）执行，确保 `cuma_cloud` 包可被导入：

```bash
cd /path/to/SRS4Autism
alembic -c cuma_cloud/alembic.ini revision --autogenerate -m "init"
alembic -c cuma_cloud/alembic.ini upgrade head
```

或在 `cuma_cloud` 目录下且已设置 `PYTHONPATH` 包含父目录时：

```bash
cd cuma_cloud
PYTHONPATH=.. alembic revision --autogenerate -m "init"
PYTHONPATH=.. alembic upgrade head
```

## 5. 验证

确认 PostgreSQL 中已创建 `cloud_accounts`、`abac_policies`、`telemetry_sync_logs` 三张表。
