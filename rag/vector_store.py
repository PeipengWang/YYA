import os
import hashlib
from typing import List, Tuple

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 假设这些是你项目里的自定义模块（根据你的截图保留）
from utils.config_handler import chroma_conf
from model.factory import embed_model
from utils.path_tool import get_abs_path
from utils.file_handler import pdf_loader, txt_loader, listdir_with_allowed_type, get_file_md5_hex
from utils.logger_handler import logger


class VectorStoreService:
    def __init__(self):
        # 1. 初始化向量数据库
        self.vector_store = Chroma(
            collection_name=chroma_conf["collection_name"],
            embedding_function=embed_model,
            persist_directory=chroma_conf["persist_directory"],
        )

        # 2. 初始化文本分割器
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf["separators"],
            length_function=len,
        )

        # 3. 启动时自动加载文档（替代外部调用）
        # self.load_document()

    def get_retriever(self):
        """获取检索器"""
        return self.vector_store.as_retriever(search_kwargs={"k": chroma_conf["k"]})

    def load_document(self):
        """
        从数据文件夹内读取数据文件，转为向量存入向量库
        要计算文件的MD5做去重
        """
        # 获取允许加载的文件路径列表
        allowed_files_path: List[str] = listdir_with_allowed_type(
            get_abs_path(chroma_conf["data_path"]),
            tuple(chroma_conf["allow_knowledge_file_type"]),
        )

        # 遍历处理每一个文件
        for path in allowed_files_path:
            # 获取文件的MD5
            md5_hex = get_file_md5_hex(path)

            # 检查MD5是否已存在，如果存在则跳过
            if self.check_md5_hex(md5_hex):
                logger.info(f"[加载知识库]{path}内容已经存在知识库内，跳过")
                continue

            try:
                # 加载文件内容
                documents: List[Document] = self.get_file_documents(path)

                if not documents:
                    logger.warning(f"[加载知识库]{path}内没有有效文本内容，跳过")
                    continue

                # 文本分割
                split_document: List[Document] = self.splitter.split_documents(documents)

                if not split_document:
                    logger.warning(f"[加载知识库]{path}分片后没有有效文本内容，跳过")
                    continue
                # 将内容存入向量库
                self.vector_store.add_documents(split_document)

                # 记录这个已经处理好的文件的md5，避免下次重复加载
                self.save_md5_hex(md5_hex)

                logger.info(f"[加载知识库]{path} 内容加载成功")

            except Exception as e:
                # exc_info=True会记录详细的报错堆栈，如果为False仅记录报错信息本身
                logger.error(f"[加载知识库]{path}加载失败：{str(e)}", exc_info=True)
                continue

    def check_md5_hex(self, md5_for_check: str) -> bool:
        """
        检查MD5是否已经存在于记录文件中
        """
        file_path = get_abs_path(chroma_conf["md5_hex_store"])

        # 如果记录文件不存在，说明是第一次运行，直接返回False（没处理过）
        if not os.path.exists(file_path):
            # 这里不需要创建文件，因为如果返回False，后面的逻辑会写入
            return False

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f.readlines():
                line = line.strip()
                if line == md5_for_check:
                    return True  # md5 处理过
        return False  # md5 没处理过

    def save_md5_hex(self, md5_for_check: str):
        """
        将处理过的文件MD5记录到本地文件中
        """
        with open(get_abs_path(chroma_conf["md5_hex_store"]), "a", encoding="utf-8") as f:
            f.write(md5_for_check + "\n")

    def get_file_documents(self, read_path: str) -> List[Document]:
        """
        根据文件路径后缀加载对应的文档
        """
        if read_path.endswith("txt"):
            return txt_loader(read_path)
        if read_path.endswith("pdf"):
            return pdf_loader(read_path)
        return []

    # # ==========================
    # # 【新增】导入 SoulChat 心理对话数据集到 Chroma
    # # ==========================
    # def import_soulchat_dataset(self, limit: int = None):
    #     """
    #     导入 SoulChatCorpus 共情心理对话数据集
    #     :param limit: 限制导入条数，防止数据太大卡死，默认 None 全部导入
    #     """
    #     try:
    #         from modelscope.msdatasets import MsDataset
    #         logger.info("正在加载 SoulChatCorpus 数据集...")
    #
    #         # 加载数据集
    #         ds = MsDataset.load('YIRONGCHEN/SoulChatCorpus', subset_name='default', split='train')
    #
    #         documents = []
    #         total = 0
    #
    #         # 遍历数据
    #         for idx, item in enumerate(ds):
    #             if limit and idx >= limit:
    #                 break
    #
    #             try:
    #                 conv_id = item["id"]
    #                 topic = item["topic"]
    #                 messages = item["messages"]
    #
    #                 # 拼接多轮对话
    #                 dialogue = f"主题：{topic}\n"
    #                 for msg in messages:
    #                     role = msg["role"]
    #                     content = msg["content"]
    #                     if role == "user":
    #                         dialogue += f"用户：{content}\n"
    #                     else:
    #                         dialogue += f"助手：{content}\n"
    #
    #                 # 构建 Document
    #                 doc = Document(
    #                     page_content=dialogue.strip(),
    #                     metadata={
    #                         "source": "SoulChat",
    #                         "topic": topic,
    #                         "id": conv_id
    #                     }
    #                 )
    #                 documents.append(doc)
    #
    #                 # 每 100 条批量入库
    #                 if len(documents) >= 100:
    #                     # 分片（兼容你的配置）
    #                     splits = self.splitter.split_documents(documents)
    #                     self.vector_store.add_documents(splits)
    #                     total += len(documents)
    #                     logger.info(f"已导入 {total} 条对话数据")
    #                     documents = []
    #
    #             except Exception as e:
    #                 continue
    #
    #         # 最后一批
    #         if documents:
    #             splits = self.splitter.split_documents(documents)
    #             self.vector_store.add_documents(splits)
    #             total += len(documents)
    #
    #         logger.info(f"✅ SoulChat 数据集导入完成！总计：{total} 条高质量心理对话")
    #
    #     except Exception as e:
    #         logger.error(f"导入失败：{e}", exc_info=True)


# --- 主程序入口（对应你截图中的 if __name__ == '__main__'） ---
# if __name__ == '__main__':
#     vs = VectorStoreService()
#     retriever = vs.get_retriever()
#
#     # 测试查询
#     # 检索时设置 k=5~8，默认一般k=3
#     # res = retriever.invoke("我有抑郁症", k=100)
#     #
#     #
#     # print("\n" + "="*50)
#     # print("检索结果：")
#     # print("="*50)
#     # # for r in res:
#     # #     print(r.page_content)
#     # #     print("-" * 20)
#     # # 遍历查看全部片段，整合内容
#     # for idx, doc in enumerate(res):
#     #     print(f"片段{idx + 1}:\n{doc.page_content}\n{'-' * 50}")
#    # 先召回 20 条，然后按分数筛选最相关的 5 条
#     results_with_scores = vs.vector_store.similarity_search_with_score(
#         query="我有抑郁症",
#         k=100  # 先拉取20条
#     )
#
#     # 排序并取前5
#     sorted_docs = sorted(results_with_scores, key=lambda x: x[1])
#     context_docs = [doc for doc, score in sorted_docs[:5]]
#     # =================================================================
#
#     # 下面是你原来的逻辑，完全不动
#     context = ""
#     print("\n" + "=" * 50)
#     print("检索结果：")
#     print("=" * 50)
#     # for r in res:
#     #     print(r.page_content)
#     #     print("-" * 20)
#     # 遍历查看全部片段，整合内容
#     for idx, doc in enumerate(res):
#         print(f"片段{idx + 1}:\n{doc.page_content}\n{'-' * 50}")
#
if __name__ == '__main__':
    vs = VectorStoreService()
    vector_store = vs.vector_store

    # 1. 检索 100 条带分数
    results_with_scores = vector_store.similarity_search_with_score(
        query="我有抑郁症",
        k=100
    )

    # 2. 按分数从小到大排序（分数越低越相关）
    results_with_scores.sort(key=lambda x: x[1])
    # 3. 直接取 TOP 5 条最相关的
    top5_docs = [doc for doc, score in results_with_scores[:5]]

    # ===================== 逐条打印（干净、清爽） =====================
    print("\n==================== TOP5 最相关结果 ====================\n")
    for i, doc in enumerate(top5_docs, 1):
        print(f"第 {i} 条：")
        print(doc.page_content)
        print("-" * 60)

