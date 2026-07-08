import json
import time

# ---------------------- 工具函数（放在文件顶部） ----------------------
# 全局阈值配置
STEP_TRIM_THRESHOLD = 10


def get_current_step(saver, thread_id: str) -> int:
    cfg = {"configurable": {"thread_id": thread_id}}
    cp = saver.get(cfg)
    if not cp:
        return 0
    ver_str = cp.get("channel_versions", {}).get("__start__", "0")
    # 分割版本号，前面整数就是迭代轮次
    try:
        step = int(ver_str.split(".")[0])
    except:
        step = 0
    return step

def compress_chat_history(model, raw_messages: list) -> str:
    """LLM压缩多轮对话为一段摘要"""
    try:
        chat_lines = []
        for msg in raw_messages:
            # 兼容 LangGraph Message对象 / dict 两种格式
            if hasattr(msg, "type") and hasattr(msg, "content"):
                role = msg.type
                content = msg.content
            else:
                role = msg.get("type", "")
                content = msg.get("content", "")
            chat_lines.append(f"{role}：{content}")
        chat_content = "\n".join(chat_lines)

        prompt = f"""
你是沂源苹果农事决策对话精简助手，浓缩历史对话：
1. 保留用户核心农事诉求、田间数据、气象风险、物候期信息
2. 保留Agent给出的农事方案、水肥建议、灾害防控措施
3. 删除重复、废话、语气词，文字通顺精简
4. 只输出摘要正文，不要标题、符号、额外解释

对话记录：
{chat_content}
        """
        res = model.invoke([{"role": "user", "content": prompt}])
        return res.content.strip()
    except Exception as err:
        print(f"对话压缩LLM调用异常: {err}")
        return ""

def trim_round_chat(saver, thread_id: str, model):
    """step达标后，替换全部消息为精简摘要，step清零"""
    cfg = {"configurable": {"thread_id": thread_id}}
    checkpoint = saver.get(cfg)
    if not checkpoint:
        return
    state = checkpoint.values
    messages = state.get("messages", [])
    # 消息过少不压缩
    if len(messages) < 4:
        return

    summary = compress_chat_history(model, messages)
    if not summary:
        return

    # 替换所有历史消息为1条系统摘要
    state["messages"] = [
        {"type": "system", "content": f"【历史对话精简摘要】{summary}"}
    ]
    # 写入新快照，step重置为0
    saver.put(
        config=cfg,
        checkpoint=checkpoint.checkpoint,
        metadata={"step": 0, "source": "round_end_trim"},
        new_versions=checkpoint.versions
    )
    print(f"会话 {thread_id} 已满{STEP_TRIM_THRESHOLD}轮，对话已精简合并，步数清零")

