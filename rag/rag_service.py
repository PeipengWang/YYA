"""
沂源苹果专属RAG知识库 — 检索与总结服务
从向量库检索苹果种植知识，经LLM凝练后输出标准化技术摘要供Agent决策使用
"""
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser

from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompts
from langchain_core.prompts import PromptTemplate
from model.factory import chat_model


class RagSummarizeService(object):
    def __init__(self):
        self.vector_store = VectorStoreService()
        self.retriever = self.vector_store.get_retriever()
        self.prompt_text = load_rag_prompts()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self.prompt_template | self.model | StrOutputParser()

    def retriever_docs(self, query: str) -> list[Document]:
        return self.retriever.invoke(query)

    def rag_summarize(self, query: str) -> str:
        context_docs = self.retriever_docs(query)
        context = ""
        for counter, doc in enumerate(context_docs, 1):
            context += f"【参考资料{counter}】：{doc.page_content} | 参考元数据：{doc.metadata}\n"
        if not context.strip():
            return "当前知识库中未检索到匹配的沂源苹果种植参考资料，建议拓展检索关键词或补充知识库内容。"
        return self.chain.invoke({"input": query, "context": context})


if __name__ == '__main__':
    rag = RagSummarizeService()
    print(rag.rag_summarize("苹果膨果期如何施肥"))
