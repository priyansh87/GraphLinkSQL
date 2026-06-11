from vector.retriever import SchemaVectorRetriever
from graph.retriever import GraphRetriever
from reranker.model import ReRanker
import time
import mlflow
from typing import Dict, Any

class HybridRetriever:
    def __init__(self):
        self.vector_retriever = SchemaVectorRetriever()
        self.graph_retriever = GraphRetriever()
        self.reranker = ReRanker()
        
    @mlflow.trace(name="retrieve_hybrid_context")
    def retrieve_context(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Executes hybrid retrieval:
        1. Union vector search for semantic & location column matches.
        2. Rerank the merged results.
        3. Extract unique anchor tables from TOP-K reranked columns.
        4. Graph search to pull shortest paths.
        5. Fuses context.
        """
        start_time = time.time()
        
        # Step 1: Semantic & Location Vector Retrieval
        vector_results, entities_detected = self.vector_retriever.retrieve_columns_and_tables(query, top_k=25)
        
        # Build mapping of chunk_text to chunk dict to recover metadata after reranking
        chunk_map = {res["document"]: res for res in vector_results}
        vector_chunks = list(chunk_map.keys())
        
        # Step 2: Rerank ALL retrieved chunks before truncation
        scored_chunks = self.reranker.rerank_with_scores(query, vector_chunks, top_k=len(vector_chunks))
        
        # Step 3: Phase 2 Table-Aware Aggregation
        from collections import defaultdict
        table_column_scores = defaultdict(list)
        
        retrieved_columns_detailed = []
        column_names = []
        
        for score, chunk_text in scored_chunks:
            original_chunk = chunk_map[chunk_text]
            metadata = original_chunk.get("metadata", {})
            table_name = metadata.get("table_name")
            column_name = metadata.get("column_name")
            reason = metadata.get("reason", "unknown")
            
            if table_name and column_name:
                table_column_scores[table_name].append(float(score))
                column_names.append(column_name)
                retrieved_columns_detailed.append({
                    "column": f"{table_name}.{column_name}",
                    "reason": reason,
                    "rerank_score": float(score)
                })
                
        # Step 3: Seed Table Selection (Dual-Score Fusion)
        # Instead of relying on Reranker logits (which are highly biased),
        # we use the Vector DB cosine similarity frequencies to pick Seed Tables.
        vector_table_counts = {}
        for res in vector_results:
            t_name = res["metadata"].get("table_name")
            if t_name:
                vector_table_counts[t_name] = vector_table_counts.get(t_name, 0) + 1
                
        sorted_vector_tables = sorted(vector_table_counts.items(), key=lambda x: x[1], reverse=True)
        seed_tables = [t[0] for t in sorted_vector_tables[:4]]
            
        # Step 4: Graph-Native Expansion
        GRAPH_EXPANSION_HOPS = 2
        graph_context, raw_paths, num_hops, expanded_tables = self.graph_retriever.retrieve_subgraph_context(
            seed_tables, max_hops=GRAPH_EXPANSION_HOPS
        )
        
        # Step 5: Semantic Injection & Fallback
        final_chunk_texts = []
        tables_with_context = set()
        
        # Intercept chunks from the initial 25 retrieval pool
        for score, chunk_text in scored_chunks:
            table_name = chunk_map[chunk_text].get("metadata", {}).get("table_name")
            if table_name in expanded_tables:
                final_chunk_texts.append(chunk_text)
                tables_with_context.add(table_name)
                
        # Targeted Fallback Fetch for missing tables
        missing_context = set(expanded_tables) - tables_with_context
        if missing_context:
            fallback_chunks = self.vector_retriever.fetch_tables(list(missing_context))
            for res in fallback_chunks:
                final_chunk_texts.append(res["document"])
        
        # Combine
        final_context = "=== Semantic Schema Context ===\n"
        final_context += "\n\n".join(final_chunk_texts)
        final_context += "\n\n"
        final_context += graph_context
        
        retrieval_latency = time.time() - start_time
        
        return {
            "context": final_context,
            "retrieved_tables": expanded_tables,
            "seed_tables": seed_tables,
            "graph_expansion_hops": GRAPH_EXPANSION_HOPS,
            "retrieved_columns": column_names,
            "retrieved_columns_detailed": retrieved_columns_detailed,
            "entities_detected": entities_detected,
            "graph_paths": raw_paths,
            "num_hops": num_hops,
            "retrieval_latency": retrieval_latency,
            "table_scores": vector_table_counts,
            "forced_anchor_tables": []
        }

if __name__ == "__main__":
    hybrid = HybridRetriever()
    query = "Find the total amount of orders placed by customers in Seattle"
    result = hybrid.retrieve_context(query, top_k=25)
    print("HYBRID CONTEXT:\n", result["context"])
