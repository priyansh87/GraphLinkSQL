import mlflow
import time
import argparse
import json
import sqlite3
from generation.llm import SQLGenerator
from evaluation.dataset import load_dataset
from evaluation.metrics import SQLEvaluator

def run_experiment(experiment_name: str, run_name: str, retrieval_mode: str, model_name: str, provider: str, phase1: bool = False, phase1_2: bool = False, phase2: bool = False, phase3: bool = False, first30: bool = False, first15: bool = False, next20: bool = False, last15: bool = False, **kwargs):
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment(experiment_name)
    
    generator = SQLGenerator(model_name=model_name, provider=provider, retrieval_mode=retrieval_mode)
    evaluator = SQLEvaluator()
    dataset = load_dataset()
    
    if phase1:
        # Filter to Control (Q1) and Location Queries (Q3, Q6, Q8, Q9)
        # 1-indexed to 0-indexed: [0, 2, 5, 7, 8]
        dataset = [dataset[i] for i in [0, 2, 5, 7, 8]]
        print("PHASE 1 VALIDATION MODE: Filtering to Q1, Q3, Q6, Q8, Q9")
        
    if phase1_2:
        # Filter to failed Location Queries from Phase 1
        # 1-indexed to 0-indexed: [2, 5, 7, 8] (Q3, Q6, Q8, Q9)
        # Wait, the user specifically said: London revenue query, Seattle product model query, Any other location-related failures from Phase 1.
        dataset = [dataset[i] for i in [2, 5, 7, 8]]
        print("PHASE 1.2 VALIDATION MODE: Filtering to Q3, Q6, Q8, Q9")
        
    if phase2 or phase3:
        # Filter to Location, ProductCategory, and Revenue queries
        # 0: ProductCategory, 1: ProductCategory/Revenue, 2: Location, 3: ProductCategory/Revenue, 5: Location/Revenue, 7: Location, 8: Location
        dataset = [dataset[i] for i in [0, 1, 2, 3, 5, 7, 8]]
        print(f"PHASE {'3' if phase3 else '2'} VALIDATION MODE: Filtering to Location, ProductCategory, and Revenue queries")
        
    if first30:
        dataset = dataset[:30]
        print("FIRST 30 VALIDATION MODE: Running on the first 30 questions in the dataset")
        
    if first15:
        dataset = dataset[:15]
        print("FIRST 15 VALIDATION MODE: Running on the first 15 questions in the dataset")
        
    if next20:
        dataset = dataset[15:35]
        print("NEXT 20 VALIDATION MODE: Running on questions 16 to 35 in the dataset")
        
    if last15:
        dataset = dataset[-15:]
        print("LAST 15 VALIDATION MODE: Running on the last 15 questions in the dataset")
        
    if kwargs.get('onehop'):
        dataset = [d for d in dataset if d["ground_truth_sql"].count(" JOIN ") == 1]
        print(f"ONE HOP VALIDATION MODE: Running on {len(dataset)} 1-hop questions")
        
    if kwargs.get('only_q8'):
        dataset = [dataset[7]]
        print("ONLY Q8 VALIDATION MODE: Running exclusively on Q8")
        
    db_path = "data/AdventureWorks.db"
    
    print(f"\nStarting run '{run_name}' using {retrieval_mode.upper()} retrieval over {len(dataset)} questions...")
    
    query_logs = []
    
    with mlflow.start_run(run_name=run_name):
        # Log parameters
        mlflow.log_params({
            "retrieval_type": retrieval_mode,
            "embedding_model": "BAAI/bge-small-en-v1.5",
            "top_k": 5,
            "reranker": "cross-encoder/ms-marco-MiniLM-L-6-v2" if retrieval_mode == "hybrid" else "none",
            "llm": generator.model_name
        })
        
        total_validity = 0
        total_accuracy = 0
        
        start_time = time.time()
        
        for idx, item in enumerate(dataset):
            question = item["question"]
            gt_sql = item["ground_truth_sql"]
            
            q_start_time = time.time()
            
            # Generate
            result = generator.generate_sql(question)
            gen_sql = result["sql"]
            context_used = result.get("context", "")
            
            # Extract detailed observability data (will be populated by retriever updates later)
            retrieved_tables = result.get("retrieved_tables", [])
            retrieved_columns = result.get("retrieved_columns", [])
            retrieved_columns_detailed = result.get("retrieved_columns_detailed", [])
            entities_detected = result.get("entities_detected", [])
            graph_paths = result.get("graph_paths", [])
            num_hops = result.get("num_hops", 0)
            retrieval_latency = result.get("retrieval_latency", 0)
            llm_latency = result.get("llm_latency", 0)
            
            # Phase 1.2, Phase 2, Phase 3 Fields
            table_scores = result.get("table_scores", {})
            forced_anchor_tables = result.get("forced_anchor_tables", [])
            seed_tables = result.get("seed_tables", [])
            graph_expansion_hops = result.get("graph_expansion_hops", 0)
            paths_before_pruning = result.get("paths_before_pruning", 0)
            paths_after_pruning = result.get("paths_after_pruning", 0)
            pruning_reduction_pct = result.get("pruning_reduction_pct", 0.0)
            
            # Evaluate
            metrics = evaluator.evaluate(gen_sql, gt_sql)
            is_valid = metrics["sql_validity"] == 1.0
            is_accurate = metrics["sql_accuracy"] == 1.0
            
            # Get execution sample
            sample_rows = []
            try:
                with sqlite3.connect(db_path) as conn:
                    conn.text_factory = bytes
                    cursor = conn.cursor()
                    cursor.execute(gen_sql)
                    sample_rows = cursor.fetchmany(3)
            except Exception as e:
                sample_rows = [f"Error: {str(e)}"]
            
            q_total_latency = time.time() - q_start_time
            
            total_validity += int(is_valid)
            total_accuracy += int(is_accurate)
            
            # Log exact query details
            query_logs.append({
                "question_id": item.get("id", idx + 1),
                "question": question,
                "entities_detected": entities_detected,
                "retrieved_tables": retrieved_tables,
                "retrieved_columns": retrieved_columns,
                "retrieved_columns_detailed": retrieved_columns_detailed,
                "graph_paths": graph_paths,
                "num_retrieved_tables": len(retrieved_tables),
                "num_retrieved_columns": len(retrieved_columns),
                "num_graph_hops": num_hops,
                "table_scores": table_scores,
                "seed_tables": seed_tables,
                "graph_expansion_hops": graph_expansion_hops,
                "forced_anchor_tables": forced_anchor_tables,
                "context_sent_to_llm": context_used,
                "generated_sql": gen_sql,
                "execution_result_sample": [str(row) for row in sample_rows],
                "validity_score": int(is_valid),
                "accuracy_score": int(is_accurate),
                "retrieval_latency": retrieval_latency,
                "llm_latency": llm_latency,
                "total_latency": q_total_latency,
                "paths_before_pruning": paths_before_pruning,
                "paths_after_pruning": paths_after_pruning,
                "pruning_reduction_pct": pruning_reduction_pct
            })
            
            print(f"[{idx+1}/{len(dataset)}] Q: {question}")
            print(f"       Valid: {'Yes' if is_valid else 'No'} | Accurate: {'Yes' if is_accurate else 'No'}")
            
        avg_validity = total_validity / len(dataset)
        avg_accuracy = total_accuracy / len(dataset)
        total_run_latency = (time.time() - start_time) / len(dataset)
        
        # Log metrics
        mlflow.log_metrics({
            "avg_sql_validity": avg_validity,
            "avg_sql_accuracy": avg_accuracy,
            "avg_latency_sec": total_run_latency
        })
        
        # Log detailed query reports as artifact
        mlflow.log_dict(query_logs, "detailed_query_logs.json")
        
        if phase1:
            report_lines = ["# Phase 1: Location-Aware Schema Linking Validation\n"]
            for log in query_logs:
                report_lines.append(f"## Q{log['question_id']}: {log['question']}")
                report_lines.append(f"- **Entities Detected**: {json.dumps(log['entities_detected'])}")
                report_lines.append(f"- **Retrieved Tables**: {log['retrieved_tables']}")
                report_lines.append(f"- **Validity**: {'Yes' if log['validity_score'] else 'No'}")
                report_lines.append(f"- **Accuracy**: {'Yes' if log['accuracy_score'] else 'No'}\n")
                
                report_lines.append("### Detailed Retrieval Scores")
                for col_detail in log['retrieved_columns_detailed']:
                    report_lines.append(f"- `{col_detail['column']}` (Score: {col_detail['rerank_score']:.4f}) - Reason: {col_detail['reason']}")
                report_lines.append("\n---\n")
                
            with open("phase1_location_fix_report.md", "w") as f:
                f.write("\n".join(report_lines))
            print("\nGenerated phase1_location_fix_report.md")
            
        if phase1_2:
            report_lines = ["# Phase 1.2: Anchor Table Promotion Validation Report\n"]
            for log in query_logs:
                report_lines.append(f"## Q{log['question_id']}: {log['question']}")
                report_lines.append(f"- **Entities Detected**: {json.dumps(log['entities_detected'])}")
                report_lines.append(f"- **Location Detected**: {log['location_detected']}")
                report_lines.append(f"- **Anchor Tables Before Promotion**: {log['anchor_tables_before_promotion']}")
                report_lines.append(f"- **Forced Anchor Tables**: {log['forced_anchor_tables']}")
                report_lines.append(f"- **Anchor Tables After Promotion**: {log['anchor_tables_after_promotion']}")
                report_lines.append(f"- **Retrieved Tables**: {log['retrieved_tables']}")
                report_lines.append(f"- **Graph Paths Generated**: {json.dumps(log['graph_paths'], indent=2)}")
                report_lines.append(f"- **Validity**: {'Yes' if log['validity_score'] else 'No'}")
                report_lines.append(f"- **Accuracy**: {'Yes' if log['accuracy_score'] else 'No'}\n")
                report_lines.append("---\n")
                
            with open("phase1_2_anchor_validation_report.md", "w") as f:
                f.write("\n".join(report_lines))
            print("\nGenerated phase1_2_anchor_validation_report.md")
            
        if phase2:
            report_lines = ["# Phase 2: Table-Aware Retrieval & Anchor Selection Report\n"]
            for log in query_logs:
                report_lines.append(f"## Q{log['question_id']}: {log['question']}")
                report_lines.append(f"- **Retrieved Columns**: {log['retrieved_columns']}")
                report_lines.append(f"- **Selected Anchor Tables**: {log['retrieved_tables']}")
                report_lines.append(f"- **Forced Anchor Tables**: {log['forced_anchor_tables']}")
                report_lines.append(f"- **Validity**: {'Yes' if log['validity_score'] else 'No'}")
                report_lines.append(f"- **Accuracy**: {'Yes' if log['accuracy_score'] else 'No'}\n")
                
                report_lines.append("### Aggregated Table Scores")
                for table, scores in sorted(log['table_scores'].items(), key=lambda x: x[1]['table_score'], reverse=True):
                    report_lines.append(f"- **{table}**: {scores['table_score']:.4f} (Max Col: {scores['max_column_score']:.4f}, Count: {scores['column_count']})")
                
                report_lines.append("\n### Graph Paths")
                report_lines.append(f"```json\n{json.dumps(log['graph_paths'], indent=2)}\n```\n")
                report_lines.append("---\n")
                
            with open("phase2_table_retrieval_report.md", "w") as f:
                f.write("\n".join(report_lines))
            print("\nGenerated phase2_table_retrieval_report.md")
            
        if phase3:
            report_lines = ["# Phase 3: Graph-Native Expansion Report\n"]
            for log in query_logs:
                report_lines.append(f"## Q{log['question_id']}: {log['question']}")
                report_lines.append(f"- **Seed Tables**: {log['seed_tables']}")
                report_lines.append(f"- **Graph Expansion Hops**: {log['graph_expansion_hops']}")
                report_lines.append(f"- **Expanded Relevant Tables**: {log['retrieved_tables']}")
                report_lines.append(f"- **Paths Before Pruning**: {log.get('paths_before_pruning', 0)}")
                report_lines.append(f"- **Paths After Pruning**: {log.get('paths_after_pruning', 0)} ({log.get('pruning_reduction_pct', 0.0):.1f}% reduction)")
                report_lines.append(f"- **Validity**: {'Yes' if log['validity_score'] else 'No'}")
                report_lines.append(f"- **Accuracy**: {'Yes' if log['accuracy_score'] else 'No'}\n")
                
                report_lines.append("\n### Graph Paths")
                report_lines.append(f"```json\n{json.dumps(log['graph_paths'], indent=2)}\n```\n")
                report_lines.append("---\n")
                
            with open("phase3_graph_expansion_report.md", "w") as f:
                f.write("\n".join(report_lines))
            print("\nGenerated phase3_graph_expansion_report.md")
            
        if first30:
            report_lines = ["# Evaluation Report: First 30 Questions\n"]
            for log in query_logs:
                report_lines.append(f"## Q{log['question_id']}: {log['question']}")
                report_lines.append(f"- **Seed Tables**: {log['seed_tables']}")
                report_lines.append(f"- **Expanded Relevant Tables**: {log['retrieved_tables']}")
                report_lines.append(f"- **Validity**: {'Yes' if log['validity_score'] else 'No'}")
                report_lines.append(f"- **Accuracy**: {'Yes' if log['accuracy_score'] else 'No'}\n")
                report_lines.append("---\n")
                
            with open("first30_evaluation_report.md", "w") as f:
                f.write("\n".join(report_lines))
            print("\nGenerated first30_evaluation_report.md")

        if first15:
            report_lines = ["# Evaluation Report: First 15 Questions\n"]
            for log in query_logs:
                report_lines.append(f"## Q{log['question_id']}: {log['question']}")
                report_lines.append(f"- **Seed Tables**: {log['seed_tables']}")
                report_lines.append(f"- **Expanded Relevant Tables**: {log['retrieved_tables']}")
                report_lines.append(f"- **Validity**: {'Yes' if log['validity_score'] else 'No'}")
                report_lines.append(f"- **Accuracy**: {'Yes' if log['accuracy_score'] else 'No'}\n")
                report_lines.append("---\n")
                
            with open("first15_evaluation_report.md", "w") as f:
                f.write("\n".join(report_lines))
            print("\nGenerated first15_evaluation_report.md")

        if next20:
            report_lines = ["# Evaluation Report: Next 20 Questions\n"]
            for log in query_logs:
                report_lines.append(f"## Q{log['question_id']}: {log['question']}")
                report_lines.append(f"- **Seed Tables**: {log['seed_tables']}")
                report_lines.append(f"- **Expanded Relevant Tables**: {log['retrieved_tables']}")
                report_lines.append(f"- **Validity**: {'Yes' if log['validity_score'] else 'No'}")
                report_lines.append(f"- **Accuracy**: {'Yes' if log['accuracy_score'] else 'No'}\n")
                report_lines.append("---\n")
                
            with open("next20_evaluation_report.md", "w") as f:
                f.write("\n".join(report_lines))
            print("\nGenerated next20_evaluation_report.md")

        if last15:
            report_lines = ["# Evaluation Report: Last 15 Questions\n"]
            for log in query_logs:
                report_lines.append(f"## Q{log['question_id']}: {log['question']}")
                report_lines.append(f"- **Seed Tables**: {log['seed_tables']}")
                report_lines.append(f"- **Expanded Relevant Tables**: {log['retrieved_tables']}")
                report_lines.append(f"- **Validity**: {'Yes' if log['validity_score'] else 'No'}")
                report_lines.append(f"- **Accuracy**: {'Yes' if log['accuracy_score'] else 'No'}\n")
                report_lines.append("---\n")
                
            with open("last15_evaluation_report.md", "w") as f:
                f.write("\n".join(report_lines))
            print("\nGenerated last15_evaluation_report.md")
        
        print(f"\nCompleted {run_name}")
        print(f"Validity: {avg_validity}, Accuracy: {avg_accuracy}, Avg Latency: {total_run_latency:.2f}s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SQL Generation Experiments")
    parser.add_argument("--pipeline", type=str, choices=["baseline", "hybrid", "both"], default="hybrid", help="Which pipeline to run")
    parser.add_argument("--provider", type=str, choices=["groq", "ollama"], default="groq", help="LLM provider")
    parser.add_argument("--model", type=str, default="llama-3.3-70b-versatile", help="Model name")
    parser.add_argument("--phase1", action="store_true", help="Run Phase 1 Validation ONLY")
    parser.add_argument("--phase1_2", action="store_true", help="Run Phase 1.2 Validation ONLY")
    parser.add_argument("--phase2", action="store_true", help="Run Phase 2 Validation ONLY")
    parser.add_argument("--phase3", action="store_true", help="Run Phase 3 Validation ONLY")
    parser.add_argument("--first30", action="store_true", help="Run on the first 30 questions")
    parser.add_argument("--first15", action="store_true", help="Run on the first 15 questions")
    parser.add_argument("--next20", action="store_true", help="Run on the next 20 questions (16-35)")
    parser.add_argument("--last15", action="store_true", help="Run on the last 15 questions")
    parser.add_argument("--onehop", action="store_true", help="Run only on 1-hop queries (exactly 1 JOIN)")
    parser.add_argument("--only_q8", action="store_true", help="Run only on Q8")
    args = parser.parse_args()

    # If user switches to ollama but leaves default model, auto-switch to qwen2.5
    if args.provider == "ollama" and args.model == "llama-3.3-70b-versatile":
        args.model = "qwen2.5"

    MODEL = args.model
    PROVIDER = args.provider
    EXPERIMENT = "SQL_Generation_Comparison_V3"
    
    if args.pipeline in ["baseline", "both"]:
        run_experiment(EXPERIMENT, "Vector_RAG_Baseline", "vector", MODEL, PROVIDER, phase1=args.phase1, phase1_2=args.phase1_2, phase2=args.phase2, phase3=args.phase3, first30=args.first30, first15=args.first15, next20=args.next20, last15=args.last15, onehop=args.onehop, only_q8=args.only_q8)
    
    if args.pipeline in ["hybrid", "both"]:
        run_experiment(EXPERIMENT, "Hybrid_GraphRAG_Enhanced", "hybrid", MODEL, PROVIDER, phase1=args.phase1, phase1_2=args.phase1_2, phase2=args.phase2, phase3=args.phase3, first30=args.first30, first15=args.first15, next20=args.next20, last15=args.last15, onehop=args.onehop, only_q8=args.only_q8)
    
    print("\nExperiments finished! Run `python -m uv run mlflow ui` to view the detailed logs.")
