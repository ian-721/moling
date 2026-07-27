# 墨灵（Moling / Living Notebook）

墨灵是一款 Android 平板优先的 AI 手写笔记本。用户在纸面上写，客户端本地识别并先保存笔迹，服务端生成回应，回应再以墨迹浮现在纸面上。它不是聊天软件，不使用气泡、头像或消息列表。

## v0.8 M0-B 代码基线

当前分支在 M0-A DeepSeek V4 基线上形成远程安装闭环：

- 匿名安装注册为 `principal_type=device`；
- 服务端签发至少 256-bit opaque bearer token，只保存 HMAC 摘要；
- Android 用 Android Keystore AES-256-GCM 保存 Token，密文不参与备份；
- Reply、Profile 和 Usage 均只信任 Bearer Token，不信任正文身份或名称；
- `assistant_name` 按 `principal_id` 存储，同名身份互不关联；
- SQLAlchemy 2.x + Alembic，开发/测试 SQLite，生产 PostgreSQL；
- 每 principal 分钟限流、日/月额度及全局人民币预算事务闸门；
- `(principal_id, request_id)` 幂等、内容指纹冲突和处理租约；
- Room 本地保存页面、完整 stroke points、turn 和 reply outbox；
- 失败、重试、进程重启和 stale response 均不删除原笔迹；
- v0.8 `versionCode=800` / `versionName=0.8.0`，Debug、Release APK 和 AAB 构建管线；
- Docker、迁移启动、健康/就绪探针、部署与回滚基线。

代码基线不等于真实生产部署、永久签名或真机通过。状态必须以本轮构建、环境凭据和 `adb devices` 的实际结果为准。

## 核心链路

```text
stroke 完成
→ Room 立即持久化
→ “回应”事务快照 stroke IDs + requestId
→ ML Kit 本地识别
→ Android Keystore Token
→ HTTPS Bearer 鉴权
→ principal profile / 配额 / 预算 / 幂等
→ DeepSeek V4 或测试 Provider
→ Room 先保存回应
→ InkReplyOverlay 墨迹浮现
→ 仅吸收该请求快照的 strokes
```

## 后端本地运行

推荐 Python 3.12+：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m pytest -q
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

本地 `.env.example` 使用 SQLite + fake provider，无需真实 DeepSeek Key。

```text
GET  /healthz
GET  /readyz
POST /api/auth/device/register
GET  /api/profile
PATCH /api/profile
GET  /api/usage
POST /api/notebook/reply
```

除注册和健康检查外，接口要求 `Authorization: Bearer <token>`。

完整认证、配额、幂等与恢复协议见
`docs/launch/M0B_REMOTE_INSTALL_PROTOCOL.md`；容器部署见
`docs/deployment/M0B_DEPLOYMENT.md`。

## 生产配置

生产必须：

- `MOLING_ENV=production`
- `MODEL_PROVIDER=deepseek`
- PostgreSQL `DATABASE_URL`
- Secret 管理注入 `DEEPSEEK_API_KEY`、`PROVIDER_USER_ID_SALT`、`TOKEN_HASH_PEPPER`
- 显式配置 Token TTL、注册开关/保护、限流、日/月额度、租约和全局预算
- HTTPS ingress
- Vision 与图片落盘关闭

缺少任何生产控制时启动会拒绝。真实值不得进入 Git、Android、Docker image、日志或 CI 输出。

## Android 构建

使用 JDK 21：

```powershell
cd moling-android
.\gradlew.bat :app:testDebugUnitTest :app:lintDebug `
  :app:assembleDebug :app:assembleRelease :app:bundleRelease
```

Release URL 通过 `-PMOLING_RELEASE_BACKEND_URL=https://...` 注入，且必须 HTTPS。
unsigned CI 基线使用不可路由的 `https://release.invalid`；永久签名构建必须显式
提供真实 hostname。签名只读取四个 `MOLING_KEYSTORE_*` 环境变量；全无时仍可
构建 unsigned Release。完整步骤见 `docs/release/V0_8_BUILD_SIGN_INSTALL.md`。

## 验证

```powershell
cd backend
python -m alembic upgrade head
python -m alembic check
python -m pytest -q
cd ..
python scripts/secret_scan.py
```

CI 执行迁移 smoke、后端测试、生产配置负向测试、Secret scan、Android Room/身份/恢复单测、lint、Debug/Release APK 与 Release AAB 构建。CI 不需要真实 DeepSeek、PostgreSQL、签名或云平台凭据。

M0-B.3A 进一步使用 CI PostgreSQL 17 服务执行全新数据库 migration smoke，
在运行时生成并 mask 临时 preflight Secret，并在不复制 `.env` 的情况下
构建 Docker image。生产 salt/pepper 必须各至少 32 UTF-8 bytes，且已知
placeholder 会被拒绝。真实部署前可执行：

```powershell
python scripts/deployment_preflight.py
python scripts/android_release_preflight.py `
  --backend-url 'https://<authorized-host>'
python scripts/remote_https_smoke.py `
  --base-url 'https://<authorized-host>'
```

远程 smoke 默认不创建数据或调用模型；只有显式加入 `--exercise-api` 才会创建
一次性 principal 并调用普通/深度回复。完整差距矩阵、外部输入和回滚协议见
`docs/deployment/M0B3A_REAL_ENVIRONMENT_PREFLIGHT.md`。

## M0-C 不在本轮

- 云端笔记或多设备同步；
- Google/华为/邮箱登录；
- 长期记忆和私人 seed 导入；
- 支付、订阅和商店权益；
- iOS/Web；
- 商店正式提交。
