import networkx as nx
import itertools
from typing import List, Set, Tuple, Dict, Any
from graph.builder import build_schema_graph

class GraphRetriever:
    def __init__(self, schema_path: str = "data/schema_info.json"):
        self.graph = build_schema_graph(schema_path)

    def retrieve_subgraph_context(self, anchor_tables: List[str], max_hops: int = None) -> Tuple[str, List[str], int, List[str]]:
        """
        Calculates shortest paths between anchor tables, infers complexity,
        dynamically expands neighborhood, and outputs sequential JOIN paths.
        Returns: (formatted_context, raw_paths_list, inferred_complexity_depth, list(relevant_tables))
        """
        # Filter to tables actually in the graph
        valid_anchors = [t for t in anchor_tables if t in self.graph]
        
        if not valid_anchors:
            return "--- Graph Context: Relationships ---\nNone", [], 0, []
            
        # 1. Calculate all shortest paths between anchors
        shortest_paths = []
        max_path_len = 0
        
        if len(valid_anchors) > 1:
            for t1, t2 in itertools.combinations(valid_anchors, 2):
                try:
                    path = nx.shortest_path(self.graph, source=t1, target=t2)
                    shortest_paths.append(path)
                    max_path_len = max(max_path_len, len(path) - 1)
                except nx.NetworkXNoPath:
                    pass
        
        # 2. Derive Complexity -> Traversal Depth
        if max_hops is not None:
            inferred_depth = max_hops
        elif len(valid_anchors) == 1 or max_path_len <= 1:
            inferred_depth = 1  # Simple
        elif max_path_len <= 3 or len(valid_anchors) <= 3:
            inferred_depth = 2  # Join
        else:
            inferred_depth = 3  # Multi-hop
            
        # 3. Dynamic Expansion (add neighbors to relevant set)
        relevant_tables: Set[str] = set()
        for t in valid_anchors:
            relevant_tables.add(t)
            neighbors = nx.single_source_shortest_path_length(self.graph, t, cutoff=inferred_depth)
            relevant_tables.update(neighbors.keys())
            
        # Also add any tables discovered along the shortest paths
        for path in shortest_paths:
            relevant_tables.update(path)
            
        # 4. Construct explicit sequential JOIN paths
        context_lines = ["=== Recommended Join Paths ==="]
        raw_paths_list = []
        
        # Output ALL valid edges that exist between the relevant_tables
        subgraph = self.graph.subgraph(relevant_tables)
        for u, v, data in subgraph.edges(data=True):
            local_cols = ", ".join(data.get("local_cols", []))
            ref_cols = ", ".join(data.get("referred_cols", []))
            
            # Formatting as a bidirectional relationship so LLM knows it can join either way
            path_str = f"{u} JOIN {v} ON {u}.{local_cols} = {v}.{ref_cols}"
            context_lines.append(f"Relation: {path_str}")
            raw_paths_list.append(path_str)
                
        return "\n".join(context_lines), raw_paths_list, inferred_depth, list(relevant_tables)

if __name__ == "__main__":
    retriever = GraphRetriever()
    # Test with multi-hop
    ctx, paths, depth, tables = retriever.retrieve_subgraph_context(["Customer", "Address"], max_hops=2)
    print(f"Inferred Depth: {depth}\n")
    print(ctx)
