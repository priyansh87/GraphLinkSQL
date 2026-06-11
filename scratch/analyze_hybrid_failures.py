import sqlite3
import json
import os
import time
from generation.llm import SQLGenerator
from evaluation.dataset import load_dataset
from evaluation.metrics import SQLEvaluator

FAILED_QUESTIONS = [
    "List customers who purchased products from the Bikes category.",
    "Find the customer who spent the most on products from the Clothing category.",
    "Find the product category generating the highest revenue among customers in London.",
    "Which customers purchased products that have a catalog description?",
    "Find all product models associated with products purchased by customers in Seattle.",
    "Count the number of products in each product category.",
    "What is the average order quantity per product in the sales details?",
    "List all products that have a standard cost strictly greater than 500."
]

def analyze_failures():
    generator = SQLGenerator(model_name="qwen2.5", provider="ollama", retrieval_mode="hybrid")
    dataset = load_dataset()
    db_path = "data/AdventureWorks.db"
    
    report_md = "# Hybrid GraphRAG Failure Analysis\n\n"
    report_md += "The following questions failed under the Hybrid GraphRAG pipeline. Let's classify them:\n\n"
    
    for item in dataset:
        q = item["question"]
        if q not in FAILED_QUESTIONS:
            continue
            
        gt_sql = item["ground_truth_sql"]
        
        # 1. Generation
        result = generator.generate_sql(q)
        gen_sql = result["sql"]
        context = result["context"]
        
        # 2. Execute both
        gt_output = []
        gen_output = []
        gt_error = None
        gen_error = None
        
        try:
            with sqlite3.connect(db_path) as conn:
                conn.text_factory = bytes
                cursor = conn.cursor()
                cursor.execute(gt_sql)
                gt_output = cursor.fetchall()
        except Exception as e:
            gt_error = str(e)
            
        try:
            with sqlite3.connect(db_path) as conn:
                conn.text_factory = bytes
                cursor = conn.cursor()
                cursor.execute(gen_sql)
                gen_output = cursor.fetchall()
        except Exception as e:
            gen_error = str(e)
            
        # Compare sets ignoring order
        is_false_negative = False
        set_gt = set(gt_output) if gt_output else set()
        set_gen = set(gen_output) if gen_output else set()
        
        if set_gt == set_gen and len(set_gt) > 0 and not gt_error and not gen_error:
            is_false_negative = True
            classification = "F. False Negative (Evaluator Bug/Result match missed?)"
        elif gt_error:
            classification = "D. Ground Truth SQL Error"
        elif gen_error:
            classification = "B. SQL Generation Failure (Syntax/Schema Error)"
        else:
            if len(set_gt) == 0:
                classification = "D. Ground Truth SQL Error (Returns empty)"
            else:
                # Need to manually inspect context to differentiate A and B.
                classification = "B. SQL Gen OR A. Retrieval Failure (Data Mismatch)"

        report_md += f"## Question: {q}\n"
        report_md += f"**Classification:** {classification}\n\n"
        report_md += f"**Ground Truth SQL:**\n```sql\n{gt_sql}\n```\n"
        report_md += f"**Generated SQL:**\n```sql\n{gen_sql}\n```\n"
        report_md += f"**Ground Truth Output (First 3):** {gt_output[:3] if gt_output else gt_error}\n\n"
        report_md += f"**Generated Output (First 3):** {gen_output[:3] if gen_output else gen_error}\n\n"
        report_md += f"**Context Used:**\n<details><summary>Click to expand</summary>\n\n```text\n{context}\n```\n</details>\n\n"
        report_md += "---\n"
        
        print(f"Analyzed: {q}")
        
    with open("hybrid_failure_report.md", "w", encoding="utf-8") as f:
        f.write(report_md)

if __name__ == "__main__":
    analyze_failures()
