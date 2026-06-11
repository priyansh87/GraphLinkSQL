import os
import time
from dotenv import load_dotenv
load_dotenv()
import ollama
from groq import Groq
from retrieval.hybrid import HybridRetriever
from prompts.sql_templates import build_sql_prompt

from vector.retriever import SchemaVectorRetriever

class SQLGenerator:
    def __init__(self, model_name: str = "qwen2.5", provider: str = "ollama", retrieval_mode: str = "hybrid"):
        """
        provider: 'ollama' or 'groq'
        retrieval_mode: 'hybrid' or 'vector'
        """
        self.model_name = model_name
        self.provider = provider.lower()
        self.retrieval_mode = retrieval_mode.lower()
        self.hybrid_retriever = HybridRetriever()
        self.vector_retriever = SchemaVectorRetriever()
        
        if self.provider == "groq":
            # Requires GROQ_API_KEY environment variable to be set
            self.groq_client = Groq()

    import mlflow
    @mlflow.trace(name="generate_sql")
    def generate_sql(self, question: str) -> dict:
        """
        End-to-end pipeline:
        1. Retrieve context (vector or hybrid)
        2. Format prompt
        3. Generate SQL via selected provider
        """
        # Step 1: Retrieval
        retrieval_data = {}
        if self.retrieval_mode == "vector":
            # Baseline: Only use semantic similarity without graph traversal or query expansion
            start_t = time.time()
            results, anchor_tables = self.vector_retriever.retrieve_columns_and_tables(question, top_k=5)
            context = "=== Semantic Schema Context ===\n" + "\n\n".join([res["document"] for res in results])
            retrieval_data = {
                "context": context,
                "retrieved_tables": anchor_tables,
                "retrieved_columns": [res["metadata"].get("column_name") for res in results],
                "retrieval_latency": time.time() - start_t
            }
        else:
            # Enhanced V3 Pipeline
            retrieval_data = self.hybrid_retriever.retrieve_context(question, top_k=25)
            context = retrieval_data["context"]
        
        # Step 2: Prompt Formatting
        prompt = build_sql_prompt(context, question)
        
        # Step 3: Generation
        sql = ""
        llm_start_time = time.time()
        
        if self.provider == "ollama":
            response = ollama.generate(model=self.model_name, prompt=prompt)
            sql = response['response'].strip()
        elif self.provider == "groq":
            from groq import RateLimitError
            
            # Explicitly schedule the request with a small timer to space out TPM/RPM limits
            time.sleep(2)
            
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    response = self.groq_client.chat.completions.create(
                        messages=[
                            {"role": "user", "content": prompt}
                        ],
                        model=self.model_name,
                    )
                    sql = response.choices[0].message.content.strip()
                    break
                except RateLimitError as e:
                    if attempt == max_retries - 1:
                        raise e
                    print(f"RateLimitError hit. Sleeping for 60 seconds... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(60)
            
        llm_latency = time.time() - llm_start_time
            
        # Clean markdown if model ignored the prompt constraint
        if sql.startswith("```sql"):
            sql = sql[6:].strip()
            if sql.endswith("```"):
                sql = sql[:-3].strip()
        elif sql.startswith("```"):
            sql = sql[3:].strip()
            if sql.endswith("```"):
                sql = sql[:-3].strip()
        
        retrieval_data.update({
            "question": question,
            "sql": sql,
            "llm_latency": llm_latency
        })
        
        return retrieval_data

if __name__ == "__main__":
    generator = SQLGenerator(model_name="qwen2.5", provider="ollama")
    question = "List the top 5 product categories by total products"
    result = generator.generate_sql(question)
    print("--- GENERATED SQL ---")
    print(result["sql"])
