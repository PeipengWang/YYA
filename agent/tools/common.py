from datetime import datetime

from rag.rag_service import RagSummarizeService
from utils.config_handler import apple_farming_conf

rag = RagSummarizeService()

# ============================================================
# 灌溉 / 施肥阈值规则（确定性读取，不走向量检索）
# ============================================================
# 阈值是要求精确的结构化事实，直接读配置，避免经过"语义召回 + 大模型归纳"后数值漂移。
# RAG 知识库只负责提供原理、操作方法与注意事项。
_IRRIGATION_RULES = apple_farming_conf.get("irrigation_rules", {})
_IRRIGATION_GLOBAL = _IRRIGATION_RULES.get("global", {})
_IRRIGATION_PERIODS = _IRRIGATION_RULES.get("periods", {})
_FERTILIZER_RULES = apple_farming_conf.get("fertilizer_rules", {})

# 膨果期内 6 月与 7~8 月的水分管理方向相反，按月份选择子期
_BULK_SUB_PERIOD_BY_MONTH = {6: "花芽分化期", 7: "果实迅速膨大期", 8: "果实迅速膨大期"}


def get_irrigation_rule(period_name: str, when: datetime = None) -> dict:
    """按物候期名称读取灌溉规则。

    :param period_name: 物候期名称，如「膨果期」
    :param when: 当前日期，用于在膨果期内判定子期（6 月控水 / 7~8 月需水高峰）
    :return: 该物候期的灌溉规则字典，含 moisture_lower、moisture_upper、drip、taboo 等
    """
    rule = _IRRIGATION_PERIODS.get(period_name)
    if not rule:
        return {}

    rule = dict(rule)
    sub_periods = rule.pop("sub_periods", None)

    if sub_periods and when is not None:
        sub_key = _BULK_SUB_PERIOD_BY_MONTH.get(when.month)
        sub = sub_periods.get(sub_key) if sub_key else None
        if sub:
            rule["当前子期"] = sub_key
            rule["moisture_lower"] = sub.get("moisture_lower", rule.get("moisture_lower"))
            rule["moisture_upper"] = sub.get("moisture_upper", rule.get("moisture_upper"))
            rule["推荐定额"] = sub.get("drip", rule.get("drip"))
        rule["可选子期"] = sub_periods

    return rule


def get_irrigation_global() -> dict:
    """返回灌溉全局规则（含水量基准、触发规则、灌溉时段、防涝要求等）"""
    return _IRRIGATION_GLOBAL


def get_fertilizer_rules() -> dict:
    """返回施肥量化规则"""
    return _FERTILIZER_RULES

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
        # 阈值来自 config/apple_farming.yml，确定性读取，不经过向量检索
        "irrigation_rule": get_irrigation_rule(name, now),
        "irrigation_global": get_irrigation_global(),
    }
