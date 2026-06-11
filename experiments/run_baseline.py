import mlflow
import time
from generation.llm import SQLGenerator
from evaluation.dataset import load_dataset
from evaluation.metrics import SQLEvaluator

def run_experiment(experiment_name: str, run_name: str):
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment(experiment_name)
    
    # generator = SQLGenerator(model_name="qwen2.5")
    generator = SQLGenerator(model_name="llama-3.3-70b-versatile", provider="groq")
    evaluator = SQLEvaluator()
    dataset = load_dataset()
    
    with mlflow.start_run(run_name=run_name):
        # Log parameters
        mlflow.log_params({
            "retrieval_type": "hybrid",
            "embedding_model": "BAAI/bge-small-en-v1.5",
            "top_k": 5,
            "reranker": "cross-encoder/ms-marco-MiniLM-L-6-v2",
            "llm": generator.model_name
        })
        
        total_validity = 0
        total_accuracy = 0
        
        start_time = time.time()
        
        for item in dataset:
            question = item["question"]
            gt_sql = item["ground_truth_sql"]
            
            # Generate
            result = generator.generate_sql(question)
            gen_sql = result["sql"]
            
            # Evaluate
            metrics = evaluator.evaluate(gen_sql, gt_sql)
            
            total_validity += metrics["sql_validity"]
            total_accuracy += metrics["sql_accuracy"]
            
        end_time = time.time()
        
        # Calculate averages
        avg_validity = total_validity / len(dataset)
        avg_accuracy = total_accuracy / len(dataset)
        avg_latency = (end_time - start_time) / len(dataset)
        
        # Log metrics
        mlflow.log_metrics({
            "avg_sql_validity": avg_validity,
            "avg_sql_accuracy": avg_accuracy,
            "avg_latency_sec": avg_latency
        })
        
        print(f"Experiment {run_name} completed.")
        print(f"Validity: {avg_validity}, Accuracy: {avg_accuracy}, Latency: {avg_latency}s")

if __name__ == "__main__":
    run_experiment("SQL_Generation_Evaluation", "Hybrid_GraphRAG_Baseline")
