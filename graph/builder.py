import json
import networkx as nx
from typing import Dict, Any

def build_schema_graph(schema_path: str = "data/schema_info.json") -> nx.Graph:
    """
    Builds a NetworkX graph representing the database schema.
    Nodes: Tables
    Edges: Foreign Key relationships
    """
    with open(schema_path, "r") as f:
        schema_info = json.load(f)
        
    G = nx.Graph()
    
    for table_name, details in schema_info.items():
        G.add_node(table_name, type="table", columns=[col["name"] for col in details["columns"]])
        
        for fk in details["foreign_keys"]:
            referred_table = fk["referred_table"]
            # Add an edge for the relationship
            G.add_edge(
                table_name,
                referred_table,
                relation="foreign_key",
                local_cols=fk["constrained_columns"],
                referred_cols=fk["referred_columns"]
            )
            
    return G

if __name__ == "__main__":
    G = build_schema_graph()
    print(f"Built schema graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
