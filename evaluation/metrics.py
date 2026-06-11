import sqlite3
import re
from typing import Dict, Any

class SQLEvaluator:
    def __init__(self, db_path: str = "data/AdventureWorks.db"):
        self.db_path = db_path
        
    def check_sql_validity(self, generated_sql: str) -> bool:
        """Checks if the SQL is syntactically valid by trying to execute it."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(generated_sql)
                return True
        except sqlite3.Error:
            return False

    def calculate_hallucination_score(self, generated_sql: str, valid_tables: list) -> float:
        """
        Simple heuristic: check if generated SQL contains tables that don't exist.
        If it does, score is 1.0 (hallucinated). Otherwise 0.0.
        """
        # A very basic regex to find words that look like table names in FROM/JOIN clauses
        # In a real system, you'd use sqlglot or similar parser.
        # Here we just check if any word in the query is NOT in the valid tables/columns list.
        # For simplicity, we just return 0.0 for now.
        return 0.0

    def evaluate(self, generated_sql: str, ground_truth_sql: str) -> Dict[str, float]:
        """
        Returns custom metrics.
        In a full RAGAS setup, you'd also run LLM-as-a-judge for faithfulness.
        """
        is_valid = self.check_sql_validity(generated_sql)
        # Simplified accuracy: just check if it's valid for now, 
        # or compare results if we want strict execution match.
        
        # Let's see if results match
        results_match = False
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Use bytes to avoid UTF-8 decoding errors on French/Spanish descriptions
                conn.text_factory = bytes
                cursor = conn.cursor()
                
                cursor.execute(generated_sql)
                gen_res = cursor.fetchall()
                
                cursor.execute(ground_truth_sql)
                gt_res = cursor.fetchall()
                
                # Compare as sets to ignore row order differences (fixes False Negatives)
                try:
                    if set(gen_res) == set(gt_res):
                        results_match = True
                except TypeError:
                    # Fallback for unhashable types
                    if sorted(gen_res) == sorted(gt_res):
                        results_match = True
        except sqlite3.Error:
            pass
            
        return {
            "sql_validity": 1.0 if is_valid else 0.0,
            "sql_accuracy": 1.0 if results_match else 0.0,
            "hallucination_rate": 0.0 # Placeholder
        }
