# M0-B.3A real-environment release preflight

更新时间：2026-07-27

本文只收口仓库内部的部署、签名和验收前置条件，不代表已经部署生产、
提供 Secret、完成永久签名或通过真机/华为验收。

## 1. 冻结基线

实时执行 `git fetch origin --prune` 后的证据：

| 检查项 | 结果 |
|---|---|
| 权威 remote | `origin=https://github.com/ian-721/moling.git` |
| 工作前本地分支 | `main` |
| 工作前 `HEAD` | `53b171f4ebb64ed9c55886170f266d9cc4264877` |
| 本地 `main` | `53b171f4ebb64ed9c55886170f266d9cc4264877` |
| `origin/main` | `53b171f4ebb64ed9c55886170f266d9cc4264877` |
| `main...origin/main` | ahead `0` / behind `0` |
| 工作前工作区 | clean |
| Merge Commit parents | `111137ea918e5859e8edbf534b6dbaefe44eafd7`、`04d1fd62f63b2f5de252cc69bb7eb4dbd8a0efb5` |
| M0-B.3A 分支 | `launch/m0b3-real-environment-preflight`，从实时 `origin/main` 创建 |
| 合并后 `main` CI | `unverified` |

`main` CI 不能核验的具体原因：

- GitHub 连接器对该 merge SHA 未返回 workflow run 或 combined status；
- 本机 `gh auth status` 报告默认账号令牌无效；
- 未使用 PR #11 的分支 CI 冒充合并后 `main` push CI。

## 2. 发布前置条件差距矩阵

| 检查项 | 当前状态 | 证据路径 | 风险 | 代码修改 | 用户外部输入 | 下一阶段执行方式 |
|---|---|---|---|---|---|---|
| Docker 不依赖 `.env` 构建 | 源码满足，CI 关卡已新增；本机无 Docker CLI | `backend/Dockerfile`、`backend/.dockerignore`、`.github/workflows/ci.yml` | P0 | 是，新增 CI build | 否 | 本分支 CI 必须通过 `docker build ./backend` |
| PostgreSQL/DeepSeek/pepper/salt 仅运行时注入 | 已满足；image 不复制环境文件 | `backend/app/config.py`、`backend/.env.example`、`backend/Dockerfile` | P0 | 否 | 是 | 部署平台 Secret 管理器注入，禁止粘贴到聊天/Git/日志 |
| 生产缺失/默认/placeholder/低强度配置拒绝启动 | 已满足并有自动负向测试；HMAC salt/pepper 最少 32 UTF-8 bytes | `backend/app/config.py`、`backend/tests/test_config.py`、`backend/tests/test_preflight_scripts.py`、`scripts/deployment_preflight.py` | P0 | 是 | 是 | 部署前在目标平台 Secret 环境运行 preflight |
| 全新 PostgreSQL `upgrade head` | 仓库 CI 骨架已补齐；真实实例仍待执行 | `.github/workflows/ci.yml`、`backend/migrations/` | P0 | 是 | 是 | CI PostgreSQL 17 smoke；M0-B.3B 对真实 staging PostgreSQL 再执行 |
| readiness 验证数据库 | 已满足，执行 `SELECT 1`，失败返回 503 | `backend/app/api.py` | P0 | 否 | 是 | 经生产 HTTPS hostname 调用 `/readyz` |
| 日志无 Token/正文/上下文/回复 | 应用日志守卫已覆盖；平台 ingress 日志仍待检查 | `backend/tests/test_api.py`、`backend/app/api.py` | P0 | 是，扩展测试 | 是 | 真实 smoke 后查询平台日志并保存脱敏证据 |
| 可重复远程 HTTPS smoke | 已新增；默认只探测，写操作需显式开关 | `scripts/remote_https_smoke.py` | P0 | 是 | 是 | 显式传入授权 hostname；真实调用使用 `--exercise-api` |
| 部署前/后/回滚协议 | 已补齐仓库协议；真实演练待执行 | 本文、`docs/deployment/M0B_DEPLOYMENT.md` | P0 | 是 | 是 | M0-B.3B 保存镜像 digest、迁移和回滚证据 |
| Release HTTPS/cleartext/Vision | 源码守卫和 preflight 已存在 | `moling-android/app/build.gradle.kts`、Manifest、`scripts/android_release_preflight.py` | P0 | 是，新增 preflight | 是 | 对真实 Release hostname 执行脚本并构建 |
| signing 四项全有或全无 | Gradle 与 preflight 双守卫；永久材料未提供 | Gradle、`scripts/android_release_preflight.py` | P0 | 是，新增 preflight | 是 | 永久 keystore 在安全存储中提供，执行 `--require-signing` |
| 真机证据可复核 | 模板已新增；没有真实执行结果 | `docs/release/V0_8_DEVICE_ACCEPTANCE_TEMPLATE.md` | P0 | 是 | 是 | 授权 Android/华为设备逐项记录，不记录笔记正文或 Token |
| 华为无 GMS + ML Kit | 代码明确失败、不用 Vision 掩盖；兼容性未知 | `InkRecognitionService.kt`、真机模板 | P0 | 否 | 是 | 无 GMS 华为设备联网下载/识别实测 |
| main push CI | 无可核验证据 | 本文第 1 节 | P1 | 否 | 是 | 修复 GitHub 授权后按 merge SHA 读取 push run |
| quota/global budget 真实闸门 | 自动测试已有；真实平台隔离验收待执行 | `backend/tests/test_api.py`、本文第 4 节 | P0 | 否 | 是 | 只在 staging 使用低额度配置，不耗尽生产预算 |

## 3. 外部资源输入清单

以下内容必须由用户在 M0-B.3B 明确授权或通过目标平台的 Secret/设备通道
提供。任何 Secret 都不得粘贴进聊天、Git、PR、CI 普通变量或日志。

- 被明确授权的部署平台、项目/服务和可回滚权限；
- 全新或专用 staging PostgreSQL，以及生产 PostgreSQL；
- HTTPS hostname、证书终止方式和 DNS 控制权；
- DeepSeek API Key；
- 独立高熵 `PROVIDER_USER_ID_SALT`；
- 独立高熵 `TOKEN_HASH_PEPPER`；
- Token TTL、注册开关/速率/容量、principal 分钟/日/月额度；
- 全局月预算、请求租约、最大尝试次数和单请求预算预留值；
- 永久 Android keystore 的安全存储位置和备份/恢复责任人；
- 四项 `MOLING_KEYSTORE_PATH`、`MOLING_KEYSTORE_PASSWORD`、
  `MOLING_KEY_ALIAS`、`MOLING_KEY_PASSWORD`；
- Android 测试设备型号、系统版本、可用连接方式和授权测试窗口；
- 华为无 GMS 设备、GMS 状态、网络条件和 ML Kit 模型下载条件。

## 4. 可执行验收协议

### 4.1 部署前

1. 冻结待部署 commit 和 Docker image digest，确认工作区 clean。
2. 在不包含 `.env` 的 backend context 构建：

   ```powershell
   docker build --tag moling-backend:m0b3b .\backend
   ```

3. 在部署平台的 Secret 环境执行；脚本不输出 Secret 值，也不联网：

   ```powershell
   python .\scripts\deployment_preflight.py
   ```

4. 对 staging PostgreSQL 执行：

   ```powershell
   Set-Location .\backend
   python -m alembic upgrade head
   python -m alembic check
   Set-Location ..
   ```

5. 记录数据库实例标识、Alembic revision、命令退出码和时间。不得记录
   `DATABASE_URL`。

### 4.2 部署后只读探测

只允许对明确授权的 hostname 执行：

```powershell
python .\scripts\remote_https_smoke.py `
  --base-url 'https://<authorized-host>'
```

这一步验证 TLS、`/healthz`、数据库驱动的 `/readyz` 和未认证 401，不创建
principal，也不调用模型。

### 4.3 显式写入与真实 DeepSeek

确认 staging 数据可丢弃、DeepSeek 费用已授权后执行：

```powershell
python .\scripts\remote_https_smoke.py `
  --base-url 'https://<authorized-host>' `
  --exercise-api
```

脚本创建一次性匿名设备 principal，复用同一 Bearer Token 完成 Profile
读取/改名和 Usage 读取，并验证：

- 普通响应为 `provider=deepseek`、Flash、`degraded=false`；
- 深度响应为 Pro，或 `degraded=true` 时明确降级到 Flash；
- `requestId` 和必要响应字段完整且匹配；
- 普通回复后日/月 Usage 各增加 1；
- 相同 `requestId` 重放后 Usage 不变；
- 不同 payload 的 409 冲突后 Usage 不变；
- 深度回复后日/月 Usage 再各增加 1。

脚本不打印 Token、回应正文或 Secret。

Android Token 跨进程持久化不能由这个脚本替代，必须按真机模板验证。

### 4.4 配额和全局预算闸门

只在独立 staging 服务执行：

1. 用低但正数的日/月额度部署一次性配置；
2. 注册一次性 principal；
3. 调用至得到 `daily_quota_exceeded` 或 `monthly_quota_exceeded`；
4. 另起隔离 staging 配置，使
   `GLOBAL_MONTHLY_BUDGET_CNY < REQUEST_COST_RESERVATION_CNY`；
5. 首次模型请求必须在 Provider 调用前得到 `global_budget_exhausted`；
6. 恢复正式配置并重新运行 `/readyz`。

不得通过耗尽真实生产预算来证明闸门。

### 4.5 日志泄漏检查

围绕 smoke 的 request ID 和时间窗检查应用、ingress、数据库及平台日志：

- 不得出现 `Authorization`、`Bearer`、原始 Token、Token HMAC；
- 不得出现 smoke 的 `recognizedText`、`recentContext` 或完整回复；
- 不得出现 DeepSeek Key、pepper、salt、PostgreSQL URL；
- 允许 request ID、匿名 principal、模型、耗时、Token 数、成本和状态。

只保存脱敏后的查询条件、命中数和结论，不下载或提交完整生产日志。

### 4.6 Android Release 与真机

在本地安全 shell 提供真实 Release hostname 和永久签名变量：

```powershell
python .\scripts\android_release_preflight.py `
  --backend-url 'https://<authorized-host>' `
  --require-signing

Set-Location .\moling-android
.\gradlew.bat :app:testDebugUnitTest :app:lintDebug `
  :app:assembleDebug :app:assembleRelease :app:bundleRelease `
  -PMOLING_RELEASE_BACKEND_URL='https://<authorized-host>'
```

随后按 `docs/release/V0_8_DEVICE_ACCEPTANCE_TEMPLATE.md` 验证：

- 签名 APK 安装、首次注册和 Token 跨重启持久化；
- Profile 读取/改名、Usage、普通/深度真实回复；
- 手写与 ML Kit 识别；
- 断网后保留笔迹；
- force-stop/重启恢复；
- 同 `requestId` 重试；
- 吸收动画期间新增笔迹不被删除；
- 华为无 GMS 下的模型状态和真实识别结果。

### 4.7 回滚与数据保持

1. 部署前记录当前 image digest、Alembic revision 和数据库备份/PITR 点。
2. 应用失败时先停止 rollout，把流量切回上一个已知 image；不执行破坏性
   `alembic downgrade`。
3. 核验 `/healthz`、`/readyz`，使用验收 principal 读取 Profile/Usage。
4. 核对回滚前后 principal、profile、usage、request 记录数量或抽样 ID；
   只记录数量/匿名 ID，不记录正文、Token hash 或 response snapshot。
5. 若旧 image 与新 schema 不兼容，保持服务停止，修复 migration 后向前
   部署；不得删表恢复。

## 5. M0-B.3B 启动条件

仓库代码层在本分支 CI 全部通过且 Draft PR 合并后，可视为具备 M0-B.3B
的内部前置条件。真实部署仍被以下 P0 外部门阻止：

1. 未授权部署平台和 PostgreSQL；
2. 未提供 HTTPS hostname/DNS/证书控制；
3. DeepSeek Key、salt、pepper 尚未通过 Secret 管理器注入；
4. 生产额度、预算和租约值尚未由用户冻结；
5. 永久 keystore 与四项签名输入未提供；
6. Android 与华为无 GMS 测试设备/窗口未提供。

只有在上述资源通过安全通道就绪、M0-B.3A CI/PR 已完成、回滚责任和数据
备份方式明确后，才能开始 M0-B.3B。开始 M0-B.3B 不代表可以自行购买资源、
修改 DNS、创建临时“永久”keystore 或把 Secret 写入聊天。

## 6. 本轮本地验证记录

以下结果只证明当前 checkout 的仓库内部状态：

| 验证 | 结果 |
|---|---|
| Python runtime | 3.12.13（仓库既有 `.venv-m0b`） |
| `pip check` | PASS，`No broken requirements found` |
| `pytest -q` | PASS，103 tests；1 条依赖弃用 warning |
| 独立 SQLite `alembic upgrade head` | PASS，升级到 `20260726_0002` |
| 独立 SQLite `alembic check` | PASS，`No new upgrade operations detected` |
| Secret scan | PASS |
| deployment preflight（运行时随机临时 Secret） | PASS；只验证结构/强度，未联网且未打印值 |
| 三个 preflight/smoke 脚本负向矩阵 | PASS；placeholder/短 Secret/模糊布尔值、签名/URL、DeepSeek 响应契约/Usage/幂等计数均有可重复测试 |
| Android Release preflight | unsigned 正向 PASS；partial signing、signed 无显式 URL、signed `.invalid` 和不安全 URL 负向 PASS |
| Gradle signing/URL 负向守卫 | all-or-none、显式 URL、`.invalid` 拒绝均 PASS |
| Android 完整命令 | PASS，113 tasks，`BUILD SUCCESSFUL` |
| Release merged manifest | `usesCleartextTraffic=false` |
| Release BuildConfig | `BACKEND_BASE_URL=https://release.invalid`、Vision=false |
| Release artifact | unsigned APK/AAB 基线；未宣称永久签名 |
| Docker build | 本机 BLOCKED：未安装/不可用 Docker CLI；由新增 CI step 验证 |
| PostgreSQL migration | 本机未连接真实 PostgreSQL；新增 CI PostgreSQL 17 service 待分支 CI 验证 |
| 远程 HTTPS/DeepSeek | 未执行：没有授权 hostname/Secret |
| 签名 APK 真机/华为 | 未执行：没有永久签名输入和授权设备 |
