# SchemaNavigator: Evaluation-Driven Graph-Native Text-to-SQL

This project implements a state-of-the-art **Graph-Native Text-to-SQL Retrieval Pipeline**, specifically designed to conquer the architectural bottlenecks of standard Vector RAG when applied to highly normalized, multi-hop relational databases (like Microsoft AdventureWorks).

The architecture was systematically evolved through extensive MLflow-driven experimentation, proving that standard semantic search cannot reliably map complex foreign-key relationships on its own.

## The Technical Bottlenecks Conquered

### 1. The Vector Search Fragmentation Problem
Standard RAG relies on chunking DDL statements and running cosine similarity against a user query. 
* **The Failure Mode:** If a user asks *"List categories for customers in London"*, the vector DB finds the `Address` table (semantic match for London) and the `ProductCategory` table, but entirely misses the intermediate tables (`CustomerAddress`, `Customer`, `SalesOrderHeader`, `SalesOrderDetail`, `Product`) because they have no semantic overlap with the prompt.
* **The Result:** The LLM hallucinates non-existent direct JOINs between `Address` and `ProductCategory`.

### 2. The Cross-Encoder Logit Bias
Initial attempts used a Cross-Encoder (`ms-marco-MiniLM-L-6-v2`) to rerank tables.
* **The Failure Mode:** Highly optimized rerankers create massive logit gaps between the top 2 tables and the rest, making dynamic score thresholds impossible to balance. It aggressively truncated necessary "seed" tables before they could be expanded.
* **The Fix:** We implemented a **Dual-Score Fusion Strategy**. We bypassed the reranker for seed selection, relying instead on raw Vector frequencies to surface the top structural anchors.

### 3. Graph-Native Subgraph Expansion
Once the optimal seed tables are selected by the Vector DB, the deterministic Graph pipeline takes over.
* **The Architecture:** We map the entire SQL schema into a `NetworkX` directed graph. 
* **The Solution:** The pipeline dynamically traverses **N-hops** outward from the semantic seed tables, generating a complete, explicitly connected subgraph. Instead of guessing JOINs, the LLM is handed the exact foreign-key mappings linking every table in the graph.

### 4. Targeted Schema Fallback Fetching
* **The Failure Mode:** Graph expansion structurally discovers tables that the Vector DB completely missed during the initial semantic search. If we only pass the table names to the LLM, it won't know their schema.
* **The Solution:** We implemented a targeted `$in` query fallback loop. For any table discovered via Graph Expansion that wasn't in the initial semantic payload, we query ChromaDB directly for its raw DDL chunk, guaranteeing 100% schema context availability.

---

## Evaluation Metrics (First 256 Queries)

When executing this **SchemaNavigator Hybrid Pipeline** on a frontier model (`Groq Llama-3-70b`), the results validate the architectural redesign:

- **Validity:** 100% (0 Syntax Errors generated)
- **Accuracy:** 88.2% (+58.2% vs standard Vector Baseline)
- **Complex Multi-Hop Accuracy:** 84.6% (compared to 14.8% on standard Baseline)

*Note: The remaining accuracy gap strictly belongs to semantic business logic (e.g., whether to calculate Revenue with or without discounts), which can be solved with a Business Glossary injection layer.*

---

## Key Engineering Observations

Throughout the development and rigorous evaluation of this pipeline, several core insights emerged about the nature of Text-to-SQL architecture:

1. **Semantic Relevance != Schema Relevance**
   CrossEncoder relevance scores do not correlate with schema importance. Tables like `Address` and `ProductCategory` were essential for correct SQL generation but consistently received low semantic scores because they represented attributes rather than primary entities in the user query.

2. **Retrieval Success != Reasoning Success**
   Retrieving the correct table is not enough. The system must identify that table as structurally important and expose it to downstream graph reasoning. Missing anchor tables caused graph traversal failures even when the correct tables were present in retrieval results.

3. **Reranking Can Hurt Structured Reasoning**
   Traditional reranking improved semantic relevance but reduced SQL accuracy. Rerankers compressed structurally important tables into low-scoring buckets, preventing the graph from discovering valid multi-hop join paths.

4. **Connected Context Beats Large Context**
   Providing a smaller but fully connected subgraph produced significantly better SQL generation than supplying a large collection of disconnected schema chunks.

5. **Graph Structure Is More Valuable Than Raw Retrieval**
   Foreign-key relationships contain powerful reasoning signals. Graph expansion enabled the system to discover tables naturally through schema topology rather than semantic similarity alone.

6. **Multi-Hop SQL Is Primarily a Retrieval Problem**
   Many SQL generation failures initially appeared to be LLM reasoning limitations. Detailed tracing revealed that most errors originated from missing schema context rather than model limitations.

7. **Better Retrieval Reduces Dependence on Larger Models**
   After improving retrieval and graph expansion, smaller local models produced outputs similar to frontier models on many benchmark queries, demonstrating that retrieval quality often has a greater impact than raw model parameter size for this task.

8. **Observability Accelerates Iteration**
   MLflow-based query tracing enabled the inspection of retrieved tables, graph paths, generated SQL, latency, and evaluation metrics for every query, allowing rapid identification of bottlenecks and data-driven improvements.

9. **Schema Navigation Is A Distinct Problem**
   Text-to-SQL is not solely a language understanding problem. It is fundamentally a schema navigation problem that requires discovering relevant regions of a relational graph before SQL generation can occur.

---

## Analytics Dashboard

We include a standalone **Streamlit + Plotly Dashboard** for visualizing the real-time performance and pipeline flow (including an interactive Sankey diagram of the architecture).

```bash
# Launch the dashboard locally
python -m streamlit run dashboard.py
```

---

## Getting Started

### Prerequisites
1. **Python 3.11+**
2. **[uv](https://github.com/astral-sh/uv)** (Fast Python package manager)
3. **[Ollama](https://ollama.com/)** (For local inference) or **Groq API** (for frontier inference)

### 1. Installation
Clone the repository, then use `uv` to install all dependencies:
```bash
uv sync
```

### 2. Setup Groq (Recommended for Production Accuracy)
1. Ensure you have a `.env` file in the root directory.
2. Add your Groq API key:
   ```env
   GROQ_API_KEY=your-api-key-here
   ```

### 3. Run the Evaluation Pipeline
To execute the end-to-end pipeline over the dataset and track it in MLflow:

```bash
# Run the Graph-Native pipeline using Groq for the first 30 queries
python -m uv run python -m experiments.run_comparison --pipeline hybrid --provider groq --first30
```

### 4. View MLflow Traces
Inspect the execution traces, latency, and exact generated subgraphs in the MLflow UI:
```bash
python -m uv run mlflow ui
```
Open your browser to `http://127.0.0.1:5000` and navigate to the **Traces** tab.

---
*Built for rigorous, evaluation-driven AI engineering.*
