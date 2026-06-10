import json
import os
from typing import List, Dict, Any

BUSINESS_CONTEXT_MAP = {
    "Address": "Stores street address information for customers, including city, state, and postal code.",
    "Customer": "Stores customer information including first name, last name, and company details. Represents clients purchasing bikes and products.",
    "CustomerAddress": "A junction table that maps Customers to their corresponding Address records. Resolves many-to-many relationships between clients and locations.",
    "Product": "Stores the master list of all products, bicycles, and components sold by AdventureWorks, including pricing (ListPrice), color, and product numbers.",
    "ProductCategory": "High-level classification of products (e.g., Bikes, Components, Clothing).",
    "ProductModel": "Stores product models. A single product model might be associated with multiple specific products varying by size or color.",
    "ProductDescription": "Stores textual marketing descriptions for products.",
    "ProductModelProductDescription": "Junction table mapping product models to localized textual descriptions.",
    "SalesOrderDetail": "Stores individual line items associated with a specific sales order. Connects to the Product table to identify what was bought.",
    "SalesOrderHeader": "Stores the main sales order metadata, including total amount due, order date, freight cost, and links the order to the Customer who placed it.",
    "ErrorLog": "System log storing application or database errors.",
    "BuildVersion": "Database build version information."
}

def create_schema_chunks(schema_path: str = "data/schema_info.json") -> List[Dict[str, Any]]:
    """
    Reads the extracted schema and generates column-level semantic chunks for vector embedding.
    """
    with open(schema_path, "r") as f:
        schema_info = json.load(f)
        
    chunks = []
    
    for table_name, details in schema_info.items():
        business_context = BUSINESS_CONTEXT_MAP.get(table_name, "Standard database table.")
        
        # Build dictionary of column -> foreign key relations
        fk_map = {}
        for fk in details["foreign_keys"]:
            for col in fk["constrained_columns"]:
                ref_cols = ", ".join(fk["referred_columns"])
                fk_map[col] = f"{fk['referred_table']} ({ref_cols})"
                
        # Generate a chunk for every column
        for col in details["columns"]:
            col_name = col["name"]
            col_type = col["type"]
            nullable = "Nullable" if col["nullable"] else "Not Null"
            is_pk = "Yes" if col_name in details["primary_keys"] else "No"
            fk_ref = fk_map.get(col_name, "None")
            
            # Location Semantic Tagging (Phase 1)
            location_keywords = ["city", "state", "country", "address", "postal", "zip", "region", "province", "location", "municipality", "town"]
            is_location_column = any(keyword in col_name.lower() for keyword in location_keywords)
            
            semantic_tags_str = ""
            metadata_tags = ""
            if is_location_column:
                semantic_tags_str = "\nSemantic Tags: location, city, geography, region, address"
                metadata_tags = "location"
            
            chunk_text = (
                f"Table: {table_name}\n"
                f"Table Context: {business_context}\n"
                f"Column: {col_name}\n"
                f"Type: {col_type} ({nullable})\n"
                f"Primary Key: {is_pk}\n"
                f"Foreign Key: {fk_ref}"
                f"{semantic_tags_str}"
            )
            
            chunk_id = f"{table_name}.{col_name}"
            
            chunks.append({
                "table_name": table_name,
                "column_name": col_name,
                "chunk_id": chunk_id,
                "chunk_text": chunk_text,
                "metadata": {
                    "type": "column_schema",
                    "table_name": table_name,
                    "column_name": col_name,
                    "tags": metadata_tags
                }
            })
            
    return chunks

if __name__ == "__main__":
    chunks = create_schema_chunks()
    with open("data/schema_chunks.json", "w") as f:
        json.dump(chunks, f, indent=4)
    print(f"Generated {len(chunks)} column-level schema chunks.")
