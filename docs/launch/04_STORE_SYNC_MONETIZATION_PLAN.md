# 墨灵双商店发布、多端同步与收费方案 v1.0

更新时间：2026-07-25

## 1. 总原则

墨灵的目标是实际上架，不是长期停留在“邀请测试版”。

但商店审核存在不可压缩的外部流程，因此采用两条并行线：

```text
产品线：持续开发、部署、修复、形成正式版本
商店线：账号认证、测试轨、素材、备案、审核同步推进
```

等待审核不能成为停止开发的理由；继续开发也不能成为迟迟不提交的理由。

## 2. 发布顺序

### 2.1 第一优先：生产基础

先完成所有商店共同依赖：

- 稳定包名；
- 正式签名密钥；
- versionCode/versionName 规则；
- 生产 HTTPS 后端；
- 隐私政策 URL；
- 用户协议 URL；
- 支持和反馈页面；
- 数据删除说明；
- 正式图标、截图、应用介绍；
- APK 与 AAB 构建；
- 本地持久化；
- Crash 监控；
- DeepSeek 鉴权与预算。

### 2.2 Google Play

顺序：

1. 建立或核验开发者账号；
2. 创建应用并冻结包名；
3. 上传 AAB 到内部测试；
4. 同时完成商店资料、内容分级、数据安全表和隐私声明；
5. 如果是 2023-11-13 后创建的个人开发者账号，立即组织至少 12 名测试者连续加入封闭测试 14 天；
6. 满足条件后申请 production access；
7. 通过后提交生产发布；
8. 首发使用分阶段发布，先小比例再扩大。

Google 官方当前要求新个人账号可能需要 12 名测试者连续 14 天封闭测试。这是上架流程的一部分，不是额外的产品研究阶段。

官方资料：

- https://support.google.com/googleplay/android-developer/answer/14151465
- https://support.google.com/googleplay/android-developer/answer/9859152
- https://support.google.com/googleplay/android-developer/answer/9845334

### 2.3 华为 AppGallery 全球版

与 Google Play 并行：

1. 注册 HUAWEI ID；
2. 完成开发者实名认证；
3. 在 AppGallery Connect 创建 Android 应用；
4. 配置名称、语言、介绍、截图、分类、隐私链接和分发国家；
5. 上传 APK 或 App Bundle；
6. 使用华为云测试/云调试检查常见设备；
7. 提交审核；
8. 上架后使用分阶段发布和运营分析。

华为官方支持 Android 应用全球分发，并提供 APK/App Bundle、云测试、崩溃、性能和分阶段发布能力。

官方资料：

- https://developer.huawei.com/consumer/cn/appgallery/
- https://developer.huawei.com/consumer/cn/appgallery/devstart/
- https://developer.huawei.com/consumer/cn/solution/agconnect/release

### 2.4 中国大陆华为版本

中国大陆版本单独建立合规轨，不阻塞 Google Play 和 AppGallery 全球其他地区版本。

原因：在中国境内提供互联网信息服务的 App 需要履行 APP 备案；华为上架流程也要求开发者关注备案、隐私声明和网络资源信息。

需要准备：

- 合适的主办主体；
- APP 备案；
- 域名、IP 和网络接入资源；
- 中国大陆隐私政策；
- 第三方 SDK 清单；
- DeepSeek 数据处理说明；
- 个人信息最小化；
- 用户查阅、删除、注销机制；
- 涉及跨境数据时的单独法律评估。

官方资料：

- https://www.gov.cn/zhengce/zhengceku/202308/content_6897341.htm
- https://developer.huawei.com/consumer/cn/notice/detail/?id=9006158606455316025

在大陆合规条件未完成前，可以先发布非中国大陆地区版本，但不能假装已经完成大陆上架。

## 3. 包体与版本策略

### 3.1 包名

当前：

```text
com.moling.livingnotebook
```

正式提交前必须确认长期使用。包名一旦进入商店，不应再修改。

### 3.2 构建产物

- Google Play：AAB；
- 华为 AppGallery：优先 AAB 或平台支持的正式 APK；
- 官网/受控分发：签名 APK；
- 所有渠道必须使用同一应用签名体系或明确的渠道签名管理，不得临时生成密钥。

### 3.3 版本编号

建议：

```text
v0.8.0  versionCode 800
v0.9.0  versionCode 900
v1.0.0  versionCode 1000
v1.0.1  versionCode 1001
v1.1.0  versionCode 1100
```

每次上传任何商店都必须递增 versionCode。

### 3.4 渠道差异

尽量保持单一代码库，仅通过 product flavor 处理：

```text
playRelease
huaweiRelease
directRelease
debug
```

渠道只允许差异化：

- 商店支付 SDK；
- Crash/分析服务；
- 更新入口；
- 必要的渠道配置。

产品逻辑、人格、同步协议和数据格式必须一致。

## 4. 华为设备与手写识别

当前 ML Kit Digital Ink 模型可能依赖 Google Play Services 下载，在缺少 GMS 的华为设备上存在失败风险。

首发必须做：

1. 启动时检查识别模型是否可用；
2. 下载失败给出明确状态；
3. 记录设备型号、系统和失败类别，但不记录笔记；
4. 华为商店提交前在无 GMS 设备上实测；
5. 不能用 Vision OCR 长期掩盖本地识别不兼容。

技术路线：

- v0.8：先确认现有华为测试机是否可稳定使用；
- v0.9：若 ML Kit 在目标华为设备不可用，抽象 `HandwritingRecognitionProvider`；
- v1.0 前至少提供一个华为可用识别路径，或限制华为首发支持设备并在商店页面明确；
- 原生 HarmonyOS 版本不是 Android v1.0 的阻塞项，另立后续迁移项目。

## 5. 多端互联

### 5.1 “多端”的第一阶段定义

首发多端不是同时开发 Android、iOS、Web 三套编辑器。

v1.0 的多端目标是：

- 同一 Android App 可运行于平板和手机；
- 用户登录后，账户、设置、文本笔记、AI 回应和记忆可以同步；
- 原始笔迹按页面同步，但允许延迟上传；
- 未来 iOS/Web 使用同一后端协议。

### 5.2 本地优先模型

```text
用户写入
→ 立即保存本地数据库
→ UI 直接读取本地数据
→ 后台生成同步任务
→ 网络恢复后增量同步
```

云端失败不能阻止写字。

### 5.3 数据对象

```text
User
Device
Notebook
Page
StrokeBlob
RecognizedText
AIReply
Memory
Setting
SyncOperation
Entitlement
```

每个可同步对象至少包含：

```text
id
user_id
revision
updated_at
deleted_at
device_id
sync_status
```

### 5.4 冲突处理

- 设置类：最新明确更新时间优先；
- 笔记类：不静默覆盖，冲突时保留两个版本；
- 删除：使用 tombstone 同步；
- 记忆：新事实不能直接覆盖旧事实，旧记录标记 superseded；
- 同一页面多设备同时编辑：v1.0 不做实时协作。

### 5.5 加密和隐私

- 传输全程 HTTPS；
- 服务端数据库加密；
- 高敏感记忆字段单独加密；
- 图片和笔迹对象使用短期签名 URL；
- 生产日志不含正文；
- 用户可导出、删除和注销；
- 未登录用户的数据仅在本地。

端到端加密可以作为后续增强，但首发必须先完成可靠的数据隔离、传输加密和删除机制。

## 6. 账户体系

### 6.1 首发登录

首发不应建设复杂社交账号系统。建议支持：

- 邮箱验证码；
- Google 登录（Google Play 渠道）；
- 华为账号登录（华为渠道，可后置到华为审核需要时）；
- 匿名本地模式。

所有登录方式最终映射到统一 `user_id`。

### 6.2 账户合并

同一用户可能先用 Google 购买，后在华为设备登录。服务端必须支持：

- 登录方式绑定；
- 账户合并审核；
- entitlement 跟随用户账户，而不是只跟设备；
- 防止同一订单重复入账。

## 7. 收费设计

### 7.1 收费原则

DeepSeek 模型成本很低，因此不能按 Token 转售，也不应让用户看到复杂的模型计费。

用户付费购买的是：

- 持续、可靠的 AI 回应；
- 老g式长期记忆；
- 多端同步；
- 深度回应；
- 高级纸张、字体、墨色和导出；
- 更高的数据保留和服务保障。

### 7.2 免费层

建议首发：

- 本地手写和本地保存永久免费；
- 基础纸张与字体；
- 每日有限 Flash 回应；
- 账户同步保留基础额度；
- 不因免费额度耗尽锁住用户自己的笔记。

### 7.3 Pro 层

建议权益：

- 更高 AI 回应额度；
- Deep 模式；
- 完整跨设备同步；
- 高级字体、纸张与墨色；
- 导出 PDF/图片/Markdown；
- 更完整长期记忆；
- 优先新功能。

首发定价建议先保留在远程配置中。初始候选：

- ¥18/月；
- ¥128/年；
- 早期创始用户可提供限量优惠，但不得承诺无法长期承担的终身无限 AI。

商店会按地区本地化价格，服务端只处理商品 ID 和权益，不硬编码货币金额。

### 7.4 首发收费时机

推荐：

- v1.0 正式上架时可以展示 Pro，但给予新用户一段完整体验期；
- v1.1 开放稳定同步；
- v1.2 正式启用订阅和 Deep 模式收费；
- 支付代码和 entitlement 在 v1.0 前建好，避免后续重构账户体系。

这不是“先不考虑收费”，而是先把收费地基放进首发架构，再在产品稳定后打开收款开关。

## 8. 双商店支付

### 8.1 渠道支付

- Google Play 渠道：Google Play Billing；
- 华为渠道：Huawei IAP；
- 官网暂不向 App 内导流规避商店规则；
- 服务端校验订单真实性、退款和撤销。

### 8.2 统一权益账本

```text
purchase provider
→ server verification
→ entitlement record
→ client fetches entitlement
```

Entitlement 字段：

```text
user_id
plan
source
product_id
original_transaction_id
starts_at
expires_at
status
last_verified_at
```

客户端不得仅凭本地购买成功回调永久解锁。

### 8.3 退款和过期

- 定期重新校验；
- 退款/撤销后更新权益；
- 到期后保留用户笔记，只关闭付费功能；
- 不因订阅失效删除云端数据；
- 给用户合理导出和降级窗口。

## 9. 商店素材

首发材料必须突出：

> 写下，它会以墨迹回应。

而不是泛泛宣传“AI 笔记”。

截图至少覆盖：

1. 空白纸面和真实手写；
2. 识别后墨迹浮现；
3. 老g式有判断的回应；
4. 纸张、字体和墨色设置；
5. 多端同步；
6. 隐私：本地优先、可删除。

商店文案避免：

- 医疗或心理治疗承诺；
- 夸大 AI 准确性；
- 暗示永远正确；
- 声称替代专业帮助；
- 使用用户私人笔记作为公开素材。

## 10. 发布清单

### 工程

- [ ] 生产 HTTPS
- [ ] DeepSeek V4
- [ ] 鉴权、限流、预算
- [ ] 本地数据库
- [ ] 账号与同步
- [ ] 签名 APK/AAB
- [ ] Crash 监控
- [ ] 版本更新
- [ ] 支付适配层

### 合规

- [ ] 隐私政策
- [ ] 用户协议
- [ ] 第三方 SDK 清单
- [ ] 数据安全表
- [ ] 账户删除
- [ ] 数据导出/删除
- [ ] 大陆 APP 备案轨
- [ ] DeepSeek 数据处理披露

### 商店

- [ ] Google 开发者账号
- [ ] Google 内部测试
- [ ] Google 封闭测试（如适用）
- [ ] 华为开发者实名认证
- [ ] AppGallery 应用创建
- [ ] 图标、截图、文案
- [ ] 内容分级
- [ ] 审核说明
- [ ] 分阶段发布

## 11. 上线顺序的最终裁决

最短且不牺牲正式上线目标的顺序是：

1. 立即建设生产后端和签名 v0.8；
2. 一旦 AAB 可用，马上开 Google 内部/封闭测试，让外部 14 天时钟开始；
3. 同时提交华为 AppGallery 全球版，不等 Google；
4. 开发 v0.9 的隐私、同步、稳定性和商店素材；
5. 哪个商店先通过，哪个先正式上线；
6. 中国大陆版按 APP 备案单独推进；
7. v1.0 上架后继续完成 v1.1 同步和 v1.2 收费，不再把“上线”当项目终点。
