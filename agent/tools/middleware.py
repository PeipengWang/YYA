from typing import Callable

from langchain.agents import AgentState
from langchain.agents.middleware import wrap_tool_call, before_model, dynamic_prompt, ModelRequest
from langchain.agents.middleware import SummarizationMiddleware
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command

from model.factory import chat_model, checkpointer
from utils.logger_handler import logger
from utils.prompt_loader import load_system_prompts


@wrap_tool_call
def monitor_tool(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    logger.info(f"[tool monitor] 执行工具: {request.tool_call['name']}")
    logger.info(f"[tool monitor] 传入参数: {request.tool_call['args']}")
    try:
        result = handler(request)
        logger.info(f"[tool monitor] 工具 {request.tool_call['name']} 调用成功")
        return result
    except Exception as e:
        logger.error(f"工具 {request.tool_call['name']} 调用失败, 原因: {str(e)}")
        raise e


@before_model
def log_before_model(state: AgentState, runtime: Runtime) -> None:
    logger.info(f"[log_before_model] 即将调用模型，带有 {len(state['messages'])} 条消息。")
    for i, msg in enumerate(state["messages"]):
        try:
            content = msg.content
            if hasattr(msg, "role"):
                role = msg.role
            elif hasattr(msg, "name"):
                role = f"Tool({msg.name})"
            elif "tool_call" in str(msg):
                role = "ToolCall"
            else:
                role = type(msg).__name__
            logger.info(f"[消息 {i+1}] {role}: {str(content)[:200]}")
        except Exception:
            logger.info(f"[消息 {i+1}] 完整内容: {str(msg)[:300]}...")
    return None


@dynamic_prompt
def report_prompt_switch(request: ModelRequest):
    return load_system_prompts()


# 沂源苹果农事决策 — 对话摘要提示词
SUMMARY_PROMPT = """
你是沂源苹果智能农事决策对话总结专家，将下面多轮农事决策对话浓缩成一段精简上下文摘要：
1. 完整保留农田土壤/环境数据、气象风险、物候期、病虫害等核心信息；
2. 保留已给出的农事建议、水肥方案、灾害防控措施；
3. 删除重复数据、客套话、无效冗余语句；
4. 输出纯正文段落，不要标题、编号、多余符号。
"""

summary_middleware = SummarizationMiddleware(
    model=chat_model,
    trigger=("messages", 100),
    keep=("messages", 10),
    summary_prompt=SUMMARY_PROMPT,
)
