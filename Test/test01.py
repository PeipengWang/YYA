import os
import sys
import requests
import logging

# 加载项目根目录 .env
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# ========== 配置（从 .env 读取）==========
HEFENG_API_KEY = os.getenv("HEFENG_API_KEY", "")
HEFENG_BASE_URL = os.getenv("HEFENG_BASE_URL", "https://n64nmvhn97.re.qweatherapi.com")


def get_location_id(city_name: str, adm: str = ""):
    """输入地名，返回 (location_id, 市名, 区县名)，失败返回 (None, None, None)"""
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


if __name__ == '__main__':
    res = get_location_id("沂源")
    print(res)
