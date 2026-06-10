import json
from sqlalchemy import create_engine, inspect
from typing import Dict, Any, List

def extract_schema(db_path: str = "data/AdventureWorks.db") -> Dict[str, Any]:
    """
    Extracts the database schema using SQLAlchemy Inspector.
    Includes tables, columns, data types, primary keys, and foreign keys.
    """
    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)
    
    schema_info = {}
    
    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        pk_constraint = inspector.get_pk_constraint(table_name)
        fks = inspector.get_foreign_keys(table_name)
        
        table_details = {
            "columns": [],
            "primary_keys": pk_constraint.get('constrained_columns', []),
            "foreign_keys": []
        }
        
        # Extract columns
        for col in columns:
            table_details["columns"].append({
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col.get("nullable", True)
            })
            
        # Extract foreign keys
        for fk in fks:
            table_details["foreign_keys"].append({
                "constrained_columns": fk["constrained_columns"],
                "referred_table": fk["referred_table"],
                "referred_columns": fk["referred_columns"],
                "name": fk.get("name")
            })
            
        schema_info[table_name] = table_details
        
    return schema_info

if __name__ == "__main__":
    schema = extract_schema()
    with open("data/schema_info.json", "w") as f:
        json.dump(schema, f, indent=4)
    print(f"Schema extracted for {len(schema)} tables.")
