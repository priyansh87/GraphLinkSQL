from .store import VectorStore
from typing import List, Dict, Any, Tuple
import spacy

class SchemaVectorRetriever:
    def __init__(self):
        self.store = VectorStore()
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("Warning: en_core_web_sm not found. Run: python -m spacy download en_core_web_sm")
            self.nlp = None
        
    def retrieve_columns_and_tables(self, query: str, top_k: int = 25) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        """
        Given a natural language query:
        1. Detects geographic entities.
        2. Retrieves most relevant columns semantically.
        3. Retrieves location-tagged columns if entities found.
        4. Unions and deduplicates results.
        Returns (unioned_chunks, entities_detected)
        """
        entities_detected = []
        has_location = False
        
        if self.nlp:
            doc = self.nlp(query)
            for ent in doc.ents:
                if ent.label_ in ["GPE", "LOC"]:
                    has_location = True
                    entities_detected.append({
                        "value": ent.text,
                        "type": "LOCATION"
                    })
                    
        # 1. Semantic Retrieval
        semantic_results = self.store.retrieve(query, top_k=top_k)
        merged_results = {}
        
        for res in semantic_results:
            chunk_id = res["id"]
            res["metadata"]["reason"] = "semantic_match"
            merged_results[chunk_id] = res
            
        # 2. Location Retrieval
        if has_location:
            location_results = self.store.retrieve(query, top_k=10, where={"tags": "location"})
            for res in location_results:
                chunk_id = res["id"]
                if chunk_id in merged_results:
                    merged_results[chunk_id]["metadata"]["reason"] += ", location_entity_match"
                else:
                    res["metadata"]["reason"] = "location_entity_match"
                    merged_results[chunk_id] = res
                    
        final_results = list(merged_results.values())
        return final_results, entities_detected
        
    def fetch_tables(self, table_names: List[str]) -> List[Dict[str, Any]]:
        """Directly fetch schema chunks for specific tables."""
        return self.store.fetch_by_table(table_names)
        
if __name__ == "__main__":
    retriever = SchemaVectorRetriever()
    query = "Find the total amount of orders placed by customers in Seattle"
    cols, entities = retriever.retrieve_columns_and_tables(query)
    print(f"Entities: {entities}")
    print(f"Top chunks: {[c['id'] for c in cols]}")
