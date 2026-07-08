from agent.tools.weather import get_yiyuan_weather_forecast
from agent.tools.soil import soil_time_series_analysis
from agent.tools.agri_tools import (
    rag_apple_knowledge_search,
    judge_apple_phenological_period,
    calculate_water_fertilizer_amount,
    decision_trace_explain,
    generate_decision_summary,
)

farming_tool_list = [
    get_yiyuan_weather_forecast,
    soil_time_series_analysis,
    rag_apple_knowledge_search,
    judge_apple_phenological_period,
    calculate_water_fertilizer_amount,
    decision_trace_explain,
    generate_decision_summary,
]
