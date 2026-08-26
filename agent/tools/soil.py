import json

import requests
from datetime import datetime, timedelta
from langchain_core.tools import tool

from agent.tools.common import _current_phenological_period
from utils.config_handler import apple_farming_conf
from utils.logger_handler import logger

# ============================================================
# 设备属性标识符映射
# ============================================================
DEVICE_IDENTIFIER_MAP = {
    "A": "PH值",
    "B": "土壤湿度",
    "C": "环境温度",
    "D": "环境湿度",
    "E": "光照",
    "F": "水泵/继电器状态",
    "G": "PH报警状态",
    "H": "土壤湿度报警状态",
    "I": "PH阈值低",
    "J": "PH阈值高",
    "K": "土壤湿度阈值低",
    "L": "土壤湿度阈值高",
    "M": "氮肥含量",
    "N": "氮肥含量",
    "O": "氮肥含量",
}

SOIL_CORE_IDENTIFIERS = ["A", "B", "G", "H", "I", "J", "K", "L","M","N","O"]


def _parse_time_range(time_range: str) -> tuple[int, int, str]:
    """将时间范围描述转换为起止毫秒时间戳"""
    now = datetime.now()
    end_ts = int(now.timestamp() * 1000)

    if "7天" in time_range:
        days = 7
    elif "30天" in time_range:
        days = 30
    elif "生育期" in time_range:
        period = _current_phenological_period()
        period_name = period["period_name"]
        period_start_offset = {
            "休眠期": 120, "萌芽期": 100, "花期": 80, "新梢生长期": 60,
            "膨果期": 40, "着色期": 20, "采收期": 10, "采后休眠期": 30,
        }
        days = period_start_offset.get(period_name, 60)
        return int((now - timedelta(days=days)).timestamp() * 1000), end_ts, f"本生育期（{period_name}）"
    else:
        days = 7

    return int((now - timedelta(days=days)).timestamp() * 1000), end_ts, f"近{days}天"


def _analyze_soil_trends(latest: dict, history: dict, time_label: str, device_name: str) -> dict:
    """基于最新数据和历史数据分析土壤趋势

    latest 数据结构（/api/latest）:
      {"device_name": "...", "data": {"A": {"value": "6.6", "time": ..., "name": "PH值", ...}, ...}}
    history 数据结构（/api/history/all）:
      {"device_name": "...", "properties": {"A": {"code": 0, "data": {"list": [{"time": ..., "value": "..."}, ...]}, ...}, ...}}
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    current_values = {}
    alarms = {}
    thresholds = {}
    latest_data = latest.get("data", {})
    for identifier in SOIL_CORE_IDENTIFIERS:
        prop = latest_data.get(identifier, {})
        if not prop:
            continue
        label = prop.get("name", DEVICE_IDENTIFIER_MAP.get(identifier, identifier))
        raw_val = prop.get("value", "")
        current_values[label] = raw_val

        if identifier in ("G", "H"):
            enum_desc = prop.get("enum_desc", {})
            alarms[label] = enum_desc.get(raw_val, raw_val)

        if identifier in ("I", "J", "K", "L"):
            thresholds[label] = raw_val

    trends = {}
    properties = history.get("properties", {}) if history else {}
    for identifier in SOIL_CORE_IDENTIFIERS:
        label = DEVICE_IDENTIFIER_MAP.get(identifier, identifier)
        prop_data = properties.get(identifier)

        if not isinstance(prop_data, dict) or prop_data.get("code") != 0:
            trends[label] = "无有效历史数据"
            continue

        points = prop_data.get("data", {}).get("list", [])
        if not points or len(points) < 2:
            trends[label] = "数据量不足，无法分析趋势"
            continue

        values = []
        for p in points:
            v = p.get("value") if isinstance(p, dict) else None
            if v is not None:
                try:
                    values.append(float(v))
                except (ValueError, TypeError):
                    pass

        if len(values) < 2:
            trends[label] = "有效数据点不足"
            continue

        first_val = values[0]
        last_val = values[-1]
        avg_val = sum(values) / len(values)
        change_pct = ((last_val - first_val) / first_val * 100) if first_val != 0 else 0

        if abs(change_pct) < 5:
            direction = "稳定"
        elif change_pct > 0:
            direction = "上升"
        else:
            direction = "下降"

        if identifier == "B":
            min_val = min(values)
            max_val = max(values)
            if min_val < 30:
                drought_risk = "存在干旱胁迫风险"
            elif min_val < 45:
                drought_risk = "湿度偏低，需关注"
            else:
                drought_risk = "湿度正常"
            trends[label] = (f"{direction}（变化{change_pct:+.1f}%），均值{avg_val:.1f}%，"
                             f"区间[{min_val:.0f}%-{max_val:.0f}%]，{drought_risk}")
        elif identifier == "A":
            trends[label] = (f"{direction}（变化{change_pct:+.1f}%），均值{avg_val:.2f}，"
                             f"苹果适宜pH区间6.0-6.5")
        else:
            trends[label] = f"{direction}（变化{change_pct:+.1f}%），均值{avg_val:.2f}"

    issues = []
    ph_str = current_values.get("PH值", "")
    try:
        ph_val = float(ph_str)
        if ph_val < 5.5:
            issues.append("土壤酸化严重，需增施石灰或土壤调理剂")
        elif ph_val < 6.0:
            issues.append("pH偏低，建议增施有机肥调理")
        elif ph_val > 7.5:
            issues.append("pH偏高，需注意铁锰元素有效性")
    except (ValueError, TypeError):
        pass

    moisture_str = current_values.get("土壤湿度", "")
    try:
        moisture_val = float(moisture_str)
        if moisture_val < 30:
            issues.append("土壤湿度严重不足，需立即灌溉")
        elif moisture_val < 45:
            issues.append("土壤湿度偏低，建议适时灌溉")
    except (ValueError, TypeError):
        pass

    if alarms.get("PH状态") == "报警":
        issues.append("PH报警触发，请检查阈值设置与实际pH值")
    if alarms.get("土壤湿度状态") == "异常":
        issues.append("土壤湿度报警触发，请检查阈值设置与实际湿度")

    return {
        "设备名称": device_name,
        "采集时间": now_str,
        "分析时间范围": time_label,
        "当前值": current_values,
        "报警状态": alarms,
        "阈值设置": thresholds,
        "历史趋势": trends,
        "综合问题判定": issues if issues else ["各项指标正常，无明显异常"],
        "数据来源": f"土壤设备API ({apple_farming_conf.get('soil_device_api', 'http://localhost:8086')})",
    }


@tool
def soil_time_series_analysis(device_name: str = "device", time_range: str = "近7天") -> str:
    """
    通过土壤设备API获取土壤指标（pH值、土壤湿度、温湿度、光照）的当前值与历史时序数据，分析趋势与异常。
    入参：device_name — 设备名称（可选，默认"device"，后续多地块扩展时传入具体设备名）；time_range — 时间范围（近7天/近30天/本生育期，默认近7天）。
    出参：JSON格式土壤当前数据、历史趋势分析、报警状态、阈值配置、综合问题判定。
    """
    logger.info(f"[Tool] soil_time_series_analysis 被调用, device_name={device_name}, time_range={time_range}")

    base_url = apple_farming_conf.get("soil_device_api", "http://localhost:8086")
    start_ts, end_ts, time_label = _parse_time_range(time_range)

    # 1. 获取设备最新数据
    latest_data = {}
    try:
        resp = requests.get(
            f"{base_url}/api/latest",
            params={"device_name": device_name},
            timeout=10,
        )
        if resp.status_code == 200:
            latest_data = resp.json()
            logger.info(f"[Tool] /api/latest 调用成功, device={device_name}")
        else:
            logger.warning(f"[Tool] /api/latest 返回 {resp.status_code}: {resp.text}")
            return json.dumps({
                "error": f"获取设备最新数据失败，HTTP {resp.status_code}",
                "detail": resp.text[:200],
            }, ensure_ascii=False)
    except requests.exceptions.ConnectionError:
        logger.exception(f"[Tool] 无法连接土壤设备API: {base_url}")
        return json.dumps({
            "error": f"无法连接土壤设备API（{base_url}），请确认服务是否启动",
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception(f"[Tool] 获取最新数据异常: {e}")
        return json.dumps({"error": f"获取最新数据异常: {str(e)}"}, ensure_ascii=False)

    if not latest_data:
        return json.dumps({
            "error": f"设备 '{device_name}' 无最新数据，请检查设备名称是否正确",
        }, ensure_ascii=False)

    # 2. 获取历史时序数据（所有属性）
    history_data = {}
    try:
        resp = requests.get(
            f"{base_url}/api/history/all",
            params={
                "device_name": device_name,
                "start": start_ts,
                "end": end_ts,
                "limit": 100,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            history_data = resp.json()
            logger.info(f"[Tool] /api/history/all 调用成功, 获取到 {len(history_data.get('properties', {}))} 个属性")
        else:
            logger.warning(f"[Tool] /api/history/all 返回 {resp.status_code}, 将仅基于当前值分析")
    except Exception as e:
        logger.warning(f"[Tool] 获取历史数据异常（将仅基于当前值分析）: {e}")

    # 3. 分析并输出
    result = _analyze_soil_trends(latest_data, history_data, time_label, device_name)
    return json.dumps(result, ensure_ascii=False, indent=2)
