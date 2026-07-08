import os
import json

import requests
from datetime import datetime
from langchain_core.tools import tool

from utils.config_handler import apple_farming_conf
from utils.logger_handler import logger

# ============================================================
# 和风天气 API 配置（密钥从 .env 读取，URL/地名从 YAML 配置读取）
# ============================================================
HEFENG_API_KEY = os.getenv("HEFENG_API_KEY", "")
HEFENG_BASE_URL = os.getenv("HEFENG_BASE_URL", "")
DEFAULT_WEATHER_LOCATION = apple_farming_conf.get("default_weather_location", "沂源县")


def _get_location_id(city_name: str, adm: str = ""):
    """输入地名，返回 (location_id, 市名, 区县名)，失败返回 (None, None, None)"""
    url = f"{HEFENG_BASE_URL}/geo/v2/city/lookup"
    headers = {"accept": "application/json", "X-QW-Api-Key": HEFENG_API_KEY}
    params = {"location": city_name, "adm": adm, "range": "cn", "number": 10, "lang": "zh"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=8)
        data = resp.json()
        if data.get("code") == "200" and len(data.get("location", [])) > 0:
            loc = data["location"][0]
            return loc["id"], loc.get("adm2", ""), loc["name"]
        return None, None, None
    except Exception as e:
        logger.error(f"[和风天气] 地名解析失败: {e}")
        return None, None, None


def _get_7day_forecast(loc_id: str) -> list:
    """获取7天天气预报"""
    url = f"{HEFENG_BASE_URL}/v7/weather/7d"
    headers = {"X-QW-Api-Key": HEFENG_API_KEY}
    params = {"location": loc_id}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        data = resp.json()
        if data.get("code") == "200":
            return data.get("daily", [])
        return []
    except Exception as e:
        logger.error(f"[和风天气] 7天预报获取失败: {e}")
        return []


def _get_weather_warning(loc_id: str) -> list:
    """获取实时气象灾害预警"""
    url = f"{HEFENG_BASE_URL}/v7/warning/now"
    headers = {"X-QW-Api-Key": HEFENG_API_KEY}
    params = {"location": loc_id}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        data = resp.json()
        if data.get("code") == "200":
            return data.get("warning", [])
        return []
    except Exception as e:
        logger.error(f"[和风天气] 气象预警获取失败: {e}")
        return []


@tool
def get_yiyuan_weather_forecast(location: str = "沂源县") -> str:
    """
    根据地点名称获取当地未来7天精细化气象预报与农业气象灾害预警。
    入参：location — 地名（如：沂源县、淄博市、济南），默认"沂源县"。
    出参：JSON格式未来7天逐日天气/温湿度/降水/风力/气象灾害预警/农事提示。
    """
    logger.info(f"[Tool] get_yiyuan_weather_forecast 被调用, location={location}")

    loc_id, city, name = _get_location_id(location)
    if not loc_id:
        loc_id, city, name = _get_location_id(location.replace("县", "").replace("市", "").replace("区", ""))
    if not loc_id:
        return json.dumps({"error": f"无法识别地区：{location}，请输入完整省市县名称"}, ensure_ascii=False)

    daily_list = _get_7day_forecast(loc_id)
    warning_list = _get_weather_warning(loc_id)

    if not daily_list:
        return json.dumps({"error": "气象预报接口请求失败，请稍后重试"}, ensure_ascii=False)

    forecast_7d = []
    for day in daily_list:
        forecast_7d.append({
            "日期": day.get("fxDate", ""),
            "白天天气": day.get("textDay", ""),
            "夜间天气": day.get("textNight", ""),
            "最高温_℃": day.get("tempMax", ""),
            "最低温_℃": day.get("tempMin", ""),
            "降水量_mm": day.get("precip", ""),
            "白天风力风向": f"{day.get('windDirDay', '')} {day.get('windScaleDay', '')}级",
        })

    warn_data = []
    for warn in warning_list:
        warn_data.append({
            "预警类型": warn.get("typeName", ""),
            "预警等级": warn.get("level", ""),
            "发布时间": warn.get("pubTime", ""),
            "预警详情": warn.get("text", ""),
        })

    display_city = city or location
    display_name = name or location
    result = {
        "查询地区": f"{display_city}{display_name}" if display_city != display_name else display_city,
        "数据更新时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "未来7天气象预报": forecast_7d,
        "气象灾害预警": warn_data if warn_data else ["当前无灾害预警"],
        "农事提示": "降雨量大时果园及时排水，低温霜冻前做好果树保温，大风前加固果树支架",
        "数据来源": "和风天气-中国气象局气象数据",
    }
    return json.dumps(result, ensure_ascii=False, indent=2)
