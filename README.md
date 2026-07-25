# 墨灵（Moling / Living Notebook）

墨灵是一款 Android 平板优先的 AI 手写笔记本。

用户在纸面界面上手写，客户端优先在本地识别文字，服务端生成回应，再由客户端以墨迹动画写回纸面。它不是聊天软件，核心体验是：

> 写下，它会像一本熟悉你、有判断的笔记本一样回应。

## 当前状态

当前仓库已有可运行的早期原型，核心链路已经形成，但生产化改造尚未完成。

截至 2026-07-25，项目已经正式冻结以下方向：

- 从内部原型进入正式上线工程；
- 生产默认模型迁移到 DeepSeek V4；
- 建设“老g”人格与每个用户隔离的私有记忆；
- 完成本地持久化、账号与多端同步；
- 推进 Google Play 和华为 AppGallery 实际上架；
- 建设免费额度、订阅和统一权益架构。

**重要：当前代码仍包含旧 OpenAI Responses API 原型实现和局域网开发配置。上述迁移尚未宣称完成，等待 M0-A 工程任务实际修改、测试和部署。**

## 核心链路

```text
用户 strokes
→ 本地保存
→ ML Kit 本地文字识别
→ 服务端加载人格、记忆和最近上下文
→ DeepSeek 生成结构化回应
→ InkReplyOverlay 墨迹浮现
→ 本地保存并后台同步
```

OpenAI Vision OCR 只保留为开发阶段的 fallback/debug 路径，不应作为默认识别方式或华为兼容问题的长期解决方案。

## 仓库结构

```text
moling/
├─ moling-android/       # Kotlin + Jetpack Compose Android 客户端
├─ backend/              # Python FastAPI 后端
├─ docs/
│  ├─ launch/            # 正式上线、人格、DeepSeek、商店与收费规划
│  └─ ...                # 早期开发资料
├─ AGENTS.md             # 当前最高优先级项目规则
└─ README.md
```

## 正式规划

开发前必须阅读：

1. [`docs/launch/01_MOLING_LAUNCH_MASTER_PLAN.md`](docs/launch/01_MOLING_LAUNCH_MASTER_PLAN.md)
2. [`docs/launch/02_OLD_G_PERSONA_AND_MEMORY_SPEC.md`](docs/launch/02_OLD_G_PERSONA_AND_MEMORY_SPEC.md)
3. [`docs/launch/03_DEEPSEEK_BACKEND_AND_COST_PLAN.md`](docs/launch/03_DEEPSEEK_BACKEND_AND_COST_PLAN.md)
4. [`docs/launch/04_STORE_SYNC_MONETIZATION_PLAN.md`](docs/launch/04_STORE_SYNC_MONETIZATION_PLAN.md)
5. [`docs/launch/05_CODEX_FIRST_EXECUTION_PROMPT.md`](docs/launch/05_CODEX_FIRST_EXECUTION_PROMPT.md)

根目录 [`AGENTS.md`](AGENTS.md) 与上述文件构成当前正式基线。

## 技术栈

### Android

- Kotlin
- Jetpack Compose
- Canvas / PathMeasure 墨迹动画
- ML Kit Digital Ink Recognition
- DataStore
- 计划加入本地数据库与同步队列

### Backend

当前原型：

- Python
- FastAPI
- OpenAI Responses API

冻结的生产目标：

- FastAPI
- DeepSeek OpenAI-compatible Chat Completions API
- `deepseek-v4-flash` 默认回应
- `deepseek-v4-pro` 深度回应
- 供应商适配层
- JSON Output
- 鉴权、限流、预算和脱敏日志

## 当前本地启动方式

以下仅适用于当前原型开发环境，M0-A 完成后将更新。

### 后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8000
```

健康检查：

```text
GET http://127.0.0.1:8000/healthz
```

核心接口：

```text
POST /api/notebook/reply
```

真实 API Key 不得写入代码、Android 客户端、Git、日志或提交历史。

### Android

1. 使用 Android Studio 打开 `moling-android/`；
2. 等待 Gradle Sync；
3. 当前原型仍通过 `BackendConfig.kt` 指定局域网地址；
4. 真机与后端电脑需位于同一局域网；
5. 执行 Build 和 Run。

该流程不是生产发布方式。M0-A 必须改成 Debug/Release 环境分离，Release 只使用 HTTPS。

## 已知上线阻塞

- 后端仍是 OpenAI 原型调用；
- Android 后端地址仍为局域网硬编码；
- Release 仍允许明文 HTTP；
- 无正式鉴权、限流和全局预算；
- 生产日志可能包含用户正文；
- Vision debug 图片可能落盘；
- 本地笔记持久化与同步尚未完成；
- 未建立签名 APK/AAB 和商店发布流程；
- 华为等无 GMS 设备可能无法下载 ML Kit 模型；
- CI、自动化测试和全新环境复现仍需完成；
- 约 50 MB 手写字体资源仍需评估。

## 当前下一步

Codex 额度恢复后，直接执行：

[`docs/launch/05_CODEX_FIRST_EXECUTION_PROMPT.md`](docs/launch/05_CODEX_FIRST_EXECUTION_PROMPT.md)

首轮必须同时完成基线核验与实际代码交付，不能只输出审计报告。

## 开发规则

修改代码前必须阅读 [`AGENTS.md`](AGENTS.md)。其中定义了产品本质、DeepSeek 模型决策、老g人格、用户记忆隔离、密钥边界、上线顺序和禁止破坏的体验约束。
