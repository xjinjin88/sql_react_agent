from typing import List
from langchain_core.embeddings import Embeddings
from tools.llm_client import EmbeddingsClient

class QwenEmbeddings(Embeddings):
    def __init__(self):
        self.client = EmbeddingsClient()
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.client.embed_documents(texts)
    
    def embed_query(self, text: str) -> List[float]:
        return self.client.embed_query(text)
