# 墨灵（Moling / Living Notebook）

墨灵是一款 Android 平板优先的 AI 手写笔记本。用户在纸面上写，客户端优先本地识别文字，服务端生成回应，回应再以墨迹浮现在纸面上。它不是聊天软件，也不会把纸面改造成气泡、头像或消息列表。

## M0-A 生产基线

本仓库已建立 v0.8 后续工程所需的第一版生产边界：

- 后端生产默认供应商为 DeepSeek，普通回应使用 `deepseek-v4-flash`，深度回应预留 `deepseek-v4-pro`；
- 业务服务依赖 `ModelProvider` 协议，不直接绑定模型 SDK；
- 使用 OpenAI-compatible `POST /chat/completions`、JSON Output、超时和最多一次受控重试；
- Persona、模式路由、安全规则与输出 schema 已从 `main.py` 拆为版本化文件；
- `assistant_name` 始终与 `user_id` 或匿名 `device_profile_id` 一起解析；
- 生产日志只记录请求 ID、模型、耗时、Token、成本估算和错误类别，不记录笔记正文、最近上下文或完整回应；
- Vision fallback 与图片落盘在生产配置中被强制关闭；
- Android Debug/Release 后端地址由 BuildConfig 分离，Release 只接受 HTTPS 且禁止明文流量；
- 本地开发可使用确定性的 fake provider，不需要真实 DeepSeek Key。

这只是 M0-A 代码基线。当前没有宣称生产后端已经部署、应用已经签名、真机已经验证或商店已经提交。

## 核心链路

```text
用户 strokes
→ 保留在客户端并由 ML Kit 本地识别
→ recognizedText + 当前隔离身份
→ Moling backend ReplyService
→ ModelProvider
→ DeepSeek 结构化回应
→ InkReplyOverlay 墨迹浮现
```

识别、网络或模型失败时，现有客户端失败分支会恢复发送状态并保留原始 strokes。Vision 仍只是明确的开发 fallback，默认关闭。

## 仓库结构

```text
moling/
├─ backend/
│  ├─ app/
│  │  ├─ models/
│  │  ├─ prompts/
│  │  ├─ providers/
│  │  └─ services/
│  ├─ tests/
│  ├─ main.py
│  └─ .env.example
├─ moling-android/
├─ scripts/secret_scan.py
├─ docs/launch/
└─ AGENTS.md
```

开发前必须完整阅读根目录 `AGENTS.md` 和 `docs/launch/`。产品品牌固定为“墨灵 / Moling”；角色显示名由每个用户自行设置。名称相同绝不代表身份、关系或记忆相同，任何未来记忆存储都只能按认证用户或匿名设备作用域读取。

## 后端本地运行

推荐 Python 3.12+。

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m pytest -q
uvicorn main:app --host 127.0.0.1 --port 8000
```

`.env.example` 默认使用 `MODEL_PROVIDER=fake`，因此测试、健康检查和本地 smoke test 不需要联网或真实 Key。

健康检查：

```text
GET http://127.0.0.1:8000/healthz
```

文本回应：

```json
POST /api/notebook/reply
{
  "requestId": "request-uuid",
  "deviceProfileId": "device-profile-uuid",
  "assistantName": "墨灵",
  "recognizedText": "今天先做哪一步",
  "recognitionSource": "mlkit",
  "recentContext": null
}
```

`userId` 与 `deviceProfileId` 必须且只能提供一个。M0-A 先固定这个作用域边界；真实 Access Token 校验、账号 profile store、限流和预算闸门属于下一轮 M0-B。

## DeepSeek 生产配置

部署时从 Secret 管理注入：

```env
MOLING_ENV=production
MODEL_PROVIDER=deepseek
DEEPSEEK_API_KEY=<deployment-secret>
PROVIDER_USER_ID_SALT=<deployment-secret>
```

其余非 Secret 默认值见 `backend/.env.example`。生产启动校验会拒绝：

- 缺少 DeepSeek Key；
- fake provider；
- 非 HTTPS DeepSeek base URL；
- 非规划模型名；
- 默认开发盐；
- 启用 Vision fallback 或图片落盘。

DeepSeek Key、provider salt、签名密钥和私人 memory seed 不得进入 Android、Git、日志、测试快照或注释。

## Android 构建配置

Debug 默认使用模拟器可访问的本机地址：

```text
http://10.0.2.2:8000
```

可在本地 `gradle.properties` 或命令行覆盖：

```powershell
.\gradlew.bat :app:testDebugUnitTest :app:assembleDebug `
  -PMOLING_DEBUG_BACKEND_URL=http://192.168.1.10:8000
```

Release 默认占位 URL 为 `https://api.moling.app`。真实部署域名确定后通过构建属性注入：

```powershell
.\gradlew.bat :app:assembleRelease `
  -PMOLING_RELEASE_BACKEND_URL=https://api.example.com
```

Release 配置阶段会拒绝 `http://`，合并后的 Manifest 将 `usesCleartextTraffic` 设为 `false`。普通设置页不提供任意后端 URL。

## 验证

```powershell
cd backend
python -m pytest -q
cd ..
python scripts/secret_scan.py

cd moling-android
.\gradlew.bat :app:testDebugUnitTest :app:assembleDebug :app:assembleRelease
```

GitHub Actions 会执行后端测试、源代码 Secret 扫描、Android Debug 单元测试以及 Debug/Release 构建。

## 仍待 M0-B 完成

- Android Access Token 与服务端强制认证；
- 按认证用户持久化的 profile store，账号切换/登出清理；
- 限流、每日/月度额度、全局预算熔断与幂等请求存储；
- 本地页面/strokes/reply 数据库、请求状态机和进程重启后的失败恢复；
- 生产 HTTPS 部署与远程 smoke test；
- 签名密钥体系、v0.8 签名 APK/AAB 和真机验证；
- 无 GMS 华为设备的识别模型状态与替代识别路径验证。
