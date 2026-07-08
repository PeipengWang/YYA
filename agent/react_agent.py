from langchain.agents import create_agent

from model.factory import chat_model, checkpointer
from utils.prompt_loader import load_system_prompts
from agent.tools import (
    get_yiyuan_weather_forecast,
    soil_time_series_analysis,
    rag_apple_knowledge_search,
    judge_apple_phenological_period,
    calculate_water_fertilizer_amount,
    decision_trace_explain,
)
from agent.tools.middleware import (
    monitor_tool,
    log_before_model,
    report_prompt_switch,
    summary_middleware,
)


class ReactAgent:
    def __init__(self):
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompts(),
            tools=[
                get_yiyuan_weather_forecast,
                soil_time_series_analysis,
                rag_apple_knowledge_search,
                judge_apple_phenological_period,
                calculate_water_fertilizer_amount,
                decision_trace_explain,
            ],
            middleware=[
                summary_middleware,
                monitor_tool,
                log_before_model,
                report_prompt_switch,
            ]
            # checkpointer=checkpointer,  //记忆管理
        )

    def execute_stream(self, query: str, thread_id: str = "default_user"):
        input_dict = {
            "messages": [
                {"role": "user", "content": query},
            ]
        }
        config = {"configurable": {"thread_id": thread_id}}
        for chunk in self.agent.stream(
            input_dict,
            stream_mode="values",
            context={},
            config=config,
        ):
            latest_message = chunk["messages"][-1]
            # 仅输出最终结论（无工具调用的 AI 消息），跳过思考过程
            if latest_message.content and latest_message.type == "ai":
                tool_calls = getattr(latest_message, "tool_calls", None)
                if not tool_calls:
                    yield latest_message.content.strip() + "\n"


if __name__ == '__main__':
    agent = ReactAgent()
    for chunk in agent.execute_stream("帮我看看当前果园需要怎么施肥、浇水？"):
        print(chunk, end="", flush=True)
