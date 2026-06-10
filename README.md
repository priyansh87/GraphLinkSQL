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
