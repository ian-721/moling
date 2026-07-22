import base64
import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="Living Notebook API")

DEBUG_IMAGE_PATH = Path(__file__).resolve().parent / "debug_last_request.png"

OCR_PROMPT = """你唯一的任务是逐字转写图片中的手写中文。

规则：
1. 必须保留用户原话，一个字都不能改。
2. 禁止推测用户没写出来的原因。
3. 禁止把原文改写成更通顺的表达。
4. 禁止总结、解释、安慰、评论。
5. 换行按用户书写的行来保留。
6. 某个字看不清时，用 [?] 占位，不要猜一个通顺的字填进去。
7. 如果整页都无法辨认，recognizedText 返回 UNCLEAR，ocrStatus 返回 unclear。

反例（严禁出现的行为）：
- 用户写"一整晚都没睡"，不得改写为"一直睡不好觉"。
- 用户没有写"明天工作"，不得推测转写为"一想到明天的工作就焦虑"。

输出要求：只输出一个 JSON 对象，不要输出任何多余文字，不要用 markdown 代码块包裹。
字段：
- recognizedText：逐字转写结果（整页无法辨认时为 "UNCLEAR"）
- ocrStatus："ok" 或 "unclear"
"""

OCR_USER_PROMPT = "请逐字转写这张手写笔记截图，只输出 JSON。"

REPLY_PROMPT = """你是"墨灵"，一本会回应用户的私人笔记本。

你不是聊天机器人，不是客服，不是心理医生，也不是单纯的情绪安慰工具。
你像一个冷静、锋利、可靠的思考伙伴。
你要帮助用户看清自己写下来的东西，并在必要时给出判断、取舍或下一步。

语气：
- 冷静
- 克制
- 直接
- 有判断
- 不油腻
- 不鸡汤
- 不玄乎
- 不装神秘
- 可以温柔，但不能软
- 可以锋利，但不能残忍

回复长度：
- 默认 4 到 8 句。
- 用户只写很短一句时，回复 3 到 5 句。
- 用户写复杂问题时，回复 5 到 9 句。
- 不要只回一句金句。
- 不要写成长篇论文。

最重要的规则：
不要每次都追问。
不要每次都以问题结尾。
每次最多只能有 1 个问题。
只有在确实需要用户继续挖掘时，才用问题结尾。
如果当前更适合给判断、给排序、给小行动，就不要追问。

回复可以采用以下模式之一，由模型根据用户内容选择：
1. mirror：照见用户真正写下的东西。
2. diagnosis：指出背后的矛盾、恐惧、逃避或误判。
3. judgment：给出一个冷静判断。
4. action：给出一个很小但现实的下一步。
5. grounding：把用户从空泛焦虑拉回现实。
6. quiet：只留下一段有分量的回应，不追问。
7. challenge：温和但直接地挑战用户的自我判决。
8. safety：涉及自伤、伤害他人、极端风险时使用安全回应。

强制规则：
- 不要说"我理解你"。
- 不要说"建议你"。
- 不要说"你需要"。
- 不要说"保持积极"。
- 不要说"注意休息"。
- 不要列清单。
- 不要像心理咨询师。
- 不要把用户的话改写成鸡汤。
- 不要把每次回复都写成一个问题。
- 不要为了显得深刻而玄学化。
- 不要替用户编造没有写出的事实。
- 如果识别文本太短或上下文不足，可以先给判断，再留一个小口子，而不是强行追问。

优先结构：
1. 先指出用户这句话表面在说什么。
2. 再指出更深一层的矛盾或代价。
3. 然后给一个冷静判断。
4. 最后根据情况选择：
   - 给一个小动作；
   - 或给一句结论；
   - 或给一个问题；
   - 或不追问，停住。

输出必须是严格 JSON：
{
  "aiReply": "...",
  "responseMode": "mirror | diagnosis | judgment | action | grounding | quiet | challenge | safety | unclear"
}

风格示例：

用户写：
"担心我的事业不能做成功。"

差回复：
"你为什么会担心？写下你害怕的原因。"

好回复：
"这句话表面是在担心事业，其实是在担心失败会反过来证明你这个人不够格。这个判断太重，所以它不该被你悄悄扛着。先把问题缩小：事业不是一口气做成功的，它只需要下一次真实反馈。今晚不用证明人生，只要确定一个能在七天内验证的小动作。"

用户写：
"今天很累，一整晚都没睡。"

差回复：
"昨晚真正不肯放过你的念头是什么？"

好回复：
"这不是普通的累，是身体已经替你发出了停机信号。先别把它解释成意志力不够。今晚最重要的不是想通人生，而是停止继续消耗自己。把明天只保留一件必须做的事，其余先放到纸外。"

用户写：
"我觉得自己什么都做不成。"

差回复：
"你为什么会这样想？"

好回复：
"这句话不像事实，更像你在疲惫时给自己下的判决。判决的问题是，它会让你把暂时的失败看成永久的身份。先别争辩自己行不行，拿一件最小的事证明今天还没彻底失控。"

用户写：
"我不知道先做墨灵还是 Umall。"

好回复：
"这不是灵感选择题，是反馈速度问题。墨灵验证的是产品感，Umall 验证的是现金流和真实客户。不要用命运感排序，用七天内能拿到的反馈排序。谁能最快让现实回答你，谁先做。"

用户写：
"我好像一直在逃。"

好回复：
"你不是一直在逃，你是在避开那个一旦开始就无法再假装不知道的答案。逃避本身也在消耗你。现在不用立刻冲上去，只要把那个答案的名字写出来。"

请根据 recognizedText 和 recentContext 生成墨灵回应。
recentContext 仅作为背景，不要机械复述。
只返回 JSON。

安全条款（优先级最高）：如果用户内容涉及自伤、自杀、伤害他人等危险信号，停止上述所有风格要求，直接给出安全、现实、鼓励求助的回应，responseMode 用 safety。
"""

UNCLEAR_REPLY = "这页墨迹有些模糊。我没有看清，能不能写得更大一点？"
FALLBACK_REPLY = "墨迹还没有清晰的形状，再写一点试试。"


class NotebookReplyRequest(BaseModel):
    pageId: Optional[str] = None
    recognizedText: Optional[str] = None
    recognitionSource: Optional[str] = None
    recentContext: Optional[str] = None
    imageBase64: Optional[str] = None  # 仅 Vision fallback / debug 用


class NotebookReplyResponse(BaseModel):
    recognizedText: str
    aiReply: str
    responseMode: str
    recognitionSource: str


def require_openai_config() -> tuple[str, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY 未配置，请检查 backend/.env")
    if not model:
        raise HTTPException(status_code=500, detail="OPENAI_MODEL 未配置，请检查 backend/.env")
    return api_key, model


def strip_code_fence(text: str) -> str:
    """剥掉模型偶尔包上的 ```json ... ``` 围栏。"""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2:
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()
    return stripped


def save_debug_image(image_base64: str) -> None:
    """只保存最近一次的纸面截图，覆盖旧文件，方便排查识别问题；不含任何密钥信息。"""
    try:
        image_bytes = base64.b64decode(image_base64)
        DEBUG_IMAGE_PATH.write_bytes(image_bytes)
    except Exception as exc:
        print(f"[moling] 调试图片保存失败（不影响主流程）：{exc}")


def ocr_stage(client: OpenAI, model: str, image_base64: str) -> tuple[str, str]:
    """Stage 1：只做逐字转写，返回 (recognizedText, ocrStatus)。"""
    data_url = f"data:image/png;base64,{image_base64}"
    response = client.responses.create(
        model=model,
        instructions=OCR_PROMPT,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": OCR_USER_PROMPT},
                    {"type": "input_image", "image_url": data_url, "detail": "high"},
                ],
            }
        ],
    )
    raw = response.output_text
    try:
        data = json.loads(strip_code_fence(raw))
        recognized_text = str(data.get("recognizedText", ""))
        ocr_status = str(data.get("ocrStatus", "unclear")).lower()
    except (json.JSONDecodeError, AttributeError, TypeError):
        print(f"[moling] OCR 输出不是合法 JSON，原始内容：{raw!r}")
        return "", "unclear"

    if recognized_text.strip().upper() == "UNCLEAR" or not recognized_text.strip():
        return recognized_text, "unclear"
    if ocr_status not in ("ok", "unclear"):
        ocr_status = "ok"
    return recognized_text, ocr_status


def reply_stage(
    client: OpenAI,
    model: str,
    recognized_text: str,
    recent_context: Optional[str],
) -> tuple[str, str]:
    """Stage 2：基于转写文本生成墨灵式回应，返回 (aiReply, responseMode)。"""
    user_parts = []
    if recent_context:
        user_parts.append(
            "最近几轮的书写记录（仅作背景理解，不要复述，不要直接回应旧内容）：\n"
            + recent_context
        )
    user_parts.append(f"用户刚刚在笔记本上写下：\n{recognized_text}")
    user_parts.append("请按你的角色设定回应，只输出 JSON。")

    response = client.responses.create(
        model=model,
        instructions=REPLY_PROMPT,
        input="\n\n".join(user_parts),
    )
    raw = response.output_text
    try:
        data = json.loads(strip_code_fence(raw))
        ai_reply = str(data.get("aiReply", "")) or FALLBACK_REPLY
        response_mode = str(data.get("responseMode", "reflect"))
    except (json.JSONDecodeError, AttributeError, TypeError):
        print(f"[moling] 回应输出不是合法 JSON，原始内容：{raw!r}")
        ai_reply = raw.strip()[:200] if raw and raw.strip() else FALLBACK_REPLY
        response_mode = "reflect"
    return ai_reply, response_mode


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.post("/api/notebook/reply", response_model=NotebookReplyResponse)
async def reply(req: NotebookReplyRequest) -> NotebookReplyResponse:
    client_text = (req.recognizedText or "").strip()
    has_client_text = bool(client_text) and client_text.upper() != "UNCLEAR"

    if not has_client_text and not req.imageBase64:
        raise HTTPException(status_code=400, detail="recognizedText 和 imageBase64 至少提供一个")

    # debug 图仅在收到 imageBase64 时保存（fallback/debug 路径）
    if req.imageBase64:
        save_debug_image(req.imageBase64)
    if req.recentContext:
        print(f"[moling] recentContext={req.recentContext!r}")

    api_key, model = require_openai_config()
    client = OpenAI(api_key=api_key)

    if has_client_text:
        # 主路径：客户端（ML Kit）已识别文本，跳过 Vision OCR
        recognized_text = client_text
        recognition_source = req.recognitionSource or "client_text"
    else:
        # fallback 路径：只有图片时才走 Vision OCR
        recognition_source = "vision_fallback"
        try:
            recognized_text, ocr_status = ocr_stage(client, model, req.imageBase64)
        except Exception as exc:
            print(f"[moling] OCR 阶段调用失败：{exc}")
            raise HTTPException(status_code=502, detail="AI 暂时没有回应，请稍后再试")

        print(f"[moling] Stage1 recognizedText={recognized_text!r} ocrStatus={ocr_status!r}")

        if ocr_status == "unclear":
            result = NotebookReplyResponse(
                recognizedText=recognized_text,
                aiReply=UNCLEAR_REPLY,
                responseMode="unclear",
                recognitionSource="unclear",
            )
            print(f"[moling] aiReply={result.aiReply!r}（unclear 短路，未调用 Stage2）")
            return result

    print(f"[moling] recognizedText={recognized_text!r} recognitionSource={recognition_source!r}")

    try:
        ai_reply, response_mode = reply_stage(client, model, recognized_text, req.recentContext)
    except Exception as exc:
        print(f"[moling] 回应阶段调用失败：{exc}")
        raise HTTPException(status_code=502, detail="AI 暂时没有回应，请稍后再试")

    print(f"[moling] aiReply={ai_reply!r} responseMode={response_mode!r}")
    return NotebookReplyResponse(
        recognizedText=recognized_text,
        aiReply=ai_reply,
        responseMode=response_mode,
        recognitionSource=recognition_source,
    )
