import json
import os
import sqlite3
import re
import time
import asyncio
import urllib.request
import urllib.error
import urllib.parse
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.sqlite import SqliteSaver
from starlette.middleware.cors import CORSMiddleware
from agent.react_agent import ReactAgent
from agent.decision_service import generate_decision_summary
from utils.config_handler import rag_conf

app = FastAPI(title="沂源苹果智能农事决策 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TTS_URL = rag_conf["TTS_URL"]
ASR_API_URL = rag_conf.get("ASR_API_URL", "http://127.0.0.1:9001/asr")

agent = ReactAgent()


def clean_tts_text(text: str) -> str:
    """清洗文本用于TTS播报"""
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'#+\s?', '', text)
    text = re.sub(r'---+', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\[.*?\]\(.*?\)', '', text)
    emoji_pattern = re.compile("["
                               u"\U0001F600-\U0001F64F"
                               u"\U0001F300-\U0001F5FF"
                               u"\U0001F680-\U0001F6FF"
                               u"\U0001F1E0-\U0001F1FF"
                               u"\U00002700-\U000027BF"
                               u"\U0000FE00-\U0000FE0F"
                               u"\U0001F900-\U0001F9FF"
                               "]+", flags=re.UNICODE)
    text = emoji_pattern.sub(r'', text)
    return text.strip()


# ===========================
# 聊天接口
# ===========================
@app.post("/api/chat/send")
async def chat_send(request: Request):
    """普通接口：一次性返回完整回复"""
    body = await request.json()
    prompt = body.get("message", "")

    if not prompt:
        return JSONResponse({"error": "消息不能为空"}, status_code=400)

    full_response = ""
    for chunk in agent.execute_stream(prompt):
        full_response += chunk
        time.sleep(0.05)

    full_response = full_response.strip()
    return {"response": full_response}


@app.post("/api/chat/stream")
async def chat_stream(request: Request):
    """SSE 流式聊天接口"""
    body = await request.json()
    prompt = body.get("message", "")

    if not prompt:
        return JSONResponse({"error": "消息不能为空"}, status_code=400)

    async def event_generator():
        full_response = ""
        try:
            for chunk in agent.execute_stream(prompt):
                full_response += chunk
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
            tts_text = clean_tts_text(full_response.strip())
            yield f"data: {json.dumps({'done': True, 'tts_text': tts_text, 'full_response': full_response}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ===========================
# 语音识别接口（ASR）
# 前端把麦克风录的音频传上来，这里原样转发给本地 faster-whisper 服务，
# 避免浏览器直连时受跨域/部署环境限制。用标准库 urllib，不额外引入依赖。
# ===========================
@app.post("/api/asr")
async def asr(request: Request):
    """语音转文字。

    把浏览器上传的 multipart 音频原样透传给本地 faster-whisper 服务，
    不做二次编解码，也不依赖 python-multipart。返回 {code, text}。
    """
    body = await request.body()
    if not body:
        return JSONResponse({"code": -1, "msg": "音频内容为空"}, status_code=400)

    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        return JSONResponse(
            {"code": -1, "msg": f"请求类型必须是 multipart/form-data，当前为 {content_type!r}"},
            status_code=400,
        )

    req = urllib.request.Request(
        ASR_API_URL,
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:500]
        return JSONResponse(
            {"code": -1, "msg": f"ASR 服务返回错误 {e.code}：{detail}"}, status_code=502
        )
    except Exception as e:
        return JSONResponse(
            {"code": -1, "msg": f"无法连接 ASR 服务（{ASR_API_URL}）：{e}"}, status_code=502
        )

    return {
        "code": 0,
        "text": payload.get("text", ""),
        "language": payload.get("language"),
        "duration": payload.get("duration"),
    }


# ===========================
# 语音合成接口（TTS）
# 与 /api/asr 同理：浏览器只认同源的 /api，由网关转发到 TTS 服务，避免直连。
# ===========================
@app.get("/api/tts-stream")
async def tts_stream(
    text: str,
    voice: str = "zh-CN-XiaoxiaoNeural",
    rate: str = "+0%",
    volume: str = "+0%",
    pitch: str = "+0Hz",
):
    """语音播报：转发给本地 edge-tts 服务，并把音频流原样回传给浏览器"""
    if not text.strip():
        return JSONResponse({"code": -1, "msg": "text 参数不能为空"}, status_code=400)

    query = urllib.parse.urlencode(
        {"text": text, "voice": voice, "rate": rate, "volume": volume, "pitch": pitch}
    )
    url = f"{TTS_URL}?{query}"

    try:
        # urlopen / read 是阻塞调用，丢到线程里执行，避免卡住事件循环
        upstream = await asyncio.to_thread(urllib.request.urlopen, url, None, 60)
    except Exception as e:
        return JSONResponse(
            {"code": -1, "msg": f"无法连接 TTS 服务（{TTS_URL}）：{e}"}, status_code=502
        )

    async def audio_generator():
        try:
            while True:
                chunk = await asyncio.to_thread(upstream.read, 8192)
                if not chunk:
                    break
                yield chunk
        finally:
            upstream.close()

    return StreamingResponse(
        audio_generator(),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store"},
    )


# ===========================
# 智能决策摘要接口
# ===========================
@app.post("/api/decision/summary")
async def decision_summary(request: Request):
    """决策摘要接口：接收用户提问，自行获取传感器数据后由智能体分析，返回结构化决策建议"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"code": -2, "message": "请求体必须是JSON格式"}, status_code=400)

    prompt = body.get("prompt", "")
    if not prompt or not prompt.strip():
        return JSONResponse({"code": -2, "message": "prompt 参数不能为空"}, status_code=400)

    result = generate_decision_summary(prompt.strip(), agent)
    if result.get("code") == 0:
        return result
    else:
        return JSONResponse(result, status_code=500)


# ===========================
# 记忆管理接口
# ===========================
@app.get("/api/memory/list_threads")
async def memory_list_threads():
    try:
        conn = sqlite3.connect("resources/apple_farming.db", check_same_thread=False)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT thread_id FROM checkpoints;")
        rows = cur.fetchall()
        conn.close()
        thread_list = [row[0] for row in rows if row[0]]
        return {"code": 0, "threads": thread_list}
    except Exception as e:
        return {"code": -1, "msg": str(e)}


@app.get("/api/memory/detail")
async def memory_detail(thread_id: str):
    try:
        conn = sqlite3.connect("resources/apple_farming.db", check_same_thread=False)
        saver = SqliteSaver(conn)
        cfg = {"configurable": {"thread_id": thread_id}}
        cp = saver.get(cfg)
        conn.close()
        return {"code": 0, "checkpoint": cp}
    except Exception as e:
        return {"code": -1, "msg": str(e)}


# ===========================
# 前端 & 静态资源
# ===========================
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    pass

# ===========================
# 服务入口
# ===========================
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_SERVER_PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
