from pydantic import BaseModel, Field
from typing import Type, List, Dict, Any, Optional, Tuple
import json
import re
import os
from langchain.vectorstores import FAISS
from langchain.docstore.document import Document
from config import Config
from tools.embeddings import QwenEmbeddings
from tools.tool_base import Tool, ToolResult, ToolContext


try:
    from tools.chroma_vector_retriever import ChromaVectorRetriever
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


class TableMetadataLoader:
    @staticmethod
    def load_from_file(file_path: str) -> Dict[str, Any]:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def get_table_info(metadata: Dict[str, Any], table_name: str) -> Optional[Dict[str, Any]]:
        return metadata.get("tables", {}).get(table_name)

    @staticmethod
    def get_all_table_names(metadata: Dict[str, Any]) -> List[str]:
        return list(metadata.get("tables", {}).keys())


class KeywordRetriever:
    @staticmethod
    def search(metadata: Dict[str, Any], query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        results = []
        tables = metadata.get("tables", {})

        for table_name, table_info in tables.items():
            score = KeywordRetriever._calculate_score(table_info, query)
            if score > 0:
                results.append((table_name, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    @staticmethod
    def _calculate_score(table_info: Dict[str, Any], query: str) -> float:
        score = 0.0
        query_lower = query.lower()
        query_tokens = set(query_lower.split())

        table_name = table_info.get("table_name", "").lower()
        description = table_info.get("description", "").lower()
        ddl = table_info.get("ddl", "").lower()

        if query_lower in table_name:
            score += 3.0
        elif any(token in table_name for token in query_tokens):
            score += 1.5

        if query_lower in description:
            score += 2.0
        elif any(token in description for token in query_tokens):
            score += 1.0

        if any(token in ddl for token in query_tokens):
            score += 0.5

        column_examples = table_info.get("column_examples", {})
        for col_name, examples in column_examples.items():
            if query_lower in col_name.lower():
                score += 1.0
            for example in examples:
                if query_lower in str(example).lower():
                    score += 0.3

        return score


class VectorRetriever:
    def __init__(self):
        self.embeddings = QwenEmbeddings()
        self.vector_store = None

    def build_index(self, metadata: Dict[str, Any]):
        documents = []
        tables = metadata.get("tables", {})

        for table_name, table_info in tables.items():
            content = self._build_document_content(table_info)
            doc = Document(
                page_content=content,
                metadata={"table_name": table_name}
            )
            documents.append(doc)

        if documents:
            self.vector_store = FAISS.from_documents(documents, self.embeddings)

    def _build_document_content(self, table_info: Dict[str, Any]) -> str:
        parts = []
        parts.append(f"表名: {table_info.get('table_name', '')}")
        parts.append(f"描述: {table_info.get('description', '')}")
        parts.append(f"DDL: {table_info.get('ddl', '')}")

        column_examples = table_info.get("column_examples", {})
        if column_examples:
            examples_str = "\n".join([f"{col}: {', '.join(map(str, vals))}" for col, vals in column_examples.items()])
            parts.append(f"字段示例: {examples_str}")

        return "\n".join(parts)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        if not self.vector_store:
            return []

        results = self.vector_store.similarity_search_with_score(query, k=top_k)
        return [(doc.metadata["table_name"], score) for doc, score in results]


class TableRetriever:
    def __init__(self, metadata_path: str):
        self.metadata = TableMetadataLoader.load_from_file(metadata_path)
        self.keyword_retriever = KeywordRetriever()
        self.vector_retriever = VectorRetriever()
        self.vector_retriever.build_index(self.metadata)

    def search(self, query: str, top_k: int = 5,
               keyword_weight: float = 0.5, vector_weight: float = 0.5,
               include_full_schema: bool = False) -> List[Dict[str, Any]]:
        keyword_results = self.keyword_retriever.search(self.metadata, query, top_k * 2)
        vector_results = self.vector_retriever.search(query, top_k * 2)

        combined_scores = {}

        for table_name, score in keyword_results:
            combined_scores[table_name] = combined_scores.get(table_name, 0) + score * keyword_weight

        for table_name, score in vector_results:
            combined_scores[table_name] = combined_scores.get(table_name, 0) + (1 - score) * vector_weight

        sorted_results = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)

        final_results = []
        for table_name, score in sorted_results[:top_k]:
            table_info = self.metadata["tables"][table_name]
            result = {
                "table_name": table_name,
                "qualified_name": table_info.get("qualified_name", table_name),
                "score": score,
                "description": table_info.get("description", "")
            }
            if include_full_schema:
                result["ddl"] = table_info.get("ddl", "")
                result["column_examples"] = table_info.get("column_examples", {})
            final_results.append(result)

        return final_results

    def get_table_schema(self, table_name: str) -> Optional[str]:
        table_info = self.metadata.get("tables", {}).get(table_name)
        if not table_info:
            return None

        ddl = table_info.get("ddl", "")
        description = table_info.get("description", "")

        return f"""表名: {table_name}

描述: {description}

DDL:
{ddl}"""

    def get_selected_tables_schema(self, table_names: List[str]) -> str:
        schemas = []
        for table_name in table_names:
            schema = self.get_table_schema(table_name)
            if schema:
                schemas.append(schema)

        return "\n\n".join(schemas)


class ChromaTableRetriever:
    def __init__(self, metadata_path: str = "tables_metadata.json"):
        self.metadata = TableMetadataLoader.load_from_file(metadata_path)
        self.keyword_retriever = KeywordRetriever()

        if CHROMA_AVAILABLE and os.path.exists("./chroma_db"):
            self.chroma_retriever = ChromaVectorRetriever()
            self.use_chroma = True
        else:
            self.chroma_retriever = None
            self.use_chroma = False
            print("ChromaDB不可用或未初始化，仅使用关键词检索")

    def search(self, query: str, top_k: int = 5,
               keyword_weight: float = 0.5, vector_weight: float = 0.5,
               include_full_schema: bool = False) -> List[Dict[str, Any]]:
        keyword_results = self.keyword_retriever.search(self.metadata, query, top_k * 2)

        combined_scores = {}

        for table_name, score in keyword_results:
            combined_scores[table_name] = combined_scores.get(table_name, 0) + score * keyword_weight

        if self.use_chroma and self.chroma_retriever:
            chroma_results = self.chroma_retriever.search(query, top_k * 2)
            for table_name, similarity, _ in chroma_results:
                combined_scores[table_name] = combined_scores.get(table_name, 0) + similarity * vector_weight

        sorted_results = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)

        final_results = []
        for table_name, score in sorted_results[:top_k]:
            table_info = self.metadata["tables"][table_name]
            result = {
                "table_name": table_name,
                "qualified_name": table_info.get("qualified_name", table_name),
                "score": score,
                "description": table_info.get("description", "")
            }
            if include_full_schema:
                result["ddl"] = table_info.get("ddl", "")
                result["column_examples"] = table_info.get("column_examples", {})
            final_results.append(result)

        return final_results

    def get_table_schema(self, table_name: str) -> Optional[str]:
        table_info = self.metadata.get("tables", {}).get(table_name)
        if not table_info:
            return None

        ddl = table_info.get("ddl", "")
        description = table_info.get("description", "")

        return f"""表名: {table_name}

描述: {description}

DDL:
{ddl}"""

    def get_selected_tables_schema(self, table_names: List[str]) -> str:
        schemas = []
        for table_name in table_names:
            schema = self.get_table_schema(table_name)
            if schema:
                schemas.append(schema)

        return "\n\n".join(schemas)


class SearchTablesArgs(BaseModel):
    query: str = Field(description="搜索关键词")
    top_k: int = Field(default=5, description="返回前k个结果")


class GetTableInfoArgs(BaseModel):
    table_name: str = Field(description="表名")


class SelectTablesArgs(BaseModel):
    query: str = Field(description="用户的自然语言查询")
    top_k: int = Field(default=4, description="选择前k个相关表")


class TableRetrieverTool(Tool):
    name = "table_retriever"
    description = "搜索与问题相关的表"
    access_groups = ["retriever"]
    categories = ["retrieval"]

    def __init__(self, metadata_path: str = "tables_metadata.json", use_chroma: bool = True):
        if use_chroma and CHROMA_AVAILABLE and os.path.exists("./chroma_db"):
            self.retriever = ChromaTableRetriever(metadata_path)
        else:
            self.retriever = TableRetriever(metadata_path)

    def get_args_schema(self) -> Type[BaseModel]:
        return SearchTablesArgs

    def execute(self, context: ToolContext, args: dict) -> ToolResult:
        query = args.get("query", "")
        top_k = args.get("top_k", 5)
        return self.search_tables_tool(query, top_k)

    def search_tables_tool(self, query: str, top_k: int = 5) -> ToolResult:
        try:
            results = self.retriever.search(query, top_k, include_full_schema=False)

            if not results:
                return ToolResult(success=True, data={"tables": [], "message": "未找到匹配的表"})

            return ToolResult(
                success=True,
                data={
                    "tables": results,
                    "count": len(results)
                }
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def get_table_info_tool(self, table_name: str) -> ToolResult:
        try:
            schema = self.retriever.get_table_schema(table_name)
            if schema:
                return ToolResult(success=True, data={"schema": schema})
            else:
                return ToolResult(success=False, error=f"未找到表: {table_name}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def select_tables_for_query_tool(self, query: str, top_k: int = 4) -> ToolResult:
        try:
            results = self.retriever.search(query, top_k)

            if not results:
                return ToolResult(success=False, error="未找到相关表，无法生成查询")

            table_names = [result["table_name"] for result in results]
            schema = self.retriever.get_selected_tables_schema(table_names)

            return ToolResult(
                success=True,
                data={
                    "schema": f"根据查询需求，推荐以下表:\n\n{schema}",
                    "table_names": table_names,
                    "tables": results
                }
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def search_tables(self, query: str, top_k: int = 5) -> str:
        results = self.retriever.search(query, top_k)

        if not results:
            return "未找到匹配的表"

        output = f"找到 {len(results)} 个匹配的表:\n\n"
        for i, result in enumerate(results, 1):
            output += f"{i}. {result['qualified_name']}\n"
            output += f"   匹配度: {result['score']:.3f}\n"
            output += f"   描述: {result['description'][:100]}...\n\n"

        return output

    def get_table_info(self, table_name: str) -> str:
        schema = self.retriever.get_table_schema(table_name)
        if schema:
            return schema
        else:
            return f"未找到表: {table_name}"

    def select_tables_for_query(self, query: str, top_k: int = 4) -> str:
        results = self.retriever.search(query, top_k)

        if not results:
            return "未找到相关表，无法生成查询"

        table_names = [result["table_name"] for result in results]
        schema = self.retriever.get_selected_tables_schema(table_names)

        return f"根据查询需求，推荐以下表:\n\n{schema}"