import json
import re

from utils.logger_handler import logger


# ── 响应校验 ───────────────────────────────────────────────

VALID_LEVELS_ADVICE = {"danger", "warning", "safe", "info"}
VALID_LEVELS_SENSOR = {"danger", "warning"}
VALID_LEVELS_ALERT = {"danger", "warning", "info"}


def validate_decision_response(data: dict) -> tuple[bool, str | None]:
    """
    按接口规范逐字段校验决策响应结构。
    返回 (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "响应必须是JSON对象"

    # summary
    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return False, "data.summary 必须是非空字符串"

    # advices
    advices = data.get("advices")
    if not isinstance(advices, list):
        return False, "data.advices 必须是数组"
    for idx, adv in enumerate(advices):
        if not isinstance(adv, dict):
            return False, f"data.advices[{idx}] 必须是对象"
        for field in ["category", "icon", "title", "level", "items"]:
            if field not in adv:
                return False, f"data.advices[{idx}] 缺少字段 '{field}'"
        if not isinstance(adv["category"], str) or not adv["category"].strip():
            return False, f"data.advices[{idx}].category 必须是非空字符串"
        if not isinstance(adv["icon"], str):
            return False, f"data.advices[{idx}].icon 必须是字符串"
        if not isinstance(adv["title"], str) or not adv["title"].strip():
            return False, f"data.advices[{idx}].title 必须是非空字符串"
        if adv["level"] not in VALID_LEVELS_ADVICE:
            return False, f"data.advices[{idx}].level 必须是 {VALID_LEVELS_ADVICE} 之一，当前值: '{adv['level']}'"
        if not isinstance(adv["items"], list):
            return False, f"data.advices[{idx}].items 必须是数组"
        for i, item in enumerate(adv["items"]):
            if not isinstance(item, str):
                return False, f"data.advices[{idx}].items[{i}] 必须是字符串"

    # problematicSensors
    sensors = data.get("problematicSensors")
    if not isinstance(sensors, list):
        return False, "data.problematicSensors 必须是数组"
    for idx, sensor in enumerate(sensors):
        if not isinstance(sensor, dict):
            return False, f"data.problematicSensors[{idx}] 必须是对象"
        for field in ["device", "name", "value", "unit", "status", "reason"]:
            if field not in sensor:
                return False, f"data.problematicSensors[{idx}] 缺少字段 '{field}'"
        if not isinstance(sensor["device"], str):
            return False, f"data.problematicSensors[{idx}].device 必须是字符串"
        if not isinstance(sensor["name"], str):
            return False, f"data.problematicSensors[{idx}].name 必须是字符串"
        if not isinstance(sensor["value"], (int, float)):
            return False, f"data.problematicSensors[{idx}].value 必须是数字"
        if not isinstance(sensor["unit"], str):
            return False, f"data.problematicSensors[{idx}].unit 必须是字符串"
        if sensor["status"] not in VALID_LEVELS_SENSOR:
            return False, f"data.problematicSensors[{idx}].status 必须是 danger/warning，当前值: '{sensor['status']}'"
        if not isinstance(sensor["reason"], str):
            return False, f"data.problematicSensors[{idx}].reason 必须是字符串"

    # alerts
    alerts = data.get("alerts")
    if not isinstance(alerts, list):
        return False, "data.alerts 必须是数组"
    for idx, alert in enumerate(alerts):
        if not isinstance(alert, dict):
            return False, f"data.alerts[{idx}] 必须是对象"
        for field in ["level", "device", "message"]:
            if field not in alert:
                return False, f"data.alerts[{idx}] 缺少字段 '{field}'"
        if alert["level"] not in VALID_LEVELS_ALERT:
            return False, f"data.alerts[{idx}].level 必须是 {VALID_LEVELS_ALERT} 之一，当前值: '{alert['level']}'"
        if not isinstance(alert["device"], str):
            return False, f"data.alerts[{idx}].device 必须是字符串"
        if not isinstance(alert["message"], str) or not alert["message"].strip():
            return False, f"data.alerts[{idx}].message 必须是非空字符串"

    return True, None


# ── 主入口 ──────────────────────────────────────────────────

def generate_decision_summary(prompt: str, agent) -> dict:
    """
    通过 ReAct Agent 执行完整 7 步决策分析链路（遵循 main_prompt.txt 模式一），
    从 Agent 最终输出中解析 JSON 并校验结构后返回。

    Agent 调用链路：
    soil_time_series_analysis → get_yiyuan_weather_forecast
    → judge_apple_phenological_period → rag_apple_knowledge_search
    → calculate_water_fertilizer_amount → decision_trace_explain
    → generate_decision_summary（工具，输出结构化JSON）

    Returns:
        {"code": 0, "data": {...}}  成功
        {"code": -1, "message": "..."}  失败
    """
    # 1. 通过 ReAct Agent 执行完整分析链路
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

    # 2. 从 Agent 最终输出中提取并解析 JSON
    raw_text = full_response
    try:
        # 兼容模型可能在 JSON 外层包裹 markdown 代码块的情况
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw_text)
        if json_match:
            raw_text = json_match.group(1).strip()
        result = json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.error(f"[decision_service] JSON解析失败: {e}\n原始响应前500字: {full_response[:500]}")
        return {"code": -1, "message": f"智能体返回格式异常，无法解析JSON: {str(e)}"}

    # 3. 校验响应结构
    is_valid, error_msg = validate_decision_response(result)
    if not is_valid:
        logger.error(f"[decision_service] 响应校验失败: {error_msg}\n数据前500字: {json.dumps(result, ensure_ascii=False)[:500]}")
        return {"code": -1, "message": f"响应格式校验失败: {error_msg}"}

    logger.info(f"[decision_service] 决策生成成功, summary={result.get('summary', '')[:80]}...")
    return {"code": 0, "data": result}
