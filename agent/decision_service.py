from typing import List, Union

from pydantic import BaseModel, Field

from model.factory import chat_model
from utils.logger_handler import logger


# ═══════════════════════════════════════════════════════════════
# Pydantic 结构化输出模型（匹配决策页面接口规范）
# ═══════════════════════════════════════════════════════════════

class AdviceItem(BaseModel):
    category: str = Field(description="分类，可选值：irrigation/fertilization/crisis/pest/weather")
    icon: str = Field(description="emoji图标")
    title: str = Field(description="分类标题")
    level: str = Field(description="等级，可选值：danger/warning/safe/info")
    items: List[str] = Field(description="该分类下具体农事建议条目")


class ProblematicSensor(BaseModel):
    device: str = Field(description="设备标识名称，如device")
    name: str = Field(description="传感器指标名，如土壤湿度")
    value: Union[int, float] = Field(description="纯数字数值，不能带百分号等单位")
    unit: str = Field(description="单位，如%")
    status: str = Field(description="异常等级：danger/warning")
    reason: str = Field(description="指标异常原因简述")


class AlertItem(BaseModel):
    level: str = Field(description="告警等级：danger/warning/info")
    device: str = Field(description="关联设备名称，无设备填'系统'")
    message: str = Field(description="完整告警文案")


class DecisionSummaryOutput(BaseModel):
    summary: str = Field(description="1-3句话果园综合状态摘要")
    advices: List[AdviceItem] = Field(description="农事建议数组，无对应分类则空数组")
    problematicSensors: List[ProblematicSensor] = Field(description="异常传感器数组，无异常为空数组")
    alerts: List[AlertItem] = Field(description="告警列表，最多5条，无告警为空数组")


# 绑定结构化输出的模型（全局单例）
structured_chat_model = chat_model.with_structured_output(DecisionSummaryOutput)


# ═══════════════════════════════════════════════════════════════
# 结构化转换系统提示词
# ═══════════════════════════════════════════════════════════════

STRUCTURED_CONVERSION_PROMPT = """你是沂源苹果智能农事决策助手"小沂"。
根据以下Agent生成的完整决策报告，提取关键信息输出标准化农事决策JSON。

严格遵循以下规则：
1. summary：1-3句话综合摘要，概括果园当前状态和核心建议
2. advices：按category分类（irrigation/fertilization/crisis/pest/weather），仅保留有实际建议的分类，无建议的分类不出现
3. problematicSensors：只列出数值异常的传感器指标，value必须为纯数字（int或float），全部正常时返回空数组[]
4. alerts：最多输出5条告警，按风险优先级从高到低排序，无告警返回空数组[]
5. 所有顶层字段必须存在，无数据时赋值为空数组[]，禁止省略键名
6. 结合沂源苹果种植场景给出贴合农事的专业建议"""


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def generate_decision_summary(prompt: str, agent) -> dict:
    """
    通过 ReAct Agent 执行完整 6 步决策分析链路，Agent 输出自然语言报告，
    再由 structured_chat_model 将报告转换为符合接口规范的结构化 JSON。

    Agent 调用链路：
    soil_time_series_analysis → get_yiyuan_weather_forecast
    → judge_apple_phenological_period → rag_apple_knowledge_search
    → calculate_water_fertilizer_amount → decision_trace_explain

    Returns:
        {"code": 0, "data": {...}}  成功
        {"code": -1, "message": "..."}  失败
    """
    # 1. 通过 ReAct Agent 生成完整自然语言决策报告
    try:
        full_response = ""
        for chunk in agent.execute_stream(prompt):
            full_response += chunk
        full_response = full_response.strip()
    except Exception as e:
        logger.exception(f"[decision_service] Agent执行失败: {e}")
        return {"code": -1, "message": f"智能体分析失败: {str(e)}"}

    if not full_response:
        logger.error("[decision_service] Agent返回为空")
        return {"code": -1, "message": "智能体分析返回为空，请稍后重试"}

    # 2. 用结构化模型将自然语言报告转换为 JSON
    full_context = f"{STRUCTURED_CONVERSION_PROMPT}\n\n决策报告：\n{full_response}"

    try:
        result: DecisionSummaryOutput = structured_chat_model.invoke(full_context)
        data = result.model_dump()
        logger.info(f"[decision_service] 决策生成成功, summary={data.get('summary', '')[:80]}...")
        return {"code": 0, "data": data}
    except Exception as e:
        logger.exception(f"[decision_service] 结构化输出转换失败: {e}")
        return {"code": -1, "message": f"结构化输出转换失败: {str(e)}"}
