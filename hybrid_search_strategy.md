# Hybrid Search Strategy: Combining Vector and Keyword Search

## 1. The "Why": Understanding the Power of Hybrid Search

Currently, the application uses **semantic search**, which is excellent at understanding the *intent* and *context* behind a query. For example, it knows that "what are the tax implications of selling a small company" is similar to "small business CGT concessions."

However, it can sometimes struggle with specific keywords, acronyms, or product codes that a user might search for verbatim. This is where **keyword search** (or full-text search) excels.

**Hybrid search** combines both approaches, giving you the best of both worlds:
-   **Semantic Search (Vectors):** Finds conceptually related documents, even if they don't share keywords.
-   **Keyword Search (Full-Text):** Finds documents with exact term matches, which is critical for precision.

## 2. How It Works in Supabase (PostgreSQL)

To implement hybrid search, you would perform two separate queries against your data and then intelligently merge the results.

1.  **Vector Search (Existing):** You already have this implemented using the `pgvector` extension. You search for vectors with the lowest distance/highest similarity to your query vector.
2.  **Full-Text Search (New):** You would use PostgreSQL's built-in full-text search capabilities. This involves:
    *   **Indexing:** Creating a special `tsvector` column in your documents table. A `tsvector` is an optimized representation of a document, stripped of common "stop words" (like 'a', 'the', 'is') and with words reduced to their root form (a process called "stemming"). For example, "running" and "ran" both become "run".
    *   **Querying:** Using functions like `to_tsquery()` to convert the user's search text into a query format and `ts_rank()` to score the results based on how well they match.

## 3. The Core Challenge: Combining and Ranking Results

This is the main point of your question. You cannot simply add the similarity score from the vector search and the relevance score from the keyword search. They are calculated differently and are not on the same scale.

The industry-standard solution for this is **Reciprocal Rank Fusion (RRF)**.

### What is Reciprocal Rank Fusion?

RRF is an elegant and effective algorithm for combining multiple result sets. Instead of looking at the *scores* of the results, it looks only at their *rank* in each list. This makes it perfect for combining different search types.

The formula is simple: for each document, its RRF score is the sum of the reciprocal of its rank in each result list.

\[ \text{RRF Score}(d) = \sum_{i \in \text{result lists}} \frac{1}{k + \text{rank}_i(d)} \]

-   `d` is a specific document.
-   `rank_i(d)` is the rank of document `d` in result list `i`.
-   `k` is a constant (a common choice is 60). It helps ensure that documents ranked lower in a list still contribute to the final score without being overly penalized.

### A Simple Example:

Let's say you search for "restraint of trade clause."

-   **Vector Search Results:**
    1.  `doc_A` (A guide to employment contracts)
    2.  `doc_B` (What is a restraint of trade?)
    3.  `doc_C` (Non-compete agreement examples)

-   **Keyword Search Results:**
    1.  `doc_B` (Title contains "restraint of trade")
    2.  `doc_D` (A case study on post-employment clauses)
    3.  `doc_A` (Mentions "clause" frequently)

**RRF Calculation (with k=60):**

-   **Score(doc_A):** `1/(60+1)` [from vector] + `1/(60+3)` [from keyword] = `0.0164 + 0.0159 = 0.0323`
-   **Score(doc_B):** `1/(60+2)` [from vector] + `1/(60+1)` [from keyword] = `0.0161 + 0.0164 = 0.0325`
-   **Score(doc_C):** `1/(60+3)` [from vector] = `0.0159`
-   **Score(doc_D):** `1/(60+2)` [from keyword] = `0.0161`

**Final Hybrid Ranking:**

1.  `doc_B` (Score: 0.0325)
2.  `doc_A` (Score: 0.0323)
3.  `doc_D` (Score: 0.0161)
4.  `doc_C` (Score: 0.0159)

As you can see, `doc_B` rose to the top because it ranked highly in both search types, demonstrating both keyword and semantic relevance.

## 4. Proposed Plan of Action

Here is a high-level plan for how you could implement this:

1.  **Database Modification:**
    *   Add a `tsvector` column to your documents table in Supabase.
    *   Create a trigger that automatically populates this column whenever a document's text is inserted or updated.
    *   Create a GIN index on the `tsvector` column to make full-text searches fast.

2.  **Create a Supabase RPC Function:**
    *   It's best to create a custom database function (using `PL/pgSQL`) that you can call from your backend. This keeps the logic clean and contained.
    *   This function would accept the user's query string and the corresponding query vector as arguments.
    *   Inside the function, it would execute both the vector search and the full-text search in parallel, returning both sets of results (e.g., just the document IDs and their ranks).

3.  **Backend API (`rag_api_service`) Modification:**
    *   Update the `/search` endpoint in `rag_api_service/main.py`.
    *   It will now call your new Supabase RPC function instead of just the vector search.
    *   After getting the two ranked lists of document IDs, implement the RRF algorithm in Python to compute the final scores and sort the results.
    *   Fetch the full document details for the final, re-ranked list and return them to the frontend.

The frontend would not require any changes, as it would simply receive a more relevant list of results from the same API endpoint. 