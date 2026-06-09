"""
ChromaDB向量检索器
基于本地SentenceTransformer模型和ChromaDB持久化存储
"""

import chromadb
import json
from typing import List, Dict, Any, Optional, Tuple
from sentence_transformers import SentenceTransformer
from tools.table_retriever import TableMetadataLoader


class ChromaVectorRetriever:
    """基于ChromaDB的向量检索器"""

    def __init__(self, db_path: str = "./chroma_db", model_name: str = "BAAI/bge-m3"):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(name="table_metadata")
        self.model = SentenceTransformer(model_name)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        向量相似度搜索

        参数:
            query: 自然语言查询
            top_k: 返回前k个结果

        返回:
            [(表名, 相似度分数, 元数据), ...]
        """
        query_vector = self.model.encode(query).tolist()

        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=top_k
        )

        output = []
        for i in range(len(results["ids"][0])):
            table_name = results["ids"][0][i]
            distance = results["distances"][0][i]
            metadata = results["metadatas"][0][i]

            if metadata.get("column_examples"):
                metadata["column_examples"] = json.loads(metadata["column_examples"])

            similarity = 1.0 - distance
            output.append((table_name, similarity, metadata))

        return output

    def get_all_tables(self) -> List[str]:
        """获取所有表名"""
        return self.collection.get()["ids"]


if __name__ == "__main__":
    retriever = ChromaVectorRetriever()
    print(f"已加载 {len(retriever.get_all_tables())} 个表")

    results = retriever.search("学生成绩", top_k=3)
    print("\n搜索结果:")
    for table_name, score, metadata in results:
        print(f"- {table_name} (相似度: {score:.3f})")