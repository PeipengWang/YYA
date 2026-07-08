import json
import os
import sqlite3
import re
import time
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
