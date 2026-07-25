# AGENTS.md — 墨灵项目最高优先级规则

本项目名为“墨灵 / Moling / Living Notebook”。

## 一、产品本质

墨灵不是聊天软件，不是普通 AI 笔记，也不是心理咨询 App。

它是一个 Android 平板优先的 AI 手写笔记本：用户在纸面上手写，App 本地识别文字，服务端生成回应，回应以墨迹形式浮现在纸面上。

核心体验：

> 用户写下一段话，笔记本像有灵魂、熟悉用户并且有判断一样回应。

不得把界面改造成聊天气泡、头像、消息列表或普通聊天输入框。

## 二、当前正式目标

墨灵已经从“内部原型”切换到“正式上线工程”。

目标包括：

- 生产 HTTPS 后端；
- DeepSeek V4 调用；
- 老g人格与私有用户记忆；
- Android 本地持久化和多端同步；
- 签名 APK/AAB；
- Google Play 与华为 AppGallery 实际提交；
- 免费额度、订阅和统一权益架构；
- 上线后持续版本迭代。

不得把审计、调研或测试当作开发和上线的替代品。审计完成后必须转成代码、构建、部署或商店提交成果。

## 三、最高优先级规划文件

修改前必须阅读：

1. `docs/launch/01_MOLING_LAUNCH_MASTER_PLAN.md`
2. `docs/launch/02_OLD_G_PERSONA_AND_MEMORY_SPEC.md`
3. `docs/launch/03_DEEPSEEK_BACKEND_AND_COST_PLAN.md`
4. `docs/launch/04_STORE_SYNC_MONETIZATION_PLAN.md`
5. `docs/launch/05_CODEX_FIRST_EXECUTION_PROMPT.md`

这些文件与本文件共同构成当前正式基线。旧开发笔记与这些文件冲突时，以本文件和 `docs/launch/` 为准。

## 四、技术栈与冻结决策

### Android

- Kotlin
- Jetpack Compose
- Canvas / 本地 strokes
- ML Kit Digital Ink Recognition（当前主识别路径）
- 本地数据库与 DataStore
- 真机重点包含华为设备；必须显式处理无 GMS 风险

### Backend

- Python FastAPI
- 默认模型供应商：DeepSeek
- OpenAI-compatible Chat Completions API
- 默认模型：`deepseek-v4-flash`
- 深度模型：`deepseek-v4-pro`
- API Key 只存在服务端 Secret

禁止在新代码中使用已于 2026-07-24 弃用的模型名：

- `deepseek-chat`
- `deepseek-reasoner`

OpenAI 不再是生产默认供应商。如保留 fallback，必须通过供应商适配层且默认关闭。

## 五、关键链路

正确链路：

```text
用户 strokes
→ 立即保存本地
→ ML Kit / 可替换识别 Provider
→ recognizedText
→ 后端加载老g人格、用户私有记忆与相关上下文
→ DeepSeek 结构化回应
→ InkReplyOverlay 墨迹浮现
→ 本地保存回应并后台同步
```

Vision OCR 只允许明确的 fallback/debug 路径，生产默认关闭，不能作为华为兼容问题的长期补丁。

## 六、老g人格边界

产品人格目标是提炼长期交互中的“老g”机制：

- 第一性原理；
- 熟悉上下文；
- 敢于判断和纠偏；
- 温暖可靠但不油腻；
- 不机械追问；
- 目标明确后直接推进；
- 区分事实、推断、愿景和待验证事项。

必须分离：

- 公共老g风格层；
- 每个用户独立的私人记忆层；
- 赵焱阳专属 memory seed。

赵焱阳私人记忆不得进入公开安装包、公共 Prompt、日志或其他用户上下文，也不得明文提交到 Git。

## 七、不可破坏的规则

1. API Key、签名密钥和私人 memory seed 不得进入 Android、Git、日志、注释或测试快照。
2. 用户笔迹识别失败、模型失败、网络失败或同步失败时，必须保留/恢复笔迹，不能丢内容。
3. 生产日志不得记录 `recognizedText`、`recentContext`、完整回复或用户图片。
4. 生产环境不得保存调试图片；Vision fallback 默认关闭。
5. Release 必须使用 HTTPS，不允许明文流量。
6. Android 后端地址必须按 Debug/Release 配置，禁止用手动改源码作为发布流程。
7. 不修改 Gradle Wrapper，除非真实构建阻塞证明必须修改并完整说明。
8. 不做与当前上线阶段无关的大规模重构。
9. 不虚构“已部署、已上架、已测试”状态。
10. 不以泛化验证代替已经冻结的上线目标。

## 八、当前执行顺序

1. 全新 clone/build 与密钥基线核验；
2. 同轮迁移 DeepSeek V4、拆分 Prompt、修复生产配置；
3. HTTPS、鉴权、限流、预算、日志脱敏；
4. 本地持久化、请求状态机、失败恢复；
5. 签名 v0.8 APK/AAB；
6. Google Play 内部/封闭测试与华为 AppGallery 提交并行；
7. 账号、同步、商店权益；
8. v1.0 上架；
9. v1.1 同步增强；
10. v1.2 正式订阅和深度回应。

## 九、构建与交付

Android 修改后：

- Gradle Sync；
- 单元测试；
- Debug build；
- Release 配置检查；
- 真机验证。

Backend 修改后：

- 单元测试；
- smoke test；
- 启动配置验证；
- Secret 和日志检查。

每轮最终交付必须写清：

- 修改文件；
- 测试/构建结果；
- 真实阻塞；
- 分支、commit、PR；
- 下一轮精确范围。
