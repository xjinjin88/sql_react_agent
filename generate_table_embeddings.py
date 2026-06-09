import json
from sentence_transformers import SentenceTransformer
import chromadb

def init_chroma_client():
    client = chromadb.PersistentClient(path="./chroma_db")
    return client

def load_metadata(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, dict) and "tables" in data:
            return list(data["tables"].values())
        elif isinstance(data, list):
            return data
        else:
            raise ValueError("Invalid metadata format")

def generate_embeddings(metadata, model):
    embeddings = []
    for table in metadata:
        table_name = table.get("table_name", "")
        description = table.get("description", "")
        column_examples = table.get("column_examples", {})

        combined_text = f"表名: {table_name}\n描述: {description}"
        if column_examples:
            examples_str = "\n".join([f"{col}: {', '.join(map(str, vals))}" for col, vals in column_examples.items()])
            combined_text += f"\n字段示例:\n{examples_str}"

        vector = model.encode(combined_text)
        embeddings.append({
            "table_name": table_name,
            "vector": vector,
            "metadata": {
                "table_name": table_name,
                "description": description,
                "qualified_name": table.get("qualified_name", ""),
                "column_examples": json.dumps(column_examples, ensure_ascii=False) if column_examples else ""
            }
        })
    return embeddings

def import_to_chroma(client, embeddings):
    collection = client.get_or_create_collection(name="table_metadata")

    existing_ids = collection.get()["ids"]
    new_embeddings = [emb for emb in embeddings if emb["table_name"] not in existing_ids]

    if not new_embeddings:
        print("所有表已存在于 Chroma 数据库中，无需更新！")
        return

    ids = [emb["table_name"] for emb in new_embeddings]
    documents = [emb["table_name"] for emb in new_embeddings]
    metadatas = [emb["metadata"] for emb in new_embeddings]
    embedding_vectors = [emb["vector"].tolist() for emb in new_embeddings]

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embedding_vectors
    )
    print(f"向量已成功导入 Chroma 数据库！共导入 {len(new_embeddings)} 个表的元数据。")

if __name__ == "__main__":
    metadata_file = "tables_metadata.json"
    metadata = load_metadata(metadata_file)

    model = SentenceTransformer('BAAI/bge-m3')

    embeddings = generate_embeddings(metadata, model)
    chroma_client = init_chroma_client()
    import_to_chroma(chroma_client, embeddings)