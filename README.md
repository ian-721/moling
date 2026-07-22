# 墨灵（Moling / Living Notebook）

墨灵是一款面向 Android 平板的 AI 手写笔记本原型。

用户在纸面界面上手写，客户端优先通过 ML Kit Digital Ink Recognition 在本地识别文字，后端调用大模型生成回应，再由客户端以墨迹动画写回纸面。它不是聊天软件，核心体验是“笔记本像有灵魂一样回应”。

> 当前状态：可运行的早期原型，供内部开发和真机测试使用，尚未按生产环境标准完成配置、测试与部署。

## 核心链路

```text
用户手写 strokes
→ ML Kit 本地文字识别
→ FastAPI 后端生成回复
→ InkReplyOverlay 墨迹浮现
```

OpenAI Vision OCR 仅保留为开发阶段的 fallback/debug 路径，不应作为默认识别方式。

## 仓库结构

```text
moling/
├─ moling-android/       # Kotlin + Jetpack Compose Android 客户端
├─ backend/              # Python FastAPI 后端
├─ docs/                 # 早期开发资料
├─ AGENTS.md             # 项目约束与开发规则
└─ README.md
```

## 技术栈

**Android**

- Kotlin
- Jetpack Compose
- Canvas / PathMeasure 墨迹动画
- ML Kit Digital Ink Recognition

**Backend**

- Python
- FastAPI
- OpenAI Responses API
- Pydantic

## 启动后端

以下命令以 Windows PowerShell 为例：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `backend/.env`：

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=your_model_id_here
```

启动服务：

```powershell
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

`backend/.env` 已被 Git 忽略，不得将真实 API Key 写入代码、日志、Android 客户端或提交历史。

## 启动 Android 客户端

1. 使用 Android Studio 打开 `moling-android/`。
2. 等待 Gradle Sync 完成。
3. 打开：

```text
moling-android/app/src/main/java/com/moling/livingnotebook/data/remote/BackendConfig.kt
```

4. 将 `BASE_URL` 改为当前开发环境地址：
   - Android 模拟器访问本机后端：`http://10.0.2.2:8000`
   - 真机访问电脑后端：`http://<电脑局域网IP>:8000`
5. 确保真机与电脑位于同一局域网，再执行 Build 和 Run。

首次使用本地手写识别时，ML Kit 可能需要下载语言模型。部分缺少 GMS 的设备可能无法正常完成下载，需要单独处理兼容性。

## 当前开发边界

现阶段优先保证手写、识别、生成回复和墨迹浮现链路稳定。

暂不优先建设：

- 登录与账户系统
- 数据库和云同步
- 支付与订阅
- 复杂生产部署

下一阶段产品方向主要是设置能力，包括回复字号、AI 回复字体、纸张背景、墨色、调试开关和本地持久化。

## 已知问题

- Android 后端地址仍为开发常量，需要手动修改。
- 华为等缺少 GMS 的设备可能遇到 ML Kit 模型下载问题。
- 仓库暂未配置完整 CI、自动化测试和发布流程。
- 手写字体资源约 50 MB，GitHub 会给出大文件提示；后续应评估压缩、替换或迁移到 Git LFS。
- 当前 README 仅用于基础建档，尚未完成全新环境复现验证。

## 后续 Codex 建档任务

后续应通过 Codex 对仓库执行一次完整的“仓库建档与可运行性核验”：

1. 从全新 clone 验证 Android 与后端启动步骤。
2. 核验依赖版本、环境变量和密钥边界。
3. 移除或配置化硬编码的后端地址。
4. 增加后端 smoke test 与基础 Android 测试。
5. 建立最小 CI。
6. 检查大字体文件的 Git LFS 或替代方案。
7. 根据真实代码重写正式 README 和开发文档。

## 开发规则

修改代码前请先阅读 [`AGENTS.md`](./AGENTS.md)。其中定义了产品本质、关键技术路径、密钥边界和禁止破坏的体验约束。
