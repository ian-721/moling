# Codex 首轮连续执行提示词

> 在 `I:\IAN\idea\Moling` 打开 Codex 新对话，完整粘贴以下内容。不要先开一个只讨论路线或只产出审计报告的对话。

---

# M0-A｜墨灵生产基线、DeepSeek V4 迁移与首个远程可运行版本

## 一、项目承接

仓库：`ian-721/moling`

本地路径：`I:\IAN\idea\Moling`

默认分支：`main`

在任何修改前，必须完整阅读：

1. `AGENTS.md`
2. `README.md`
3. `docs/launch/00_IDENTITY_AND_NAMING_BOUNDARY.md`
4. `docs/launch/01_MOLING_LAUNCH_MASTER_PLAN.md`
5. `docs/launch/02_OLD_G_PERSONA_AND_MEMORY_SPEC.md`
6. `docs/launch/03_DEEPSEEK_BACKEND_AND_COST_PLAN.md`
7. `docs/launch/04_STORE_SYNC_MONETIZATION_PLAN.md`

以上文件是本轮最高优先级产品与工程约束。旧开发资料与其冲突时，以 `AGENTS.md` 和 `docs/launch/` 为准。

## 二、冻结目标

墨灵已经决定正式上线，不允许把本轮做成只输出审计报告的研究任务。

本轮必须同时完成：

1. 全新环境可运行性核验；
2. 后端从 OpenAI Responses API 迁移到 DeepSeek V4；
3. 生产/开发环境配置分离；
4. 基础安全、成本和日志边界；
5. 人格 Prompt 拆分与命名隔离基础；
6. 必要测试与最小 CI；
7. 形成可继续部署和构建 v0.8 的代码基线。

审计只是开工动作，不是最终交付物。遇到本轮范围内可修复的问题，直接修复并测试。

## 三、模型决策

生产默认供应商：DeepSeek。

必须使用当前规划模型名：

- 默认：`deepseek-v4-flash`
- 深度：`deepseek-v4-pro`

禁止在新代码中使用：

- `deepseek-chat`
- `deepseek-reasoner`

默认回应关闭思考模式；深度模式保留服务端配置能力，但本轮不需要在客户端开放。

使用 OpenAI-compatible Chat Completions API：

```text
https://api.deepseek.com
```

若实际 API 文档或账号能力与规划文件存在可验证冲突，先记录证据，采用兼容配置完成适配，不得自行退回 OpenAI 作为生产默认方案。

## 四、强制产品、身份与隐私边界

1. 产品与 App 品牌固定为“墨灵 / Moling”。
2. 内部角色名称由每个用户自行设置，字段为 `assistant_name`；新用户安全默认值可为“墨灵”。
3. 用户可以把自己的角色命名为“老g”或其他合法名称，但该名称只绑定当前 `user_id` 或匿名 `device_profile_id`。
4. 名称相同绝不代表身份、关系或记忆相同；严禁按 `assistant_name` 查询、关联或共享记忆。
5. 登出、切换账户、配置读取失败或缓存失效时，宁可回退默认“墨灵”，也不能沿用上一个用户的名称。
6. 当前角色自称使用当前用户的 `assistant_name`，但不得声称自己是 ChatGPT、OpenAI、DeepSeek、现实人物或另一平台中的助手实例。
7. 不得把产品改造成聊天气泡、聊天列表或普通 AI 对话 App。
8. 保持主链路：strokes → 本地保存与识别 → 后端回应 → 墨迹浮现。
9. Vision OCR 只允许开发 fallback，生产默认关闭。
10. 识别、网络、模型或同步失败时必须保留/恢复用户原始笔迹。
11. API Key、签名密钥和私人 memory seed 不得进入 Android、Git、日志、测试快照或注释。
12. 赵焱阳的私人记忆不得写入公共 Prompt、公开安装包或 Git；本轮只建立隔离接口和数据结构，不导入真实私有记忆。
13. 不做与本轮无关的大规模重构。
14. 不修改 Gradle Wrapper，除非真实构建阻塞证明必须修改，并在交付中说明原因。

## 五、本轮执行顺序

### A. Git 与基线核验

- 检查工作树、当前分支、远端、默认分支和最新 `origin/main`；
- 在修改前执行实时 `git fetch origin`；
- 检查仓库中是否存在密钥、签名文件、真实 `.env` 或私人记忆；
- 验证后端依赖安装、启动和 `/healthz`；
- 验证 Android Gradle Sync、测试和 Debug build；
- 记录真实阻塞，但本轮可修复的问题必须直接修复；
- 不因缺少真实 DeepSeek Key 而停止：使用 fake/mock provider 完成结构和测试。

### B. 后端结构

将后端整理为最小清晰结构，不做无关微服务化。建议：

```text
backend/
  app/
    providers/
      base.py
      deepseek.py
    services/
      reply_service.py
      prompt_service.py
      usage_service.py
    models/
    prompts/
    config.py
  tests/
  main.py
```

允许按现状调整，但必须建立 `ModelProvider` 抽象，业务路由不能直接绑定 DeepSeek SDK。

### C. DeepSeek Provider

实现：

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_FLASH_MODEL=deepseek-v4-flash`
- `DEEPSEEK_PRO_MODEL=deepseek-v4-pro`
- OpenAI-compatible Chat Completions；
- JSON Output；
- `max_tokens`；
- 普通模式关闭思考；
- 匿名 provider `user_id` 支持，但该值不得包含姓名、邮箱或笔记内容；
- 超时；
- 最多一次受控重试；
- 400/401/402/422/429/500/503 错误映射；
- 空 content 和非法 JSON 处理；
- Flash 默认、Pro 配置预留；
- input/output/cache token 与估算成本结构预留。

### D. 人格 Prompt 与角色命名

本轮不完成全部长期记忆系统，但必须：

- 将当前巨大内联 Prompt 从 `main.py` 中拆出；
- 建立版本化 persona、mode router、safety、output schema 文件；
- 按 `02_OLD_G_PERSONA_AND_MEMORY_SPEC.md` 提炼人格机制；“老g”只作为内部工程来源代号，不硬编码成公共默认角色名；
- Prompt 中通过可信服务端变量注入当前用户的 `assistant_name`；
- `assistant_name` 缺失或非法时回退“墨灵”；
- 不允许客户端通过普通笔记文本覆盖系统身份变量；
- 输出结构至少包含 `reply`、`mode`、`safety_level`、`should_ask`；
- 固定公共前缀与动态用户上下文分离；
- 建立人格回归测试目录和最小样例；
- 不把赵焱阳的私人记忆写进 Git。

### E. 用户隔离基础

本轮至少建立可扩展的数据/接口边界：

```text
user_id 或 device_profile_id
assistant_name
provider_user_id
request_id
```

要求：

- 所有名称读取都必须带当前用户或本地 profile 作用域；
- 不得出现按名称读取记忆的代码路径；
- 切换账户后旧名称和旧上下文不能残留；
- 暂未建设数据库时，也要用接口、模型和测试固定该边界；
- 至少增加两个用户设置相同名称但数据完全隔离的测试。

### F. 隐私与日志

- 生产环境不打印 `recognizedText`、`recentContext`、完整 AI 回复、私人记忆或图片；
- 图片保存功能只允许 debug 显式开启；
- 生产默认禁止图片落盘；
- 日志只记录 request id、匿名用户、模型、耗时、状态、Token usage 和错误类别；
- 错误响应不得泄露供应商异常全文或 Secret；
- 日志中的用户标识必须匿名化。

### G. Android 环境配置

- 移除单一局域网硬编码生产方式；
- 使用 Debug/Release BuildConfig、product flavor 或等价方式；
- Debug 可访问本地 HTTP；
- Release 必须使用 HTTPS；
- Release 不允许 `usesCleartextTraffic=true`；
- 不在普通设置页暴露任意后端 URL；
- 为未来 `assistant_name` 本地保存预留清晰配置模型，但本轮不必完成完整设置 UI。

### H. 后端环境配置

- 更新 `.env.example`；
- 增加环境配置校验；
- 缺少生产 Secret 时给出安全、明确的启动错误；
- 测试使用 fake provider，不依赖真实网络；
- 真实 DeepSeek Key 只由部署 Secret 注入。

### I. 测试

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
- 日志不出现正文；
- `assistant_name` 正常注入；
- 名称缺失安全回退；
- 两个用户使用相同名称仍完全隔离；
- 不能按名称读取记忆或用户资料。

Android 至少覆盖或验证：

- Debug/Release base URL；
- Release 禁止明文；
- 错误映射；
- 当前 Debug build 成功。

### J. 文档与 CI

- 根据真实代码更新 README；
- 更新 `.env.example` 和本地运行文档；
- 增加最小 CI：后端测试 + Android Debug build/test + secret scan；
- 在 CI 或测试中守卫生产代码不得重新出现旧模型名；
- 记录 DeepSeek 配置、构建命令和已知外部阻塞；
- 不写虚假“已部署”“已上架”或“已真机验证”状态。

## 六、完成标准

本轮只有同时满足以下条件才算完成：

1. 代码中生产默认模型已迁移至 DeepSeek V4 规划；
2. OpenAI Responses 不再是生产默认主路径；
3. Prompt 已从 `main.py` 拆出并版本化；
4. 产品品牌与用户自定义角色名已在代码结构中分离；
5. `assistant_name` 按用户或匿名 profile 隔离，且存在同名不同用户隔离测试；
6. 不存在按角色名称读取或共享记忆的路径；
7. 用户正文不会进入生产日志；
8. Vision 图片不会在生产落盘；
9. Android Debug/Release 后端配置分离；
10. Release 明文 HTTP 被禁用；
11. 后端测试通过；
12. Android Debug build 通过，或给出可复现且无法在本轮环境解决的外部阻塞证据；
13. README、`.env.example` 与实际代码一致；
14. 有实际代码提交，不是只有报告。

## 七、Git 与交付

- 新建分支：`launch/m0a-deepseek-production-baseline`
- 不直接修改 `main`；
- 保持提交范围清晰；
- 不改无关文件；
- 完成后运行全部相关测试；
- 提交并推送；
- 创建 Draft PR；
- PR 标题：`M0-A: migrate Moling to DeepSeek V4 production baseline`

最终输出必须包括：

1. 真实基线发现；
2. 修改文件列表；
3. 架构变化；
4. 身份命名与用户隔离实现；
5. 测试和构建结果；
6. 未完成阻塞；
7. 分支、commit、PR；
8. 下一轮 M0-B 的精确范围。

不要重新询问是否使用 DeepSeek、是否正式上线、产品是否叫墨灵、角色名称是否允许用户自定义、是否需要严格用户隔离。这些决策已经冻结。

---
