from datetime import datetime

from rag.rag_service import RagSummarizeService

rag = RagSummarizeService()

# ============================================================
# 沂源苹果物候期映射表
# ============================================================
PHENOLOGICAL_PERIODS = {
    1: ("休眠期", "11月下旬-2月下旬", "树体休眠，养分回流，冬剪整形，清园防病虫"),
    2: ("萌芽期", "3月上旬-3月下旬", "根系开始活动，花芽萌动，需补氮促芽，防倒春寒"),
    3: ("花期", "4月上旬-4月下旬", "开花坐果关键期，忌大水漫灌，需硼肥促花，防霜冻"),
    4: ("新梢生长期", "5月上旬-6月上旬", "新梢旺长，需氮磷钾均衡供应，疏果定果，防蚜虫红蜘蛛"),
    5: ("膨果期", "6月中旬-8月下旬", "果实快速膨大，需高钾低氮，保证水分供应，防伏旱连阴雨"),
    6: ("着色期", "9月上旬-9月下旬", "增糖着色关键期，需控氮增钾，增大昼夜温差，防后期病害"),
    7: ("采收期", "10月上旬-10月下旬", "适时采收，采后补肥恢复树势，清园防越冬病虫"),
    8: ("采后休眠期", "11月上旬-11月中旬", "秋施基肥，浇封冻水，树干涂白，防冬季冻害"),
}


def _current_phenological_period() -> dict:
    """根据当前日期判定沂源苹果物候期"""
    now = datetime.now()
    month = now.month
    day = now.day

    if month == 1 or month == 2 or (month == 11 and day >= 20) or (month == 3 and day < 10):
        period_id = 1
    elif (month == 3 and day >= 10) or (month == 4 and day < 5):
        period_id = 2
    elif (month == 4 and day >= 5) or (month == 5 and day < 5):
        period_id = 3
    elif (month == 5 and day >= 5) or (month == 6 and day < 15):
        period_id = 4
    elif (month == 6 and day >= 15) or month == 7 or month == 8:
        period_id = 5
    elif month == 9:
        period_id = 6
    elif month == 10 and day < 20:
        period_id = 7
    elif (month == 10 and day >= 20) or (month == 11 and day < 20):
        period_id = 8
    else:
        period_id = 1

    name, date_range, core_needs = PHENOLOGICAL_PERIODS[period_id]
    return {
        "period_id": period_id,
        "period_name": name,
        "date_range": date_range,
        "core_needs": core_needs,
    }
