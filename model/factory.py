import os
from typing import Optional

from langchain.chat_models import init_chat_model
from langchain_core.embeddings import Embeddings
from langchain_community.chat_models.tongyi import BaseChatModel
from langchain_community.embeddings import DashScopeEmbeddings
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

from utils.config_handler import agent_conf

load_dotenv()

if not os.path.exists("resources"):
    os.mkdir("resources")
connection = sqlite3.connect("resources/apple_farming.db", check_same_thread=False)
checkpointer = SqliteSaver(connection)
checkpointer.setup()


class ChatModelFactory:
    def generator(self):
        return init_chat_model(
            model=agent_conf["chat_model_name"],
            model_provider="deepseek",
            temperature=agent_conf.get("temperature", 0.3),
        )


class EmbeddingsFactory:
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return DashScopeEmbeddings(model=agent_conf["embedding_model_name"])


chat_model = ChatModelFactory().generator()
embed_model = EmbeddingsFactory().generator()

if __name__ == '__main__':
    """
      仅用于验证：
      1. chat_model 是否能成功初始化
      2. 是否能正常调用通义千问 API
      """

    test_prompt = "你好，请用一句话介绍你自己。"

    try:
        # ✅ 推荐方式（LangChain 标准写法）
        response = chat_model.invoke([HumanMessage(content=test_prompt)])

        print("✅ ChatModel 调用成功！")
        print("模型返回结果：")
        print(response.content)

    except Exception as e:
        print("❌ ChatModel 调用失败！")
        print("错误信息：", str(e))