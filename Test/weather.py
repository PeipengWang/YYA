import os
import sys
import requests
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from langchain.tools import tool

# 加载项目根目录 .env
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

# ========== 配置区（密钥从 .env 读取，URL 从环境变量或 YAML 读取）==========
HEFENG_API_KEY = os.getenv("HEFENG_API_KEY", "")
HEFENG_BASE_URL = os.getenv("HEFENG_BASE_URL", "https://n64nmvhn97.re.qweatherapi.com")
logger = logging.getLogger(__name__)


def get_location_id(city_name: str, adm: str = ""):
    """输入地名，返回城市 location ID，失败返回 (None, None, None)"""
    url = f"{HEFENG_BASE_URL}/geo/v2/city/lookup"
    headers = {
        "accept": "application/json",
        "X-QW-Api-Key": HEFENG_API_KEY,
    }
    params = {
        "location": city_name,
        "adm": adm,
        "range": "cn",
        "number": 10,
        "lang": "zh",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=8)
        data = resp.json()
        if data.get("code") == "200" and len(data.get("location", [])) > 0:
            loc = data["location"][0]
            return loc["id"], loc.get("adm2", ""), loc["name"]
        return None, None, None
    except Exception as e:
        logger.error(f"地名解析失败: {str(e)}")
        return None, None, None


def get_7day_forecast(loc_id: str) -> list:
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
        logger.error(f"7天预报获取失败: {str(e)}")
        return []


def get_weather_warning(loc_id: str) -> list:
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
        logger.error(f"气象预警获取失败: {str(e)}")
        return []


@tool
def get_agri_weather_by_location(location: str) -> str:
    """
    根据省市/区县地名，获取当地未来7天精细化气象预报与官方农业气象灾害预警。
    入参：location — 完整地区名称，例如：沂源县、淄博市沂源县
    出参：JSON格式每日温湿度、降水、风力、霜冻/暴雨/大风预警、农事提示
    """
    logger.info(f"[和风天气工具] 查询地区：{location}")

    # 解析省市层级：先尝试完整名称，再尝试简化
    adm_parts = location.replace("市", " ").replace("县", " ").replace("区", " ").split()
    city = adm_parts[0] if len(adm_parts) > 0 else location
    adm = adm_parts[1] if len(adm_parts) > 1 else ""

    loc_id, adm2, name = get_location_id(location, adm)
    if not loc_id:
        # 降级：只用城市名再试一次
        loc_id, adm2, name = get_location_id(city, "")
    if not loc_id:
        return json.dumps({"error": f"无法识别地区：{location}，请输入完整省市县名称"}, ensure_ascii=False)

    daily_list = get_7day_forecast(loc_id)
    warning_list = get_weather_warning(loc_id)

    if not daily_list:
        return json.dumps({"error": "气象预报接口请求失败"}, ensure_ascii=False)

    forecast_7d = []
    for day in daily_list:
        forecast_7d.append({
            "日期": day.get("fxDate", ""),
            "白天天气": day.get("textDay", ""),
            "夜间天气": day.get("textNight", ""),
            "最高温_℃": day.get("tempMax", ""),
            "最低温_℃": day.get("tempMin", ""),
            "降水概率_%": day.get("pop", ""),
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

    display_city = adm2 or city
    display_name = name or location
    result = {
        "查询地区": f"{display_city}{display_name}",
        "数据更新时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "未来7天气象预报": forecast_7d,
        "官方气象灾害预警": warn_data if warn_data else ["当前无灾害预警"],
        "农事提示": "降雨量大时果园及时排水，低温霜冻前做好果树保温，大风前加固果树支架",
        "数据来源": "和风天气-中国气象局气象数据",
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


# 本地测试
if __name__ == "__main__":
    # 1. 测试地名解析
    print("=== 地名解析测试 ===")
    loc_id, city, name = get_location_id("沂源", "zibo")
    print(f"Location ID: {loc_id}, City: {city}, Name: {name}")

    # 2. 测试完整工具
    print("\n=== 完整天气查询测试 ===")
    res = get_agri_weather_by_location.invoke({"location": "沂源县"})
    print(res)
