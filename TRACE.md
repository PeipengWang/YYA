# 变更追踪

## 项目概述

**项目名称**：沂源苹果智能农事助手（小沂）

**技术栈**：
- 后端：FastAPI (port 8001) + LangChain/LangGraph ReAct Agent
- 模型：DeepSeek Chat（通过 `model/factory.py`）+ DashScope Embedding
- 知识库：ChromaDB 向量数据库 + RAG 检索（`rag/rag_service.py`）
- 语音：TTS 服务 (port 9000) + ASR 服务 (port 9001)
- 设备数据：土壤传感器 MQTT → REST API (port 8086)
- 前端：单页 HTML（`static/index.html`），SSE 流式对话 + Markdown 渲染

**核心能力**：面向沂源山地苹果种植的智能农事决策，覆盖物候期判定、微气象采集、土壤分析、天气预判、水肥量化、决策溯源 7 大工具。

**目录结构**：
```
YAA/
├── api_server.py          # FastAPI 主服务
├── agent/
│   ├── react_agent.py     # ReAct Agent 定义
│   └── tools/
│       ├── agent_tools.py # 7 个农事决策工具
│       ├── middleware.py  # Agent 中间件（监控/日志/摘要）
│       └── music_tools.py # 音乐播放工具（未启用）
├── config/
│   ├── agent.yml          # Agent 配置
│   ├── apple_farming.yml  # 农事接口与属地参数配置
│   ├── chroma.yml         # ChromaDB 配置
│   ├── prompts.yml        # 提示词配置
│   └── rag.yml            # RAG 与音乐服务配置
├── model/
│   └── factory.py         # ChatModel / Embedding / Checkpointer 工厂
├── rag/
│   └── rag_service.py     # RAG 检索与摘要服务
├── prompts/
│   ├── main_prompt.txt    # 系统提示词
│   └── main_prompt2.txt   # 系统提示词（v2）
├── static/
│   └── index.html         # 前端 SPA
├── utils/
│   ├── config_handler.py  # 配置加载器
│   ├── logger_handler.py  # 日志
│   ├── music_utils.py     # 本地音乐扫描
│   ├── path_tool.py       # 路径工具
│   └── prompt_loader.py   # 提示词加载器
└── nginx.conf             # Nginx 反向代理配置
```

---

## 变更记录

### 2026-07-07：删除前端音乐播放功能

**原因**：当前接口（`api_server.py`）不提供音乐播放相关端点，音乐功能依赖的外部服务（port 9002 / port 8006）未在当前 API 中暴露，前端保留音乐播放能力会造成功能不可用。

**变更文件**：
- `static/index.html`：
  - 删除 CSS 变量 `--music-bg` / `--music-hover`
  - 删除 `.music-float-btn` 悬浮按钮样式
  - 删除 HTML 音乐停止按钮 `#musicStopBtn`
  - 删除 JS 全局变量：`musicWs`, `playMusicAudio`, `currentMusicPath`, `MUSIC_WS_URL`, `MUSIC_STREAM_BASE`
  - 删除 JS 函数：`initMusicWebSocket()`, `playMusic()`, `localStopMusic()`, `stopMusicAudio()`
  - 删除 `DOMContentLoaded` 中的 `initMusicWebSocket()` 调用
- **保留**：TTS 语音播报（`playTTS()` → port 9000）和 ASR 语音识别（`/api/asr` → port 9001）

---

### 2026-07-07：重构 soil_time_series_analysis 工具

**原因**：原工具使用模拟数据（mock），需对接真实土壤设备 API 获取传感器数据。

**设备 API 参考**：`获取土壤环境接口文档.md`（服务地址 `http://localhost:8086`）

**设备属性映射**（identifier → 中文含义）：
| 标识符 | 含义 | 数据类型 |
|--------|------|----------|
| A | PH值 | float |
| B | 土壤湿度 | int32 (0-100%) |
| C | 环境温度 | int32 |
| D | 环境湿度 | int32 |
| E | 光照 | int32 (lux) |
| F | 水泵/继电器状态 | enum |
| G | PH报警状态 | enum |
| H | 土壤湿度报警状态 | enum |
| I | PH阈值低 | string |
| J | PH阈值高 | string |
| K | 土壤湿度阈值低 | string |
| L | 土壤湿度阈值高 | string |

**变更文件**：
- `config/apple_farming.yml`：
  - 删除模拟桩配置 `soil_timeseries_api: http://127.0.0.1:9003/api/soil/timeseries`
  - 新增真实配置 `soil_device_api: http://localhost:8086`（标注参考文档）
- `agent/tools/agent_tools.py`：
  - 新增 `import requests` 和 `from datetime import timedelta`
  - 新增常量 `DEVICE_IDENTIFIER_MAP`（属性标识符→中文含义映射表）
  - 新增常量 `SOIL_CORE_IDENTIFIERS`（土壤分析核心属性列表）
  - 新增函数 `_parse_time_range(time_range)`：将"近7天/近30天/本生育期"转换为毫秒时间戳，本生育期根据物候期自动估算起始偏移
  - 新增函数 `_analyze_soil_trends(latest, history, time_label, device_name)`：综合当前值与历史数据分析趋势，输出 pH/湿度专项评估、报警状态、综合问题判定
  - 重写 `soil_time_series_analysis(device_name, time_range)`：
    - 入参变更：新增 `device_name`（必填），`time_range` 改为默认"近7天"
    - 调用 `GET /api/latest?device_name=xxx` 获取当前传感器数据
    - 调用 `GET /api/history/all?device_name=xxx&start=...&end=...&limit=100` 获取历史时序数据
    - 完善的错误处理：连接失败、HTTP 错误、空数据均有独立返回
- `prompts/main_prompt.txt` 和 `prompts/main_prompt2.txt`：
  - 更新工具描述，入参增加 `device_name`，出参反映真实 API 能力（pH/湿度/温湿度/光照/报警/阈值）

**设计要点**：
- 历史趋势分析采用首尾对比法：计算变化百分比，判断上升/下降/稳定方向，输出均值
- 土壤湿度特殊处理：输出 min/max 区间，低于 30% 判定干旱胁迫，低于 45% 提示关注
- pH 分析结合苹果适宜区间 6.0-6.5 给出偏离建议
- 报警状态与阈值配置一并返回，便于决策溯源

---

### 2026-07-07：soil_time_series_analysis 设备参数改为可选

**原因**：当前仅有 "device" 一个土壤设备，后续按地块扩展时再传入具体设备名。将 `device_name` 从必填改为可选可简化当前调用，同时保留扩展能力。

**变更文件**：
- `agent/tools/agent_tools.py`：`device_name` 默认值设为 `"device"`
- `prompts/main_prompt.txt`：入参描述改为"可选，默认'device'"
- `prompts/main_prompt2.txt`：同上

---

### 2026-07-07：修复 _analyze_soil_trends 以适配真实 API 响应结构

**原因**：`获取土壤环境接口文档.md` 补充了 `/api/latest` 和 `/api/history/all` 的真实 JSON 响应实例，原代码的数据解析逻辑与真实响应结构不匹配。

**响应结构对照**：
- `/api/latest`：`{"device_name": "...", "data": {"A": {"value": "6.6", "time": ..., "name": "PH值", "unit": "", ...}, ...}}`
  - `data` 以标识符（A/B/C...）为 key，非中文名称
- `/api/history/all`：`{"device_name": "...", "properties": {"A": {"code": 0, "data": {"list": [{"time": ..., "value": "..."}, ...]}}, ...}}`
  - 历史数据路径为 `properties.{identifier}.data.list`，非直接 `history[identifier]`

**修复内容**（`agent/tools/agent_tools.py`）：
- `_analyze_soil_trends` 函数：
  - **latest 解析修复**：`latest["data"][identifier]["value"]` 替代原来的 `latest["data"][label]["value"]`（key 从中文名改为标识符）
  - **history 解析修复**：`history["properties"][identifier]["data"]["list"]` 替代原来的 `history[identifier]`，增加 `code != 0` 错误状态检查
  - **报警状态解析修复**：从 latest 的 `enum_desc` 字典正确提取（G=PH状态, H=土壤湿度状态），替代原来空字典未赋值
  - **阈值解析修复**：新增 I/J/K/L 阈值提取逻辑，替代原来注释掉的占位代码
  - **综合判定修复**：所有 value 为字符串类型，增加 `float()` 转换后再比较；报警判定适配 `enum_desc` 的中文值（"报警"/"异常"）
  - **返回值**：恢复之前被注释的字段——报警状态、阈值设置、综合问题判定、数据来源
- `soil_time_series_analysis`：
  - 日志修复：`len(history_data)` → `len(history_data.get('properties', {}))`，适配 dict 结构

---

### 2026-07-07：修复前端 Markdown 渲染乱码与 SSE 流式发送

**原因**：智能体输出包含大量 Markdown 结构（代码块、引用块、列表、标题、加粗等），前端手写正则解析器仅支持 `#`/`**`/`*`/`---` 四种语法，导致其余 Markdown 标记符直接显示为乱码文本。SSE 流式接口仅发送最后一条 chunk，前端无法渐进展示。

**根因分析**：
| 问题 | 位置 | 说明 |
|------|------|------|
| SSE 仅发最终块 | `api_server.py` event_generator | `for` 循环收集 `last_chunk`，循环结束后才 yield 一次 |
| Markdown 解析器残缺 | `index.html` markdownToHtml | 缺少代码块、引用、有序列表、内联代码、表格等处理 |
| CSS 样式缺失 | `index.html` .msg 样式区 | 代码块无深色背景、引用无左边框、表格无边框等 |

**修复内容**：
- `api_server.py`：
  - SSE event_generator 改为逐块计算增量（`delta = chunk[len(full_response):]`），每个 delta 实时 yield
- `static/index.html`：
  - 引入 `marked.js` CDN（`cdn.jsdelivr.net/npm/marked`）替代手写正则，支持完整 GFM 语法
  - 配置 `marked.setOptions({ breaks: true, gfm: true })`
  - CSS 新增：`blockquote` 左边框+浅绿背景、`pre > code` 深色代码块、`code` 行内灰底、`table` 表格边框、`th/td` 表头样式、`a` 链接色
  - 保留原有 `h1-h3`/`p`/`ul/ol`/`strong`/`em`/`hr` 样式并微调间距

---

### 2026-07-07：修复 SSE 流式返回用户提问的 bug

**原因**：`react_agent.py` 的 `execute_stream` 使用 `stream_mode="values"` 时，第一个 chunk 中的 `messages[-1]` 是用户刚发送的 HumanMessage，其 `content` 即用户提问本身。上轮修改中 `api_server.py` 的增量计算条件 `chunk.startswith("")` 始终为 true，导致用户提问被作为第一个 delta 发送到前端并显示在 AI 气泡中。

**修复内容**：
- `agent/react_agent.py`：
  - 增加消息类型过滤：`latest_message.type == "ai"`，仅输出 AI 生成的思考/回复，跳过 HumanMessage 和 ToolMessage
- `api_server.py`：
  - 移除 `startswith` 增量计算逻辑（ReAct 模式下每个 AI 消息是独立片段，非累积文本）
  - 改为直接 yield 每个 AI 消息 chunk，由前端累积拼接

---

### 2026-07-08：气象工具从模拟桩迁移到和风天气真实 API

**原因**：`get_yiyuan_weather_forecast` 原来使用硬编码模拟数据，无法反映真实气象情况。用户已在 `Test/weather.py` 中验证了和风天气 API 的 `get_location_id` 地名解析功能，现将其扩展到完整的 7 天预报 + 灾害预警链路。

**API 调用链**：
1. `_get_location_id(city_name, adm)` → 和风天气城市地理编码 `/geo/v2/city/lookup`，返回 location ID
2. `_get_7day_forecast(loc_id)` → 和风天气 7 天预报 `/v7/weather/7d`
3. `_get_weather_warning(loc_id)` → 和风天气灾害预警 `/v7/warning/now`

**变更文件**：
- `config/apple_farming.yml`：
  - 删除 `yiyuan_weather_api: http://127.0.0.1:9003/api/weather`
  - 新增 `hefeng_api_key`、`hefeng_base_url`、`default_weather_location: "沂源县"`
- `agent/tools/agent_tools.py`：
  - 新增 `HEFENG_API_KEY` / `HEFENG_BASE_URL` / `DEFAULT_WEATHER_LOCATION` 常量（从配置读取）
  - 新增 `_get_location_id(city_name, adm)` — 地名→和风 location ID 解析
  - 新增 `_get_7day_forecast(loc_id)` — 7 天逐日天气预报
  - 新增 `_get_weather_warning(loc_id)` — 实时气象灾害预警
  - 重写 `get_yiyuan_weather_forecast`：
    - **入参变更**：`query: str` → `location: str = "沂源县"`，支持任意中国地名
    - 实际调用和风天气 API 三阶段链路，完善错误处理与降级策略
    - 出参格式化：日期/天气/最高最低温/降水量/风力风向/灾害预警/农事提示
- `prompts/main_prompt.txt`：
  - 更新工具描述：入参改为 `location`，注明支持任意中国地名，标注"对接和风天气API"
- `Test/weather.py`：
  - 解除注释并修正 `get_7day_forecast` / `get_weather_warning` API key 传递方式（统一使用 header `X-QW-Api-Key`）
  - 完成 `get_agri_weather_by_location` LangChain `@tool` 函数
  - 新增完整本地测试入口

---

### 2026-07-08：配置拆分 — 密钥入 .env，配置入 YAML

**原因**：API Key、域名、端口、默认城市名等散落在代码和配置中，不利于部署切换与安全管理。按"密钥类到 .env、配置类到 YAML"原则全面拆分。

**拆分原则**：
| 类型 | 去向 | 示例 |
|------|------|------|
| API Key / Token | `.env` | DEEPSEEK_API_KEY, HEFENG_API_KEY |
| 第三方基础 URL | `.env` | HEFENG_BASE_URL, DASHSCOPE_BASE_URL |
| 服务端口 | `.env` | API_SERVER_PORT |
| 业务配置（城市/阈值/物候期） | YAML | default_weather_location, soil_types |
| 本地服务地址 | YAML | TTS_URL, ASR_API_URL, soil_device_api |

**变更文件**：
- `.env`：
  - 新增注释分组，补充 `HEFENG_BASE_URL`、`API_SERVER_PORT`
- `.env.example`（新增）：
  - 脱敏模板文件，所有密钥替换为 `your-xxx-key` 占位符，供新开发者复制使用
- `.gitignore`：
  - 修复 `.env` 忽略规则（`./.env` → `.env`）
- `config/apple_farming.yml`：
  - **删除** `hefeng_api_key`（密钥已迁移到 .env）
  - **保留** `hefeng_base_url` 注释说明（实际读取改为 .env 的 `HEFENG_BASE_URL`）
- `config/rag.yml`：
  - **精简**：删除 `FIELD_MICROCLIMATE_API`/`YIYUAN_WEATHER_API`/`SOIL_TIMESERIES_API`/`WATER_FERTILIZER_API`（与 apple_farming.yml 重复的模拟桩地址）
  - **保留** TTS/ASR/MUSIC 服务地址
- `utils/config_handler.py`：
  - 新增 `from dotenv import load_dotenv` + `load_dotenv()`，确保全局任何模块导入时 `.env` 已加载
- `agent/tools/agent_tools.py`：
  - `HEFENG_API_KEY` → `os.getenv("HEFENG_API_KEY")`
  - `HEFENG_BASE_URL` → `os.getenv("HEFENG_BASE_URL")`
  - `DEFAULT_WEATHER_LOCATION` → 仅从 YAML 读取（`apple_farming_conf.get("default_weather_location")`）
- `api_server.py`：
  - 端口 → `os.getenv("API_SERVER_PORT", "8001")`
- `Test/weather.py`、`Test/test01.py`：
  - API key 改为 `os.getenv("HEFENG_API_KEY")`，URL 改为 `os.getenv("HEFENG_BASE_URL")`
  - 新增 `load_dotenv()` 调用

---

### 2026-07-08：前端只回复最终结论，隐藏 ReAct 思考过程

**原因**：ReAct Agent 的思考-行动-观察循环会产生多条 AI 消息（含工具调用），前端会逐条展示"我需要调用XX工具..."等思考过程，用户体验差。需只输出不带工具调用的最终结论。

**实现方式**：在 `react_agent.py` 的 `execute_stream` 中通过 LangChain `AIMessage.tool_calls` 属性过滤：
- `tool_calls` 非空 → 思考/行动消息，**跳过不输出**
- `tool_calls` 为空 → 最终结论，**正常输出**

**变更文件**：
- `agent/react_agent.py`：
  - 新增 `getattr(latest_message, "tool_calls", None)` 检查
  - 增加条件 `if not tool_calls` 过滤带工具调用的思考消息
  - 影响范围：`execute_stream()` 仅 yield 最终结论，`/api/chat/stream` 和 `/api/chat/send` 均自动生效

---

### 2026-07-08：拆分 agent_tools.py（602行 → 5个模块）

**原因**：`agent_tools.py` 单文件达 602 行，包含 7 个工具 + 天气/土壤 helper + 物候期映射 + RAG 实例，职责混杂难以维护。

**拆分方案（按功能内聚）**：

```
agent/tools/
├── __init__.py          # 聚合导出 farming_tool_list（15行）
├── common.py            # 物候期映射/判定 + RAG 实例（55行）
├── weather.py           # 和风天气：helper×3 + tool（110行）
├── soil.py              # 土壤设备：标识符映射 + helper×2 + tool（250行）
├── agri_tools.py        # 其余5个工具：微气象/物候/RAG/水肥/溯源（145行）
└── agent_tools.py       # 向后兼容层，仅 re-export（30行）
```

**依赖关系**：
- `common.py` → 无内部依赖
- `weather.py` → 无内部依赖
- `soil.py` → 依赖 `common._current_phenological_period`
- `agri_tools.py` → 依赖 `common.rag` + `common._current_phenological_period`

**变更文件**：
- `agent/tools/common.py`（新增）：`PHENOLOGICAL_PERIODS`、`_current_phenological_period()`、`rag` 实例
- `agent/tools/weather.py`（新增）：和风天气配置常量、`_get_location_id/_get_7day_forecast/_get_weather_warning`、`get_yiyuan_weather_forecast`
- `agent/tools/soil.py`（新增）：`DEVICE_IDENTIFIER_MAP`、`SOIL_CORE_IDENTIFIERS`、`_parse_time_range`、`_analyze_soil_trends`、`soil_time_series_analysis`
- `agent/tools/agri_tools.py`（新增）：`get_field_microclimate`、`rag_apple_knowledge_search`、`judge_apple_phenological_period`、`calculate_water_fertilizer_amount`、`decision_trace_explain`
- `agent/tools/__init__.py`：从各子模块导入工具，组装 `farming_tool_list`
- `agent/tools/agent_tools.py`：重写为向后兼容 re-export 层（所有旧 `from agent.tools.agent_tools import X` 仍有效）
- `agent/react_agent.py`：导入路径从 `agent.tools.agent_tools` 改为 `agent.tools`

---

### 2026-07-08：删除前端会话管理侧边栏及后端会话接口

**原因**：当前系统无需多会话管理功能，前端侧边栏占用 300px 空间且会话管理 API 无实际业务需求。

**变更文件**：

- `static/index.html`：
  - **删除 CSS**：`.sidebar`、`.sidebar h3`、`.sidebar .divider`、`.sidebar input/sidebar select`、`.btn`、`.btn-outline`、`.session-id`、`.menu-toggle`、响应式侧边栏媒体查询
  - **删除 CSS 变量**：`--sidebar-bg`、`--radius-sm`
  - **修改 CSS**：`.main` 移除 `margin-left: 300px`
  - **删除 HTML**：`<button class="menu-toggle">`、整个 `<aside class="sidebar">` 元素
  - **删除 JS 函数**：`toggleSidebar()`、`loadSessions()`、`createSession()`、`switchSession()`、`renameSession()`、`updateSessionIdDisplay()`、`clearMessages()`
  - **删除 JS 变量**：`currentSession` → 不再需要，API 调用不再发送 `session_name`
  - **简化 API 调用**：`sendMessage()` 和 `sendMessageWithText()` 的 body 不再包含 `session_name`

- `api_server.py`：
  - **删除** `sessions` 全局字典
  - **删除** 4 个会话管理端点：`GET /api/sessions`、`POST /api/sessions`、`PUT /api/sessions/rename`
  - **删除** `chat/send` 和 `chat/stream` 中的 `session_name`/`thread_id` 参数处理
  - **删除** 未使用的 imports：`uuid`、`Form`、`UploadFile`、`File`、`requests`
  - **删除** 未使用的 `ASR_API_URL` 配置引用

---

### 2026-07-08：新增 POST /api/decision/summary 决策摘要接口

**原因**：前端决策页面需要结构化决策建议接口，规范定义在 `决策页面接口规范.md`。

**架构演进**：
- 初版：`decision_service.py` 自行获取传感器数据 + 自定义 `_DECISION_SYSTEM_PROMPT` + 直接调 `chat_model.invoke()` 生成 JSON
- 当前版：删除自定义 Prompt 和直接 LLM 调用，改为通过 ReAct Agent 走 `main_prompt.txt` 模式一（7步完整链路），Agent 的 `generate_decision_summary` 工具在链路末尾生成结构化 JSON 作为最终输出，`decision_service.py` 从中解析 JSON 并校验

**变更文件**：
- `agent/decision_service.py`：
  - **保留** `validate_decision_response()` — 逐字段校验响应结构（类型/必填/枚举值），不通过则拒绝返回
  - **重写** `generate_decision_summary(prompt, agent)` — 通过 ReAct Agent 执行完整分析链路 → 从最终输出解析 JSON → 校验 → 返回 `{code, data}`
  - **删除** `_DECISION_SYSTEM_PROMPT`、`_build_user_prompt()`、`_fetch_sensor_data()`、`_format_sensor_context()`、所有直接 LLM 调用逻辑
  - **删除** 未使用的 imports：`requests`、`datetime`、`HumanMessage`/`SystemMessage`、`chat_model`、`_current_phenological_period`、`DEVICE_IDENTIFIER_MAP`、`apple_farming_conf`
- `api_server.py`：
  - 新增 `POST /api/decision/summary` 端点
  - 接收 `{"prompt": "..."}`，参数为空返回 code=-2，分析失败返回 code=-1
  - 调用 `generate_decision_summary(prompt.strip(), agent)` 传入全局 agent 实例

---

### 2026-07-08：新增 generate_decision_summary 工具（第7个Agent工具）

**原因**：需要作为 ReAct Agent 的可用工具，在工具调用链末尾汇总所有前置分析结果，调用大模型生成符合前端接口规范的结构化 JSON 响应（summary/advices/problematicSensors/alerts），替代原来 `decision_service.py` 中直接调用 chat_model 的方式。

**变更文件**：
- `agent/tools/agri_tools.py`：
  - 新增 `generate_decision_summary(context)` — LangChain `@tool`，接收整合所有前置工具结果的综合分析文本，调用 `chat_model.invoke()` 生成结构化决策 JSON
  - 复用已有 imports（`json`/`tool`/`chat_model`/`logger`）
- `agent/tools/__init__.py`：导出 `generate_decision_summary`，加入 `farming_tool_list`（共7个工具）
- `agent/react_agent.py`：导入并注册 `generate_decision_summary` 到 Agent 工具列表
- `agent/tools/agent_tools.py`：向后兼容 re-export 增加 `generate_decision_summary`
- `prompts/main_prompt.txt`：
  - 三、新增第7个工具描述（结构化决策摘要生成Tool），标注仅用于决策分析模式
  - 四、工具调用链路拆分为两种模式：
    - **模式一：决策分析模式** — 触发条件为"请分析当前果园状况，给出今日农田管理建议"，走完整7步链，必须调用 `generate_decision_summary` 输出结构化JSON
    - **模式二：普通农事咨询模式** — 其他农事问题走1-6步，禁止调用 `generate_decision_summary`，输出自然语言
  - 五、输出规则增加模式区分说明
  - 六、示例行为拆分两个子章节：示例一（普通模式）、示例二（决策分析模式），修复原来示例三的不完整内容
  - 修复工具5出参行格式错位问题

---

### 2026-07-08：决策分析模式结构化输出改造方案评估

**原因**：决策分析模式下结构化JSON输出存在可靠性问题——`generate_decision_summary` 工具内嵌套LLM调用、Agent最终输出可能污染JSON、正则提取脆弱。

**产物**：`决策分析结构化输出改造方案.md`

**方案概览**：
| 方案 | 核心思路 | 推荐度 |
|------|----------|--------|
| A | `create_agent(response_format=ToolStrategy(Model))` | ⚠️ DeepSeek兼容性存疑 |
| **B（推荐）** | Agent自然语言报告 → `with_structured_output` 后处理转换 | ⭐⭐⭐⭐⭐ |
| C | 跳过Agent，直接顺序调用工具 + 结构化输出 | 可靠性高但失去Agent推理 |
| D | 保持现状，针对性修复 | 改动最小但治标不治本 |

**推荐方案B理由**：`with_structured_output` 已在当前代码验证可用（`agri_tools.py:242`），只需改变调用位置（从工具内移到 `decision_service.py` 的Agent调用之后），DeepSeek零风险，改动可控且不影响咨询模式。
