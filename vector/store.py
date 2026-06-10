import chromadb
from chromadb.utils import embedding_functions
import json
from typing import List, Dict, Any

class VectorStore:
    def __init__(self, db_path: str = "data/chroma_db", collection_name: str = "column_schema_collection"):
        self.client = chromadb.PersistentClient(path=db_path)
        
        # BAAI/bge-small-en-v1.5 is an excellent embedding model for search
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="BAAI/bge-small-en-v1.5"
        )
        
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn
        )

    def ingest_chunks(self, chunks_path: str = "data/schema_chunks.json"):
        """Reads schema chunks from JSON and inserts them into ChromaDB."""
        with open(chunks_path, "r") as f:
            chunks: List[Dict[str, Any]] = json.load(f)
            
        ids = []
        documents = []
        metadatas = []
        
        for i, chunk in enumerate(chunks):
            ids.append(chunk["chunk_id"])
            documents.append(chunk["chunk_text"])
            metadatas.append(chunk["metadata"])
            
        # Insert into Chroma DB
        if len(documents) > 0:
            # We can use upsert to avoid duplication
            self.collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            print(f"Upserted {len(documents)} chunks into ChromaDB.")
            
    def retrieve(self, query: str, top_k: int = 5, where: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Retrieves top_k chunks matching the query, optionally filtering by metadata."""
        kwargs = {
            "query_texts": [query],
            "n_results": top_k
        }
        if where:
            kwargs["where"] = where
            
        results = self.collection.query(**kwargs)
        
        retrieved_chunks = []
        if "documents" in results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                retrieved_chunks.append({
                    "id": results["ids"][0][i],
                    "document": doc,
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "distance": results["distances"][0][i] if results.get("distances") else 0.0
                })
                
        return retrieved_chunks
        
    def fetch_by_table(self, table_names: List[str]) -> List[Dict[str, Any]]:
        """Directly fetches all chunks that belong to the specified table_names."""
        if not table_names:
            return []
            
        results = self.collection.get(where={"table_name": {"$in": table_names}})
        
        retrieved_chunks = []
        if "documents" in results and results["documents"]:
            for i, doc in enumerate(results["documents"]):
                retrieved_chunks.append({
                    "id": results["ids"][i],
                    "document": doc,
                    "metadata": results["metadatas"][i] if results.get("metadatas") else {},
                    "distance": 0.0  # Not a similarity search
                })
                
        return retrieved_chunks

if __name__ == "__main__":
    store = VectorStore()
    store.ingest_chunks()
