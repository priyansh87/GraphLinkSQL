from sentence_transformers import CrossEncoder
from typing import List, Dict, Any, Tuple

class ReRanker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        # Using a fast and lightweight cross-encoder for reranking
        self.model = CrossEncoder(model_name)
        
    def rerank(self, query: str, context_chunks: List[str], top_k: int = 5) -> List[str]:
        """
        Reranks a list of context chunks based on their relevance to the query.
        """
        if not context_chunks:
            return []
            
        # Create pairs of (query, chunk)
        pairs = [[query, chunk] for chunk in context_chunks]
        
        # Predict scores
        scores = self.model.predict(pairs)
        
        # Sort chunks by score in descending order
        scored_chunks = list(zip(scores, context_chunks))
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        # Return top_k chunks
        return [chunk for score, chunk in scored_chunks[:top_k]]
        
    def rerank_with_scores(self, query: str, context_chunks: List[str], top_k: int = 5) -> List[Tuple[float, str]]:
        """
        Reranks and returns both the score and the chunk text.
        """
        if not context_chunks:
            return []
            
        pairs = [[query, chunk] for chunk in context_chunks]
        scores = self.model.predict(pairs)
        
        scored_chunks = list(zip(scores, context_chunks))
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        return scored_chunks[:top_k]

if __name__ == "__main__":
    reranker = ReRanker()
    query = "Customer who ordered bikes"
    chunks = [
        "Table Product stores bike models.",
        "Table Customer stores customer names.",
        "Table SalesOrderHeader connects customer orders."
    ]
    best_chunks = reranker.rerank(query, chunks, top_k=2)
    print("Top Chunks:", best_chunks)
