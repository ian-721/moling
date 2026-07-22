# PROJECT_STATE.md — 墨灵当前状态

## 已完成

### v0.1
- Android Compose 项目搭建
- 纸面 Canvas
- 手写 stroke 捕捉
- 清空 / 撤销 / mock 回应

### v0.2
- AI 回复逐字浮现
- 回复残影
- 初步墨迹动画

### v0.3
- FastAPI 后端
- Android 调用本地后端
- OpenAI API 接入
- imageBase64 上传
- 后端返回 recognizedText / aiReply / responseMode

### v0.4
- 后端拆成 OCR Stage 和 Reply Stage
- 墨灵 Prompt 强化
- 用户笔迹吸墨交互
- turnHistory / recentContext

### v0.4.1
- 墨灵 Prompt v2
- 回复更长、更冷静、更像思考系统
- 默认模型建议 gpt-5.6-terra

### v0.5
- 接入 ML Kit Digital Ink Recognition
- ML Kit 作为主识别路径
- OpenAI Vision OCR 降级为 fallback/debug
- 后端支持 recognizedText 主路径，收到 recognizedText 时跳过 OCR Stage
- InkReplyOverlay 替代 AiReplyOverlay
- AI 回复有更明显的墨迹浮现/残影动画

## 重要问题和结论

### 1. OpenAI Vision OCR 不适合作为主识别路径
它会对中文手写严重幻读。例如用户写：
“担心我的事业不能做成功。”

它曾识别成：
“我呢—内心的柔软是不够么
被欺负。”

所以 Vision OCR 不能做默认主路径。

### 2. ML Kit 才是主识别路径
应使用 stroke 数据构造 Ink，再用 Digital Ink Recognition 识别文字。

中文模型 tag：
- zh-Hani-CN
- zh-Hani

不要使用 zh-Hans，因为 ML Kit Digital Ink 没有 zh-Hans 模型。

### 3. 华为 Pad 可能无 GMS
HUAWEI MRO-W00 可能无法下载 ML Kit 模型。
这不是代码一定错误，而是设备生态限制。

### 4. AI 回复不能一直追问
之前墨灵每次都追问，体验很烦。
现在方向是：
- 有时判断
- 有时指出矛盾
- 有时给小行动
- 有时安静停住
- 最多一个问题，不要每次问题结尾

### 5. 字迹感不足
当前 InkReplyOverlay 仍可能像系统字体。
真正手写字迹需要用户放入授权字体文件：

moling-android/app/src/main/res/font/moling_hand.ttf

后续 Settings 需要允许用户调整：
- 字体
- 字号
- 背景
- 墨色
- 动画速度
- 残影强度