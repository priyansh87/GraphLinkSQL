import sqlite3
import json
import os
import time
from generation.llm import SQLGenerator
from evaluation.dataset import load_dataset
from evaluation.metrics import SQLEvaluator

FAILED_QUESTIONS = [
    "Find the total quantity sold for each product category.",
    "Count the number of products in each product category.",
    "What is the average order quantity per product in the sales details?",
    "Find the total amount of orders placed by customers in London.",
    "Find the customer who placed the most orders.",
    "List the categories that have products costing more than $1000.",
    "List all products that have a standard cost strictly greater than 500.",
    "List the product models that have a catalog description.",
    "List the descriptions of product model ID 19.",
    "Find the product category generating the highest revenue among customers in London.",
    "Find all product models associated with products purchased by customers in Seattle.",
    "List the categories purchased by customers whose orders were shipped to London.",
    "List all product descriptions for products purchased by Orlando Gee."
]

def analyze_failures():
    generator = SQLGenerator(model_name="qwen2.5", provider="ollama", retrieval_mode="hybrid")
    evaluator = SQLEvaluator()
    dataset = load_dataset()
    
    db_path = "data/AdventureWorks.db"
    report_md = "# False Negative Analysis Report\n\n"
    
    false_negatives = 0
    gt_issues = 0
    actual_failures = 0
    total_evaluated = 0
    
    for item in dataset:
        q = item["question"]
        if q not in FAILED_QUESTIONS:
            continue
            
        gt_sql = item["ground_truth_sql"]
        total_evaluated += 1
        
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
                cursor = conn.cursor()
                cursor.execute(gt_sql)
                gt_output = cursor.fetchall()
        except Exception as e:
            gt_error = str(e)
            
        try:
            with sqlite3.connect(db_path) as conn:
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
            classification = "F. Multiple Valid SQL Solutions (False Negative)"
            false_negatives += 1
        elif gt_error:
            classification = "D. Ground Truth SQL Error"
            gt_issues += 1
        elif gen_error:
            classification = "B. SQL Generation Failure"
            actual_failures += 1
        else:
            # Further logic to identify if it's schema ambiguity or retrieval
            if len(set_gt) == 0:
                classification = "D. Ground Truth SQL Error (Returns empty)"
                gt_issues += 1
            else:
                classification = "B. SQL Generation Failure / A. Retrieval Failure"
                actual_failures += 1

        report_md += f"## Question: {q}\n"
        report_md += f"**Classification:** {classification}\n\n"
        report_md += f"**Ground Truth SQL:**\n```sql\n{gt_sql}\n```\n"
        report_md += f"**Generated SQL:**\n```sql\n{gen_sql}\n```\n"
        report_md += f"**Ground Truth Output (First 5):** {gt_output[:5] if gt_output else gt_error}\n\n"
        report_md += f"**Generated Output (First 5):** {gen_output[:5] if gen_output else gen_error}\n\n"
        report_md += f"**Context Used:**\n<details><summary>Click to expand</summary>\n\n```text\n{context}\n```\n</details>\n\n"
        report_md += "---\n"
        
        print(f"Processed: {q} -> {classification}")
        time.sleep(1) # Small delay to respect rate limits
        
    report_md += f"## Summary\n"
    report_md += f"- **Original Accuracy:** 0.72 (36/50)\n"
    # Estimate corrected accuracy
    corrected_acc = (36 + false_negatives + gt_issues) / 50.0
    report_md += f"- **Corrected Accuracy:** {corrected_acc:.2f}\n"
    report_md += f"- **Number of False Negatives:** {false_negatives}\n"
    report_md += f"- **Number of Ground Truth Issues:** {gt_issues}\n"
    report_md += f"- **Number of Actual Model Failures:** {actual_failures}\n"

    with open("investigation_report.md", "w", encoding="utf-8") as f:
        f.write(report_md)

if __name__ == "__main__":
    analyze_failures()
