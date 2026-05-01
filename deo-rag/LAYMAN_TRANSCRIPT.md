# DEO RAG Project Transcript (Layman Version)

Date: April 24, 2026

## 1) What We Set Out to Build

We built a local DEO records question-answer system from scratch.

In simple terms, we wanted this flow:
1. Upload DEO PDF files.
2. Break them into smaller readable parts.
3. Store those parts in a searchable memory (vector database).
4. Ask questions in plain language.
5. Get answers based only on the uploaded DEO records.

This gives a private, document-grounded assistant instead of a generic chatbot.

## 2) What We Built, Step by Step

### Step A: Core Stack and Plumbing

We connected:
- React frontend (user interface)
- FastAPI backend (API and logic)
- PostgreSQL + pgvector (searchable memory)
- LLM + embedding models (to understand questions and generate answers)

Result: basic end-to-end app where users could upload, ingest, and ask questions.

### Step B: Reliable PDF Parsing and Ingestion

We added a parser strategy with a main parser first and fallback parser second.

Why: not all PDFs behave the same way.

Result: better coverage across DEO PDFs, fewer ingestion failures.

### Step C: Background Ingestion Jobs and Status Tracking

Ingestion was moved to a background job with status updates.

Result: the UI can show progress instead of freezing.

### Step D: Retrieval + Answering Pipeline

We wired retrieval (find relevant chunks) to generation (write answer from those chunks).

Result: answers started being tied to actual source documents.

## 3) Problems We Faced and How We Solved Them

### Problem 1: Re-ingestion Could Break After Clear/Reset

What happened:
- If vector data was cleared, the next ingestion sometimes failed with "Collection not found".

Why it happened:
- The collection was deleted, but ingestion tried writing into it before recreating it.

Fix:
- We explicitly recreate the vector collection before adding new chunks.

Outcome:
- Re-ingestion became idempotent and stable.

---

### Problem 2: Clear Data During Active Ingestion Caused Conflicts

What happened:
- Users could try clearing data while ingestion was still running.
- Backend returned conflict (HTTP 409).

Why it happened:
- Clearing while writing can corrupt the run.

Fix:
- Backend blocks clear while ingestion is active.
- Frontend disables clear button and shows a clear explanation.

Outcome:
- Safer behavior, less confusion.

---

### Problem 3: Answers Were Sometimes Vague or Too Generic

What happened:
- Some answers were not specific enough even when documents existed.

Why it happened:
- Retrieval quality and chunk quality needed tuning.
- Similarity filtering/diversity needed visibility.

Fix:
- Added retrieval debug endpoints.
- Added score inspection, threshold retrieval, and MMR retrieval for diversity.
- Added tuning guidance for chunk size, overlap, top-k, and model choices.

Outcome:
- We can now diagnose whether a bad answer is a retrieval issue or generation issue.

---

### Problem 4: Internal Prompt Labels Leaked Into User Answers

What happened:
- Labels like STRUCTURED or FACT/SHORT could appear in final responses.

Why it happened:
- Prompt instructions were too complex and leaked formatting behavior.

Fix:
- Simplified the main prompt.
- Explicitly banned internal label text in output.

Outcome:
- Label leakage dropped to zero in current regression results.

---

### Problem 5: False Refusals ("No information") Even When Sources Existed

What happened:
- The system sometimes said the document had no answer despite retrieving relevant chunks.

Why it happened:
- Refusal behavior was too strict and triggered too early.

Fix:
- Separated refusal from normal answer generation.
- Added second-pass fallback answer path.
- Added extractive rescue path if model still refused despite sources.

Outcome:
- False no-information responses are now zero in the latest test run.

---

### Problem 6: Truncated or Incomplete Long DEO Records Answers

What happened:
- Longer descriptive questions could produce cut-off answers.

Why it happened:
- Token budget was too small and incomplete answers were not consistently retried.

Fix:
- Increased default generation budget (to 768).
- Increased fallback budget (to 1024).
- Added incomplete-answer detection and auto-retry logic.

Outcome:
- Truncation count is now zero in latest regression metrics.

---

### Problem 7: Hard to Know What Path the System Took Internally

What happened:
- We could not easily tell when fallback, rescue, or retries were happening.

Fix:
- Added debug metadata to /ask responses:
  - used_fallback
  - used_rescue
  - used_incomplete_detection
  - answer_length
  - retrieved_count
  - top_similarity_score

Outcome:
- Easier monitoring, faster debugging, safer future changes.

## 4) How We Validated the Improvements

We built a regression testing framework and ran a repeatable question set.

Latest summary (10 tests):
- Successful tests: 10/10
- False no-information responses: 0
- Label leakage: 0
- Truncated answers: 0
- Avg quality score: 91.5

This shows major stability and quality improvements compared to earlier behavior.

## 5) Honest Current Status (What Is Still Imperfect)

Even though the system is much better, quality is not perfect yet.

Example from latest report:
- "What is estate records?" returned a very short answer in one case.
- Similarity scores are still relatively low in multiple tests, which means retrieval can still be improved further.

So the platform is stable and usable, but we still have room to improve answer depth and retrieval precision.

## 6) Final Plain-English Summary

We successfully built a full DEO RAG system from scratch.

The hardest parts were not UI or API wiring, but making answers reliable:
- stopping false refusals,
- preventing label leakage,
- avoiding cut-off answers,
- and making ingestion/reset behavior safe.

We solved these with better prompting, fallback/rescue paths, stronger answer-completeness checks, richer debug visibility, and regression testing.

Today, the system is stable, measurable, and much more trustworthy than the first version.
