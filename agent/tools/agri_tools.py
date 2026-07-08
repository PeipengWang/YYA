
from datetime import datetime
import json
from pydantic import BaseModel, Field
from typing import List, Union
from langchain_core.tools import tool

from model.factory import chat_model
from agent.tools.common import rag, _current_phenological_period
from utils.logger_handler import logger


# ============================================================
# 沂源苹果垂直RAG检索
# ============================================================
@tool
def rag_apple_knowledge_search(query: str) -> str:
    """
    从沂源苹果专属RAG知识库检索本地化、分物候期的专业种植标准与农技方案。
    入参：query — 当前农事研判需求/场景问题文本。
    出参：凝练后的标准化技术摘要（物候标准、土壤规范、灾害防控、病虫害防治）。
    """
    logger.info(f"[Tool] rag_apple_knowledge_search 被调用, query={query}")
    return rag.rag_summarize(query)


# ============================================================
# 工具5：苹果物候期自动判定
# ============================================================
@tool
def judge_apple_phenological_period() -> str:
    """
    基于当前日期与沂源本地物候规律，自动判定苹果树当前生育阶段及核心管护需求。
    无入参（系统自动读取日期判定）。
    出参：JSON格式当前物候期名称、时间段、核心生长需求、管护要点。
    """
    logger.info("[Tool] judge_apple_phenological_period 被调用")
    period = _current_phenological_period()
    result = {
        "判定时间": datetime.now().strftime("%Y-%m-%d"),
        "当前物候期": period["period_name"],
        "时间段": period["date_range"],
        "核心生长需求": period["core_needs"],
        "属地": "山东省淄博市沂源县",
        "山地苹果物候特点": "沂源山地昼夜温差大，物候期较平原晚3-5天，着色期糖分积累优势明显",
        "数据来源": "基于沂源本地积温与物候规律自动判定",
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


# ============================================================
# 工具6：水肥量化计算
# ============================================================
@tool
def calculate_water_fertilizer_amount(analysis_context: str) -> str:
    """
    将数据研判与专业标准转化为可落地的量化农事参数（施肥品类、配比、用量、灌溉时长、水量）。
    入参：analysis_context — 整合土壤时序、环境、物候期、气象风险的综合文本。
    出参：JSON格式精准施肥方案、灌溉方案、土壤改良方案。
    """
    logger.info(f"[Tool] calculate_water_fertilizer_amount 被调用")
    prompt = f"""你是沂源苹果水肥量化计算专家。基于以下综合分析上下文，输出精准量化农事方案。

综合分析上下文：
{analysis_context}

请按以下JSON结构输出（只输出JSON，无额外说明）：
{{
    "施肥方案": {{
        "推荐肥料品类": "复合肥类型名称",
        "氮磷钾配比": "N:P:K比例",
        "每亩用量_kg": 数字,
        "最佳施肥时间": "具体日期或时间窗口",
        "施肥方式": "沟施/穴施/撒施/水肥一体化",
        "注意事项": "沂源山地适配提醒"
    }},
    "灌溉方案": {{
        "灌溉方式": "滴灌/微喷/沟灌",
        "单次灌溉时长_分钟": 数字,
        "每亩灌水量_立方米": 数字,
        "灌溉时段": "清晨/傍晚等",
        "灌溉频率": "每X天一次"
    }},
    "土壤改良方案": {{
        "改良措施": "增施有机肥/调酸/松土等",
        "改良剂用量": "具体用量",
        "执行时机": "时间窗口"
    }}
}}"""
    try:
        response = chat_model.invoke(prompt)
        content = getattr(response, "content", "")
        if not content:
            return json.dumps({"error": "水肥计算模型返回为空"}, ensure_ascii=False)
        return content.strip()
    except Exception as e:
        logger.exception(f"水肥量化计算失败: {e}")
        return json.dumps({"error": f"计算异常: {str(e)}"}, ensure_ascii=False)


# ============================================================
# 工具7：决策溯源与推理解释
# ============================================================
@tool
def decision_trace_explain(decision_context: str) -> str:
    """
    梳理完整决策链路，输出可解释、可溯源的农事决策报告。
    入参：decision_context — 本次所有工具调用结果与决策内容汇总文本。
    出参：结构化决策溯源报告（推理依据、数据支撑、知识库条款、注意事项）。
    """
    logger.info(f"[Tool] decision_trace_explain 被调用")
    prompt = f"""你是沂源苹果农事决策溯源专家。基于以下决策上下文，输出完整可解释决策报告。

决策上下文：
{decision_context}

请按以下结构输出（纯文本，不使用代码块）：

【决策溯源报告】

一、推理依据链
- 土壤数据依据：（简述土壤时序分析结论）
- 田间环境依据：（简述实时微气象数据）
- 气象趋势依据：（简述未来天气预判）
- 物候期约束：（当前生育期及核心需求）
- 知识库条款引用：（匹配的沂源苹果本地化种植标准）

二、决策总结
（一段话概括本次农事建议的核心要点）

三、风险提示与注意事项
- 气象风险：有无及应对
- 田间胁迫风险：有无及应对
- 操作禁忌：（当前物候期禁止的操作）

四、免责声明
本建议为AI智能辅助决策参考，极端天气或重大农事操作请结合实地情况并咨询本地农技人员。"""
    try:
        response = chat_model.invoke(prompt)
        content = getattr(response, "content", "")
        if not content:
            return "决策溯源生成异常，请重试。"
        return content.strip()
    except Exception as e:
        logger.exception(f"决策溯源自生成失败: {e}")
        return f"决策溯源生成异常: {str(e)}"


# # ============================================================
# # 工具8：结构化决策摘要生成
# # ============================================================
# @tool
# def generate_decision_summary(context: str) -> str:
#     """
#     基于前面的土壤数据、天气数据、物候期、RAG知识等综合分析上下文，调用大模型生成符合决策页面接口规范的结构化JSON响应。
#     入参：context — 整合所有前置工具调用结果的综合分析文本。
#     出参：JSON格式含 summary/advices/problematicSensors/alerts 四项的决策数据（不含 code 包装）。
#     """
#     logger.info("[Tool] generate_decision_summary 被调用")
#     prompt = f"""你是沂源苹果智能农事决策助手"小沂"。根据以下综合分析上下文，生成结构化决策建议JSON。
#
# 综合分析上下文：
# {context}
#
# 请严格按照以下JSON结构输出（只输出JSON，不含markdown代码块标记，不含任何额外文字）：
#
# {{
#     "summary": "1-3句话的综合摘要",
#     "advices": [
#         {{
#             "category": "irrigation/fertilization/crisis/pest/weather",
#             "icon": "emoji图标",
#             "title": "分类标题",
#             "level": "danger/warning/safe/info",
#             "items": ["建议条目1", "建议条目2"]
#         }}
#     ],
#     "problematicSensors": [
#         {{
#             "device": "设备名",
#             "name": "指标名",
#             "value": 数值,
#             "unit": "单位",
#             "status": "danger/warning",
#             "reason": "异常原因简述"
#         }}
#     ],
#     "alerts": [
#         {{
#             "level": "danger/warning/info",
#             "device": "关联设备或'系统'",
#             "message": "告警描述"
#         }}
#     ]
# }}
#
# 规则：
# - advices：只返回有实际建议的分类，无需建议的分类不返回
# - problematicSensors：只列异常的传感器，value必须是数字类型，全正常则返回空数组[]
# - alerts：最多5条，按优先级排序，无告警则返回空数组[]
# - 所有字段必须存在，即使值为空数组"""
#     try:
#         response = chat_model.invoke(prompt)
#         content = getattr(response, "content", "")
#         if not content:
#             return json.dumps({"error": "决策摘要生成返回为空"}, ensure_ascii=False)
#         return content.strip()
#     except Exception as e:
#         logger.exception(f"决策摘要生成失败: {e}")
#         return json.dumps({"error": f"决策摘要生成异常: {str(e)}"}, ensure_ascii=False)
# --------------------------
# 1. 定义结构化输出Pydantic模型，完全匹配前端接口规范
# --------------------------
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

# 顶层决策输出结构
class DecisionSummaryOutput(BaseModel):
    summary: str = Field(description="1-3句话果园综合状态摘要")
    advices: List[AdviceItem] = Field(description="农事建议数组，无对应分类则空数组")
    problematicSensors: List[ProblematicSensor] = Field(description="异常传感器数组，无异常为空数组")
    alerts: List[AlertItem] = Field(description="告警列表，最多5条，无告警为空数组")

# 提前绑定带结构化输出的模型（全局初始化一次，不要每次工具调用重复创建）
structured_chat_model = chat_model.with_structured_output(DecisionSummaryOutput)

# ============================================================
# 工具8：结构化决策摘要生成（Pydantic强约束改造版）
# ============================================================
@tool
def generate_decision_summary(context: str) -> str:
    """
    基于前面的土壤数据、天气数据、物候期、RAG知识等综合分析上下文，
    调用大模型生成符合决策页面接口规范的结构化JSON响应。
    入参：context — 整合所有前置工具调用结果的综合分析文本。
    出参：标准JSON字符串，包含 summary/advices/problematicSensors/alerts 四项
    """
    logger.info("[Tool] generate_decision_summary 被调用")

    system_prompt = """
你是沂源苹果智能农事决策助手"小沂"。
根据用户提供的果园综合分析上下文，输出标准化农事决策结果，严格遵循以下规则：
1. advices：仅保留有实际农事操作建议的分类，无建议的分类不出现；
2. problematicSensors：只列出数值异常的传感器指标，value必须为纯数字，全部正常时返回空数组；
3. alerts：最多输出5条告警，按风险优先级从高到低排序，无告警返回空数组；
4. 所有顶层字段必须存在，无数据时赋值为空数组，禁止省略键名；
5. 结合沂源苹果种植场景给出贴合农事的专业建议。
    """
    full_prompt = f"{system_prompt}\n综合分析上下文：\n{context}"

    try:
        # 强结构化输出，直接得到校验后的模型实例
        result: DecisionSummaryOutput = structured_chat_model.invoke(full_prompt)
        # 序列化为纯净JSON字符串返回给上层Agent
        value =  result.model_dump_json(ensure_ascii=False, indent=2)
        print("**" * 20)
        print(value)
        print("**" * 20)
        return value

    except Exception as e:
        logger.exception(f"决策摘要生成失败: {e}")
        err_data = {"error": f"决策摘要生成异常: {str(e)}"}
        return json.dumps(err_data, ensure_ascii=False)