from utils.config_handler import prompts_conf
from utils.path_tool import get_abs_path
from utils.logger_handler import logger


def _load_prompt_from_config(key: str) -> str:
    """
    通用方法：根据 yaml 配置 key 加载 prompt 文本
    """
    try:
        prompt_path = get_abs_path(prompts_conf[key])
    except KeyError as e:
        logger.error(f"[{key}] 在 yaml 配置项中不存在")
        raise ValueError(f"配置缺失: {key}") from e

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"[{key}] 解析提示词文件失败: {str(e)}")
        raise RuntimeError(f"读取提示词失败: {prompt_path}") from e


def load_system_prompts() -> str:
    """加载主提示词"""
    return _load_prompt_from_config("main_prompt_path")


def load_rag_prompts() -> str:
    """加载 RAG 总结提示词"""
    return _load_prompt_from_config("rag_summarize_prompt_path")


def load_report_prompts() -> str:
    """加载报告生成提示词"""
    return _load_prompt_from_config("report_prompt_path")

# ==========================
if __name__ == "__main__":
    try:
        print("✅ 开始加载 Prompt ...\n")

        main_prompt = load_system_prompts()
        print(f"✔ main_prompt 加载成功，长度: {len(main_prompt)} 字符\n")

        rag_prompt = load_rag_prompts()
        print(f"✔ rag_summarize_prompt 加载成功，长度: {len(rag_prompt)} 字符\n")

        report_prompt = load_report_prompts()
        print(f"✔ report_prompt 加载成功，长度: {len(report_prompt)} 字符\n")

        print("🎉 所有 Prompt 加载正常")

    except Exception as e:
        print(f"❌ Prompt 加载失败: {e}")