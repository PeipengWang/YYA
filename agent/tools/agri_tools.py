
from datetime import datetime
import json
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