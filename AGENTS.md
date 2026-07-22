# AGENTS.md — 墨灵项目规则

本项目名为“墨灵 / Moling / Living Notebook”。

## 产品本质

墨灵不是聊天软件，不是普通 AI 笔记，也不是心理咨询 App。

它是一个 Android 平板优先的 AI 手写笔记本：
用户在纸面上手写，App 识别文字，后端大模型生成回应，回应以墨迹形式浮现在纸面上。

核心体验是：
用户写下一段话，笔记本像有灵魂一样回应。

## 当前技术栈

Android:
- Kotlin
- Jetpack Compose
- Canvas
- ML Kit Digital Ink Recognition
- 本地 stroke 手写输入
- 真机测试设备主要是 HUAWEI MRO-W00，但该设备可能缺少 GMS，ML Kit 下载可能失败

Backend:
- Python FastAPI
- OpenAI Responses API
- backend/.env 保存 OPENAI_API_KEY 和 OPENAI_MODEL
- API Key 绝对不能进入 Android 端

## 重要约束

1. 不要把 OpenAI API Key 写进 Android、Git、日志或注释。
2. 不要修改 Gradle Wrapper。
3. 不要大规模重构无关代码。
4. 不要把界面做成聊天气泡、头像、对话列表。
5. 不要删除 ML Kit 主识别路径。
6. 不要偷偷把 OpenAI Vision OCR 设回默认主路径。
7. Vision OCR 只能作为明确 fallback/debug。
8. 用户笔迹识别失败时，必须恢复笔迹，不能丢内容。
9. 回复不能一直追问用户；墨灵要冷静、靠谱、有判断。
10. AI 回复视觉必须像写在纸上的墨迹，不是普通聊天文本。

## 当前关键路径

正确链路应为：

用户 strokes
→ ML Kit Digital Ink Recognition
→ recognizedText
→ backend reply_stage
→ aiReply
→ InkReplyOverlay 墨迹浮现

OpenAI Vision OCR 只作为 fallback/debug，不是默认主路径。

## 文件结构重点

Android 项目在：
moling-android/

后端在：
backend/

重要 Android 文件：
- app/src/main/java/com/moling/livingnotebook/data/recognition/InkRecognitionService.kt
- app/src/main/java/com/moling/livingnotebook/ui/components/InkReplyOverlay.kt
- app/src/main/java/com/moling/livingnotebook/ui/NotebookPageScreen.kt
- app/src/main/java/com/moling/livingnotebook/viewmodel/NotebookViewModel.kt
- app/src/main/java/com/moling/livingnotebook/data/remote/NotebookApiClient.kt
- app/src/main/java/com/moling/livingnotebook/data/remote/BackendConfig.kt

重要后端文件：
- backend/main.py
- backend/.env.example

## 构建和测试

Android 改动后：
- 如果改了 build.gradle.kts，必须 Sync Project with Gradle Files
- 然后 Build > Make Project
- 再 Run 到设备

后端改动后：
- 必须重启 uvicorn

命令：
uvicorn main:app --host 0.0.0.0 --port 8000

## 当前下一步方向

下一步优先做 Settings：
- 回复字号可调
- AI 回复字体可配置
- 纸张背景可选
- 墨色可选
- 调试信息开关
- 设置持久化

不要做登录、数据库、云同步、支付。