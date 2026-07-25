# Codex 首轮连续执行提示词

> Codex 额度恢复后，在 `I:\IAN\idea\Moling` 打开新对话，完整粘贴以下内容。不要先开一个只讨论路线的对话。

---

# M0-A｜墨灵生产基线、DeepSeek V4 迁移与首个远程可运行版本

## 一、项目承接

仓库：`ian-721/moling`

本地路径：`I:\IAN\idea\Moling`

默认分支：`main`

在任何修改前，必须完整阅读：

1. `AGENTS.md`
2. `README.md`
3. `docs/launch/01_MOLING_LAUNCH_MASTER_PLAN.md`
4. `docs/launch/02_OLD_G_PERSONA_AND_MEMORY_SPEC.md`
5. `docs/launch/03_DEEPSEEK_BACKEND_AND_COST_PLAN.md`
6. `docs/launch/04_STORE_SYNC_MONETIZATION_PLAN.md`

以上文件是本轮最高优先级产品与工程约束。

## 二、冻结目标

墨灵已经决定正式上线，不允许把本轮做成只输出审计报告的研究任务。

本轮必须同时完成：

1. 全新环境可运行性核验；
2. 后端从 OpenAI Responses API 迁移到 DeepSeek V4；
3. 生产/开发环境配置分离；
4. 基础安全、成本和日志边界；
5. 必要测试；
6. 形成可继续部署和构建 v0.8 的代码基线。

审计只是开工动作，不是最终交付物。

## 三、模型决策

生产默认供应商：DeepSeek。

必须使用当前模型名：

- 默认：`deepseek-v4-flash`
- 深度：`deepseek-v4-pro`

禁止使用已于 2026-07-24 弃用的：

- `deepseek-chat`
- `deepseek-reasoner`

默认回应关闭思考模式；深度模式保留配置能力但本轮不需要在客户端开放。

使用 OpenAI-compatible Chat Completions API：

```text
https://api.deepseek.com
```

## 四、强制产品边界

1. 不得把产品改造成聊天气泡、聊天列表或普通 AI 对话 App。
2. 保持主链路：strokes → 本地识别 → 后端回应 → 墨迹浮现。
3. Vision OCR 只允许开发 fallback，生产默认关闭。
4. 识别或模型失败时必须保留/恢复用户原始笔迹。
5. API Key 不得进入 Android、Git、日志、测试快照或注释。
6. 不做与本轮无关的大规模重构。
7. 不修改 Gradle Wrapper，除非已有构建事实证明必须修改，并在交付中说明原因。
8. 不提交真实 API Key、签名密钥或个人记忆 seed。

## 五、本轮执行顺序

### A. 基线核验

- 检查 git 状态、当前分支和远端；
- 检查仓库中是否存在密钥或敏感文件；
- 从现有仓库验证后端依赖安装、启动和 `/healthz`；
- 验证 Android Gradle Sync/测试/Debug build；
- 记录真实阻塞，但遇到可修复问题直接修复；
- 不因缺少真实 DeepSeek Key 而停止：使用 mock/fake provider 完成代码和测试。

### B. 后端结构

将后端整理为最小清晰结构，不做无关微服务化：

```text
backend/
  app/
    providers/
    services/
    models/
    config.py
  tests/
  main.py
```

允许根据现状调整，但必须建立 `ModelProvider` 抽象，业务路由不能直接绑定 DeepSeek SDK。

### C. DeepSeek Provider

实现：

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_FLASH_MODEL=deepseek-v4-flash`
- `DEEPSEEK_PRO_MODEL=deepseek-v4-pro`
- OpenAI SDK 指向 DeepSeek base URL；
- Chat Completions；
- JSON Output；
- `max_tokens`；
- 普通模式 `thinking=disabled`；
- 匿名 `user_id` 支持；
- 超时；
- 最多一次受控重试；
- 400/401/402/422/429/500/503 映射；
- 空 content 和非法 JSON 处理；
- Flash 默认、Pro 配置预留。

### D. 人格 Prompt

本轮不要完成全部长期记忆系统，但必须：

- 将当前巨大内联 Prompt 从 `main.py` 中拆出；
- 建立版本化 persona prompt 文件；
- 按 `02_OLD_G_PERSONA_AND_MEMORY_SPEC.md` 重写人格 v1；
- 输出结构至少包含 `reply`、`mode`、`safety_level`、`should_ask`；
- 固定公共前缀与动态上下文分离；
- 保留人格回归测试的目录和样例入口；
- 不把赵焱阳的私人记忆写进 Git。

### E. 隐私与日志

- 生产环境不打印 `recognizedText`、`recentContext`、完整 AI 回复；
- 图片保存功能只允许 debug 明确开启；
- 生产默认禁止图片落盘；
- 日志只记录 request id、匿名用户、模型、耗时、状态、Token usage 和错误类别；
- 错误响应不得泄露供应商异常全文或 Secret。

### F. 环境配置

Android：

- 移除单一局域网硬编码生产方式；
- 使用 Debug/Release BuildConfig 或等价方案；
- Debug 可访问本地 HTTP；
- Release 必须使用 HTTPS；
- Release 不允许 `usesCleartextTraffic=true`；
- 不在设置页暴露任意后端 URL。

后端：

- 更新 `.env.example`；
- 增加环境配置校验；
- 缺少生产 Secret 时给出安全、明确的启动错误；
- 测试使用 fake provider，不依赖真实网络。

### G. 测试

后端至少覆盖：

- `/healthz`；
- 文本主路径；
- 空请求；
- 缺少配置；
- 正常 JSON；
- 空 content；
- 非法 JSON；
- 402/429/503；
- 重试次数；
- Vision 生产关闭；
- 日志不出现正文。

Android 至少覆盖或验证：

- Debug/Release base URL；
- Release 禁止明文；
- 错误映射；
- 当前构建成功。

### H. 文档与 CI

- 根据真实代码更新 README；
- 增加最小 CI：后端测试 + Android Debug build/test + secret scan；
- 记录本地运行、环境变量、DeepSeek 配置和构建命令；
- 不写虚假“已部署”或“已上架”状态。

## 六、完成标准

本轮只有同时满足以下条件才算完成：

1. 代码中生产默认模型已是 DeepSeek V4；
2. 旧模型名和 OpenAI Responses 主路径已移除或不再作为默认；
3. Prompt 已从 `main.py` 拆出并版本化；
4. 用户正文不会进入生产日志；
5. Vision 图片不会在生产落盘；
6. Android Debug/Release 后端配置分离；
7. Release 明文 HTTP 被禁用；
8. 后端测试通过；
9. Android Debug build 通过，或给出可复现且无法在本轮环境解决的外部阻塞证据；
10. README 和 `.env.example` 与实际一致；
11. 有实际代码提交，不是只有报告。

## 七、Git 与交付

- 新建分支：`launch/m0a-deepseek-production-baseline`
- 保持提交范围清晰；
- 不改无关文件；
- 完成后运行测试；
- 提交并推送；
- 创建 Draft PR；
- PR 标题：`M0-A: migrate Moling to DeepSeek V4 production baseline`

最终输出必须包括：

1. 真实基线发现；
2. 修改文件列表；
3. 架构变化；
4. 测试和构建结果；
5. 未完成阻塞；
6. 分支、commit、PR；
7. 下一轮 M0-B 的精确范围。

不要重新询问是否使用 DeepSeek、是否上线、是否保留老g人格。这些决策已经冻结。

---
