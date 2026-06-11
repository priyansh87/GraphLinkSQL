def build_query_expansion_prompt(question: str) -> str:
    """
    Generates a prompt to ask the LLM to expand the user's natural language question
    into alternative synonyms and business terms to improve semantic retrieval.
    """
    return f"""You are a query expansion assistant for an SQL database.
Your goal is to take the user's question and expand it with synonyms, alternate phrasings, and business context terms to improve vector search recall.

For example, if the user asks for "clients", you should expand it to include "customers".
If the user asks for "money", expand it to "revenue, sales, total due, list price".

USER QUESTION:
{question}

Generate a concise, comma-separated list of 3-5 alternative search phrases or keywords.
DO NOT provide any conversational text. ONLY provide the expanded keywords.

EXPANDED KEYWORDS:"""
