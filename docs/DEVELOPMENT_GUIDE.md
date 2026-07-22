AI Living Notebook Android App 开发指南
0. 产品一句话
开发一个 Android 平板优先的 AI 手写笔记 App。用户在纸面风格页面上手写内容，点击“回应”后，App 识别用户写下的文字，发送给后端 AI Agent，AI 生成短句回应，并以“墨水浮现”的方式写回页面。
核心体验不是聊天，而是：
用户写下想法，笔记本像有灵魂一样回应、追问、帮助用户整理思考。
第一版目标不是正式上架，而是做出可在华为 Pad 上安装测试的本地 APK Demo。
________________________________________
1. 第一版 MVP 范围
只做最小闭环：
1.	Android App 启动后进入一页笔记页面。
2.	用户可以用手指或触控笔在页面上自由书写。
3.	App 记录笔迹 stroke。
4.	用户点击“回应”按钮。
5.	App 把当前页面截图或笔迹内容发给后端。
6.	后端调用 AI 大模型，识别/理解用户内容。
7.	AI 返回一句或几句短回应。
8.	App 在页面上用墨水浮现动画显示 AI 回复。
9.	本地保存当前页面内容和 AI 回复。
10.	下次打开 App 可以看到之前页面。
第一版不要做：
•	登录系统
•	订阅支付
•	Google Play 上架
•	多用户
•	社区
•	分享
•	复杂设置
•	多个 Agent
•	复杂模板市场
•	Web 搜索
•	日历/邮箱/文件联动
第一版只验证一个问题：
用户写完一句话后，看到笔记本回应，会不会想继续写下去？
________________________________________
2. 推荐技术栈
Android 客户端
使用：
Kotlin
Jetpack Compose
Canvas
PointerInput
Room
DataStore
OkHttp 或 Ktor Client
原因：
•	Kotlin 原生适合 Android 手写体验。
•	Jetpack Compose 开发速度快。
•	Canvas 可以自由绘制纸张、笔迹、AI 回复。
•	PointerInput 可以捕捉触控笔和手指轨迹。
•	Room 用于本地保存页面、笔迹、AI 回复。
•	DataStore 保存简单设置。
•	OkHttp/Ktor 负责请求后端。
后端
使用：
Python FastAPI
OpenAI / Claude / Gemini API 可切换
SQLite 或 PostgreSQL
第一版可以先用 SQLite。
后续再升级 PostgreSQL + pgvector + 对象存储。
AI 调用原则
大模型 API Key 绝对不能放在 Android App 里。
App 只能请求我们自己的后端。
后端再调用大模型 API。
________________________________________
3. App 信息架构
第一版只有 3 个核心页面：
1. NotebookPageScreen
主页面。显示一张纸，用户可以手写，AI 回复也显示在这张纸上。
包含：
•	顶部标题：Living Notebook
•	中间纸张 Canvas
•	底部按钮：
o	清空
o	撤销
o	回应
o	保存
2. HistoryScreen
简单历史页，展示保存过的页面。
第一版可以很简单，只显示：
•	创建时间
•	OCR 文本摘要
•	AI 回复摘要
3. SettingsScreen
第一版可以只放：
•	后端 API 地址
•	是否开启调试模式
•	清除本地数据
如果时间紧，HistoryScreen 和 SettingsScreen 可以先不做，只做主页面。
________________________________________
4. Android 项目结构建议
app/
  src/main/java/com/stormeye/livingnotebook/
    MainActivity.kt

    ui/
      NotebookPageScreen.kt
      HistoryScreen.kt
      SettingsScreen.kt
      components/
        PaperCanvas.kt
        InkToolbar.kt
        AiReplyOverlay.kt

    drawing/
      Stroke.kt
      StrokePoint.kt
      DrawingState.kt
      DrawingRepository.kt
      CanvasRenderer.kt

    data/
      local/
        AppDatabase.kt
        PageEntity.kt
        AiReplyEntity.kt
        PageDao.kt
      remote/
        ApiClient.kt
        NotebookApi.kt
        dto/
          NotebookRequest.kt
          NotebookResponse.kt

    domain/
      NotebookUseCase.kt
      GenerateReplyUseCase.kt
      SavePageUseCase.kt

    viewmodel/
      NotebookViewModel.kt
________________________________________
5. 数据结构
StrokePoint
data class StrokePoint(
    val x: Float,
    val y: Float,
    val timestamp: Long,
    val pressure: Float = 1f
)
Stroke
data class Stroke(
    val id: String,
    val points: List<StrokePoint>,
    val color: Long,
    val width: Float
)
PageEntity
@Entity(tableName = "pages")
data class PageEntity(
    @PrimaryKey val id: String,
    val createdAt: Long,
    val updatedAt: Long,
    val strokesJson: String,
    val ocrText: String?,
    val aiReply: String?
)
________________________________________
6. 核心交互流程
用户书写
1.	用户触摸 Canvas。
2.	App 捕捉 pointer down / move / up。
3.	每次移动生成 StrokePoint。
4.	一个完整落笔动作形成一个 Stroke。
5.	Canvas 实时绘制所有 strokes。
用户点击“回应”
1.	App 把当前 strokes 渲染成 bitmap。
2.	App 调用后端 /api/notebook/reply。
3.	请求内容包含：
o	pageId
o	strokesJson
o	pageImageBase64，可选
o	recentContext，可选
4.	后端调用大模型。
5.	后端返回：
o	recognizedText
o	aiReply
o	responseMode
6.	App 保存 recognizedText 和 aiReply。
7.	App 用墨水动画显示 aiReply。
________________________________________
7. 后端 API 设计
POST /api/notebook/reply
请求：
{
  "pageId": "page_001",
  "strokes": [],
  "imageBase64": "optional_base64_image",
  "recentContext": "optional recent notes summary"
}
返回：
{
  "recognizedText": "我最近有很多想法，但不知道该先做哪个。",
  "aiReply": "你不是缺方向。你缺的是一个能让现实给你反馈的顺序。先写下：哪件事能在 14 天内拿到第一个真实用户？",
  "responseMode": "clarify"
}
POST /api/notebook/summarize
后续版本再做。
第一版可以不实现。
________________________________________
8. AI Agent 设计
第一版只做一个 Agent：
Notebook Agent
它的职责：
1.	理解用户当前写下的内容。
2.	判断用户是在表达情绪、做决策、发散灵感，还是复盘问题。
3.	生成短、准、有延续性的回应。
4.	不要像客服。
5.	不要长篇大论。
6.	不要动不动列清单。
7.	优先追问本质问题。
System Prompt 初版
你是一本会回应用户的私人笔记本。

你不是聊天机器人，不是客服，不是心理医生。
你的任务不是给出大量建议，而是帮助用户看清自己正在写下的东西。

你的回应应该像从纸里浮现出来的话，而不是 AI 助手的回答。

回应原则：
1. 少而准。
2. 每次回应控制在 1 到 5 句话。
3. 优先指出用户文字背后的核心矛盾。
4. 如果用户情绪低落，先承接情绪，再给一个很小的问题。
5. 如果用户正在做决策，指出关键取舍。
6. 如果用户在空想，温和地把他拉回可验证的下一步。
7. 不要泛泛鼓励。
8. 不要输出长清单。
9. 不要说“作为一个 AI”。
10. 不要用客服口吻。
11. 不要过度解释。
12. 如果用户表达危险的自伤、自杀、伤害他人等内容，要停止角色扮演，给出安全、现实、求助导向的回应。

输出格式：
返回 JSON：
{
  "recognizedText": "...",
  "aiReply": "...",
  "responseMode": "comfort | clarify | action | reflect | creative | safety"
}
User Prompt 模板
下面是用户在私人笔记本上手写的内容。请识别并理解它，然后生成一句或几句适合写回笔记本页面上的回应。

用户手写内容：
{{recognized_or_ocr_text}}

最近上下文：
{{recent_context}}

请返回 JSON。
________________________________________
9. 手写识别策略
第一版优先做最简单方案：
v0.1
App 把页面截图发给后端。
后端把图片传给多模态大模型，让模型识别用户写了什么并生成回应。
优点：
•	开发最快。
•	不依赖 ML Kit。
•	适合快速验证产品体验。
缺点：
•	成本较高。
•	图片识别可能不稳定。
v0.2
接入 Google ML Kit Digital Ink Recognition。
使用 stroke 数据直接识别手写文字。
识别后的文本再发给后端大模型。
优点：
•	成本更低。
•	响应更快。
•	更适合长期产品化。
第一阶段先做 v0.1，不要卡在识别优化上。
________________________________________
10. 墨水浮现动画
AI 回复不能像普通聊天气泡一样出现。
第一版实现方式：
1.	使用 Compose Text 显示 AI 回复。
2.	按字逐个显示。
3.	每个字使用 alpha 淡入。
4.	放在纸张 Canvas 的下方或用户文字旁边。
5.	样式使用手写感字体或 serif 字体。
6.	背景保持纸张质感。
伪逻辑：
var visibleText by remember { mutableStateOf("") }

LaunchedEffect(aiReply) {
    visibleText = ""
    aiReply.forEach { char ->
        visibleText += char
        delay(45)
    }
}
后续版本再做真正的 SVG 笔画动画。
________________________________________
11. 视觉风格
第一版风格：
深色封面
羊皮纸 / 旧纸张页面
墨水黑色笔迹
AI 回复略微发灰或深蓝黑
页面有轻微纸张纹理
按钮尽量克制
不要做成聊天 App
重要原则：
•	不要气泡。
•	不要头像。
•	不要像微信。
•	不要像 ChatGPT。
•	它应该像一本会回应的笔记本。
________________________________________
12. 本地保存
第一版本地保存即可。
保存内容：
pageId
createdAt
updatedAt
strokesJson
recognizedText
aiReply
不要第一版就做云同步。
先保证本地 APK 能跑通体验。
________________________________________
13. 后端 FastAPI 结构建议
backend/
  main.py
  requirements.txt
  app/
    api/
      notebook.py
    services/
      ai_service.py
      prompt_service.py
    models/
      notebook.py
    config.py
requirements.txt
fastapi
uvicorn
pydantic
python-dotenv
openai
main.py
from fastapi import FastAPI
from app.api.notebook import router as notebook_router

app = FastAPI(title="Living Notebook API")

app.include_router(notebook_router, prefix="/api/notebook")
notebook.py
from fastapi import APIRouter
from pydantic import BaseModel
from app.services.ai_service import generate_notebook_reply

router = APIRouter()

class NotebookReplyRequest(BaseModel):
    pageId: str
    strokes: list | None = None
    imageBase64: str | None = None
    recentContext: str | None = None

class NotebookReplyResponse(BaseModel):
    recognizedText: str
    aiReply: str
    responseMode: str

@router.post("/reply", response_model=NotebookReplyResponse)
async def reply(req: NotebookReplyRequest):
    result = await generate_notebook_reply(req)
    return result
________________________________________
14. 开发顺序
Step 1：创建 Android 项目
目标：
•	Kotlin
•	Jetpack Compose
•	单 Activity
•	可以运行在 Android 平板上
Step 2：实现纸张 Canvas
目标：
•	显示一张居中的纸
•	用户可以手写
•	可以清空
•	可以撤销
Step 3：实现 stroke 保存
目标：
•	保存用户每一笔 stroke
•	可以序列化为 JSON
•	页面重开后能恢复笔迹
Step 4：实现后端 FastAPI
目标：
•	/api/notebook/reply 可以接收请求
•	暂时返回 mock AI 回复
Step 5：App 连接后端
目标：
•	点击“回应”
•	请求后端
•	收到 aiReply
•	显示在页面上
Step 6：实现墨水浮现动画
目标：
•	AI 回复不是瞬间出现
•	按字逐渐浮现
Step 7：接入真实大模型 API
目标：
•	后端调用大模型
•	根据用户手写内容生成回应
Step 8：页面截图上传
目标：
•	App 将当前 Canvas 渲染成 bitmap
•	转 base64
•	发给后端
•	后端传给多模态模型识别
Step 9：本地保存完整页面
目标：
•	页面、笔迹、AI 回复全部保存
•	App 重启后能恢复
________________________________________
15. 验收标准
第一个 Demo 完成后，必须满足：
1.	华为 Pad 可以安装 APK。
2.	打开 App 后能看到纸张页面。
3.	用户可以流畅手写。
4.	点击“回应”后，App 不崩溃。
5.	后端可以收到请求。
6.	AI 可以返回一句回应。
7.	回应以墨水浮现形式显示。
8.	关闭 App 后再打开，页面内容还在。
最重要的体验验收：
看起来不能像聊天软件，必须像一本活的笔记本。
________________________________________
16. Cursor / Codex 执行要求
请按阶段开发，不要一次性生成巨大工程。
每完成一个阶段，需要：
1.	说明改了哪些文件。
2.	说明如何运行。
3.	说明如何测试。
4.	保证代码可以编译。
5.	不要引入不必要的复杂依赖。
6.	不要提前做登录、支付、云同步。
7.	如果遇到技术取舍，优先选择最快能跑通 MVP 的方案。
第一目标：
先做出 Android 本地手写页面 + mock AI 回复 + 墨水浮现动画。
第二目标：
再接 FastAPI 后端。
第三目标：
最后接真实大模型 API。
________________________________________
17. 当前最优先任务
请先完成：
创建一个 Android Kotlin + Jetpack Compose 项目。
实现一个 NotebookPageScreen。
页面中间显示一张纸。
用户可以在纸上用手指或触控笔书写。
底部有三个按钮：清空、撤销、回应。
点击回应后，暂时显示一条 mock 回复：
“你不是缺方向。你缺的是一个能让现实给你反馈的顺序。”
这条回复需要以逐字浮现的墨水动画显示在纸上。
完成后再进入后端和大模型 API 接入。
