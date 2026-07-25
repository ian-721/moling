# 墨灵 DeepSeek 后端与成本方案 v1.0

更新时间：2026-07-25

## 1. 当前官方基线

DeepSeek 已在 2026-04-24 发布 V4 API。新代码必须使用：

- `deepseek-v4-flash`
- `deepseek-v4-pro`

旧模型名 `deepseek-chat` 与 `deepseek-reasoner` 已于北京时间 2026-07-24 23:59 弃用，不得作为新架构配置。

官方基线：

- OpenAI-compatible base URL：`https://api.deepseek.com`
- Flash：缓存未命中输入 1元/百万 Token，缓存命中输入 0.02元/百万 Token，输出 2元/百万 Token；
- Pro：缓存未命中输入 3元/百万 Token，缓存命中输入 0.025元/百万 Token，输出 6元/百万 Token；
- 两者支持 JSON Output；
- 上下文硬盘缓存默认开启；
- 可通过匿名 `user_id` 做缓存、内容安全和调度隔离。

官方资料：

- https://api-docs.deepseek.com/zh-cn/
- https://api-docs.deepseek.com/zh-cn/quick_start/pricing
- https://api-docs.deepseek.com/zh-cn/guides/json_mode/
- https://api-docs.deepseek.com/zh-cn/guides/kv_cache/
- https://api-docs.deepseek.com/zh-cn/quick_start/rate_limit
- https://api-docs.deepseek.com/zh-cn/guides/thinking_mode

## 2. 模型路由

### 2.1 默认回应

```text
model = deepseek-v4-flash
thinking = disabled
max_tokens = 420
response_format = json_object
```

用于：

- 日常笔记；
- 情绪照见；
- 普通判断；
- 小型行动建议；
- 轻松陪伴。

Flash 是生产默认模型，不应因为用户内容略长就自动切 Pro。

### 2.2 深度回应

```text
model = deepseek-v4-pro
thinking = enabled
reasoning_effort = high
max_tokens = 800
response_format = json_object
```

仅用于：

- 用户主动点击“深度回应”；
- 明确的复杂决策；
- 需要跨多个长期目标权衡；
- Flash 连续两次无法生成有效结构化输出；
- 订阅权益允许的高级调用。

不得把“用户情绪强烈”自动等同于“使用更贵模型”。

### 2.3 降级

- Pro 429/503：降级到 Flash，并向客户端返回 `degraded=true`；
- Flash 429/503：短退避后只重试一次；
- 402：立即停止调用并触发预算告警；
- 非法 JSON/空 content：同模型使用简化 Prompt 重试一次；
- 第二次失败：返回本地友好提示，不继续循环烧费。

## 3. 供应商适配层

当前代码直接使用 OpenAI Responses API。迁移时不得把 DeepSeek 调用散落在路由函数中。

建议结构：

```text
backend/
  app/
    providers/
      base.py
      deepseek.py
      openai_fallback.py   # 默认关闭，仅保留紧急适配能力
    services/
      reply_service.py
      prompt_service.py
      memory_service.py
      usage_service.py
    models/
      reply.py
      usage.py
```

接口：

```python
class ModelProvider(Protocol):
    async def generate_reply(self, request: ModelRequest) -> ModelResponse:
        ...
```

业务层只关心：

- 最终回复；
- mode；
- usage；
- provider/model；
- degraded；
- safety_level；
- prompt_version。

## 4. 环境变量

```env
MODEL_PROVIDER=deepseek
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_FLASH_MODEL=deepseek-v4-flash
DEEPSEEK_PRO_MODEL=deepseek-v4-pro
DEEPSEEK_DEFAULT_MAX_TOKENS=420
DEEPSEEK_DEEP_MAX_TOKENS=800
DEEPSEEK_TIMEOUT_SECONDS=40
DEEPSEEK_RETRY_COUNT=1
DAILY_MODEL_BUDGET_CNY=20
MONTHLY_MODEL_BUDGET_CNY=300
```

生产环境变量只存在部署平台的 Secret 管理中。

## 5. Prompt 与缓存

DeepSeek 上下文缓存按前缀匹配。为获得高命中率，必须让公共前缀稳定：

```text
[固定]
Persona Core
Mode Router
Safety Rules
JSON Schema

[动态]
User Profile
Relevant Memories
Recent Context
Current Handwriting
```

规则：

- 固定 Prompt 文件有版本号；
- 不在固定 Prompt 前部插入时间、requestId 等动态值；
- 私有记忆放在固定前缀之后；
- 同一 Prompt 版本保持完全一致；
- 每次记录缓存命中 Token，观察是否真的产生收益。

## 6. JSON 输出

请求中必须设置：

```python
response_format={"type": "json_object"}
```

Prompt 中必须明确包含 `json` 字样和输出样例。

目标结构：

```json
{
  "reply": "",
  "mode": "companion | mirror | judgment | root_cause | decision | execution | grounding | challenge | quiet | safety",
  "safety_level": "normal | elevated | critical",
  "memory_candidates": [],
  "should_ask": false
}
```

服务端必须做二次校验：

- `reply` 非空；
- 字符长度上限；
- `mode` 为枚举；
- `memory_candidates` 数量和长度受限；
- 高风险内容不允许普通 mode；
- 解析失败进入一次简化重试。

DeepSeek 官方说明 JSON Output 偶尔可能返回空 content，因此空结果必须是显式错误分支，不能当作正常空回复。

## 7. 成本估算

### 7.1 Flash 普通回应

假设单次：

- 输入 2,500 Token；
- 输出 300 Token；
- 全部输入未命中缓存。

成本约：

```text
输入：2,500 / 1,000,000 × 1元 = 0.0025元
输出：300 / 1,000,000 × 2元 = 0.0006元
合计：约 0.0031元/次
10,000 次：约 31元
```

若固定 Prompt 大量命中缓存，实际成本会进一步下降。

### 7.2 Pro 深度回应

同样按输入 2,500、输出 300 Token，全部输入未命中：

```text
输入：2,500 / 1,000,000 × 3元 = 0.0075元
输出：300 / 1,000,000 × 6元 = 0.0018元
合计：约 0.0093元/次
10,000 次：约 93元
```

结论：DeepSeek 的纯模型成本不是墨灵首发的主要商业障碍。真正需要控制的是：

- 被盗用后的无限请求；
- 重试循环；
- 无限制长上下文；
- 无限制输出；
- Vision 图片调用；
- 服务端和同步基础设施成本。

## 8. 配额与预算

### 免费用户

初始建议：

- 每日 10 次 Flash；
- 每月 120 次；
- 不含或仅体验 1–3 次 Pro；
- 单次输入上限 3,000 中文字符；
- recentContext 有独立 Token 上限。

### Pro 用户

- 每日较高软上限；
- 每月公平使用上限；
- Deep 模式独立配额；
- 超过正常范围时限速，而不是继续无限调用。

### 全局预算

- 50%：记录；
- 70%：告警；
- 85%：关闭非必要 Pro 自动路由；
- 95%：免费用户降到较低日额度；
- 100%：停止新模型调用，保留本地笔记功能。

模型余额耗尽不能让 App 无法打开或导致笔记丢失。

## 9. 鉴权与 `user_id`

客户端不得直接持有 DeepSeek Key。

请求链：

```text
Android Access Token
→ Moling Backend
→ 校验账户/设备和 entitlement
→ 生成匿名 provider_user_id
→ DeepSeek API
```

`provider_user_id`：

- 只能是随机或哈希标识；
- 不包含姓名、邮箱、手机号或笔记内容；
- 满足 DeepSeek 的字符格式要求；
- 用户注销后解除映射。

## 10. 超时与重试

- 客户端总等待目标：普通回应尽量控制在 30 秒内；
- 服务端调用超时：约 35–40 秒；
- 普通 Flash 默认关闭思考，避免不必要延迟；
- 只对网络错误、429、500、503 做一次受控重试；
- 400/401/402/422 不自动重试；
- 每个请求携带幂等键；
- 客户端新请求开始时，旧请求即使返回也不得覆盖新页面。

## 11. 日志和观测

允许记录：

- request_id；
- 匿名 user/device id；
- provider/model；
- input/output/cache tokens；
- 估算人民币成本；
- 时延；
- HTTP 状态；
- prompt_version；
- mode；
- degraded；
- safety_level。

禁止记录：

- 原始笔记正文；
- recentContext；
- 私人记忆内容；
- 完整 AI 回应；
- 上传图片；
- API Key。

调试正文日志必须通过显式开发开关启用，且生产环境强制关闭。

## 12. Vision OCR

生产默认关闭图片上传和服务器图片落盘。

后续确需 Vision fallback 时：

- 单独用户授权；
- 单独接口和配额；
- 图片只在内存中处理；
- 请求完成即释放；
- 不和普通文本调用混在同一预算；
- 隐私政策明确披露。

首发优先解决本地识别和无 GMS 设备路径，不依赖 Vision 掩盖识别问题。

## 13. 测试

必须覆盖：

- Flash 正常 JSON；
- Pro 正常 JSON；
- 空 content；
- 非法 JSON；
- 400/401/402/422/429/500/503；
- 超时；
- 受控重试次数；
- 配额耗尽；
- 全局预算耗尽；
- 用户隔离；
- 日志中无正文；
- Prompt 缓存前缀稳定；
- 旧模型名不再出现。

## 14. 迁移完成定义

1. OpenAI 不再是生产默认供应商；
2. 后端使用 DeepSeek V4 新模型名；
3. Flash/Pro 路由、JSON 校验和降级成立；
4. 单请求成本可记录；
5. 无鉴权不能调用模型；
6. 预算耗尽不影响本地笔记；
7. 日志不泄露用户正文；
8. 自动测试覆盖主要故障路径。
