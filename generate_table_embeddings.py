import json
from sentence_transformers import SentenceTransformer
import chromadb

def init_chroma_client():
    # 创建本地持久化客户端
    client = chromadb.PersistentClient(path="./chroma_db")
    return client

def load_metadata(file_path):
    """
    自适应解析你提供的新版 JSON 结构
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # 严格匹配最外层的 "tables" 键
    if isinstance(data, dict) and "tables" in data:
        # 为了拿到外层的 key (如 dbo.class)，我们遍历字典
        table_list = []
        for key, table_info in data["tables"].items():
            # 将外层完整的限定名也注入进去，确保万无一失
            table_info["_lookup_id"] = key 
            table_list.append(table_info)
        return table_list
    else:
        raise ValueError("JSON 文件格式不符合预期的 {'tables': {...}} 结构！")

def generate_embeddings(metadata, model):
    embeddings = []
    for table in metadata:
        # 提取各个维度的数据
        lookup_id = table.get("_lookup_id", table.get("qualified_name", ""))
        table_name = table.get("table_name", "")
        description = table.get("description", "")
        ddl = table.get("ddl", "")
        column_examples = table.get("column_examples", {})

        # ----------------- 核心丰富化：构建超强语义文本 -----------------
        combined_text = f"完整表名: {lookup_id}\n"
        combined_text += f"业务描述: {description}\n"
        
        if ddl:
            combined_text += f"DDL建表语句:\n{ddl}\n"
            
        if column_examples:
            examples_str = "\n".join([f"  - {col}: {', '.join(map(str, vals))}" for col, vals in column_examples.items()])
            combined_text += f"字段真实数据样例:\n{examples_str}"
        # --------------------------------------------------------------

        # 使用 BGE-M3 模型生成向量
        vector = model.encode(combined_text)
        
        # 将 DDL 存入 metadata，这样 RAG 检索出来直接就能拿到建表语句给大模型
        embeddings.append({
            "id": lookup_id,
            "vector": vector,
            "metadata": {
                "table_name": table_name,
                "schema": table.get("schema", "dbo"),
                "qualified_name": lookup_id,
                "description": description[:500], # 限制长度防止超限
                "ddl": ddl,
                "column_examples": json.dumps(column_examples, ensure_ascii=False) if column_examples else ""
            }
        })
    return embeddings

def import_to_chroma(client, embeddings):
    # 创建或获取向量集合
    collection = client.get_or_create_collection(name="table_metadata")

    # 获取数据库里现有的 ids，进行增量去重
    existing_ids = collection.get()["ids"]
    new_embeddings = [emb for emb in embeddings if emb["id"] not in existing_ids]

    if not new_embeddings:
        print("所有表结构已存在于 Chroma 向量库中，无需重复更新！")
        return

    # 组装批量写入的数据
    ids = [emb["id"] for emb in new_embeddings]
    documents = [emb["id"] for emb in new_embeddings] # document可以存放ID或简短文本
    metadatas = [emb["metadata"] for emb in new_embeddings]
    embedding_vectors = [emb["vector"].tolist() for emb in new_embeddings]

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embedding_vectors
    )
    print(f"🎉 向量化成功！已成功导入 {len(new_embeddings)} 个表的完整特征到 Chroma 数据库中。")

if __name__ == "__main__":
    # 1. 指定你导出的标准 JSON 文件名
    metadata_file = "tables_metadata.json" 
    
    print("正在加载 JSON 元数据...")
    metadata = load_metadata(metadata_file)

    print("正在初始化 BGE-M3 模型并计算向量（这可能需要一点时间）...")
    model = SentenceTransformer('BAAI/bge-m3')
    embeddings = generate_embeddings(metadata, model)
    
    print("正在连接本地 ChromaDB...")
    chroma_client = init_chroma_client()
    
    print("开始数据去重并入库...")
    import_to_chroma(chroma_client, embeddings)