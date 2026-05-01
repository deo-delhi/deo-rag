# Refining Plan for DEO RAG Answers

## Goal
Improve answer quality so the app does not:
- return "The document does not contain this information" when relevant sources exist
- leak internal labels like `STRUCTURED`, `FACT/SHORT`, or `DESCRIPTIVE`
- produce incomplete or truncated answers on descriptive DEO records questions
- drift into unsupported general knowledge when the retrieved context is sufficient

## Observed Failure Modes
From the `systemllm.xlsx` evaluation sheet:
- Some answers are good, but a subset are too short compared with the ideal answer.
- Some answers append the no-information sentence after already giving a valid answer.
- Some answers leak internal labels from the prompt.
- Some answers use unsupported information when the model should stay grounded.

## Implementation Order

### 1. Simplify the main answer prompt
Replace the current multi-phase instruction block with a shorter prompt that:
- uses retrieved context only
- allows partial but relevant evidence to be answered
- forbids internal labels in the output
- reserves the exact no-information sentence only for completely unrelated context

Acceptance criteria:
- The final answer never contains `STRUCTURED`, `FACT/SHORT`, `DESCRIPTIVE`, `Mode`, or `Classification`.
- The model does not add the fallback sentence after a valid answer.

### 2. Separate refusal logic from answer generation
Refusal should be a last resort, not part of the main reasoning path.

Implementation details:
- If retrieval returns documents, the app should first try to answer from those sources.
- Only if the retrieval is empty or clearly unrelated should the app return the no-information sentence.
- Do not let the LLM decide refusal after it already received relevant sources.

Acceptance criteria:
- Questions with relevant sources do not end in a refusal by default.

### 3. Add a second-pass fallback answer path
If the first pass is too conservative, regenerate from the same retrieved chunks using a simpler prompt.

Implementation details:
- Build a fallback prompt with fewer instructions.
- Pass the retrieved source documents directly into the fallback answer generator.
- Use a larger token budget for the fallback than the first pass.

Acceptance criteria:
- When the first answer is too strict, the second pass produces a grounded best-effort answer.

### 4. Add incomplete-answer detection
Detect answers that are likely truncated or incomplete.

Suggested checks:
- response is very short relative to the expected answer length
- response ends abruptly without proper punctuation
- response contains leaked labels
- response contains the no-information sentence even though sources exist

Acceptance criteria:
- Incomplete answers automatically trigger a retry.
- The app does not silently keep a cut-off answer when a retry can improve it.

### 5. Add an extractive rescue path
If the LLM still refuses despite having sources, generate a direct extractive answer from the retrieved chunks.

Implementation details:
- Select the most relevant sentences from retrieved documents.
- Prefer sentences that overlap with the question terms.
- Use this only when sources exist and the LLM still returns the no-information sentence.

Acceptance criteria:
- The app returns a grounded answer rather than a false refusal when relevant chunks are present.

### 6. Increase generation budget for descriptive questions
The current output budget is too small for some longer DEO records explanations.

Implementation details:
- Raise `ollama_num_predict` for answer generation.
- Keep a smaller budget only for short factual queries if needed.
- Do not rely on a low token cap for descriptive questions.

Acceptance criteria:
- Longer answers are not cut off midway.
- Descriptive questions produce complete, multi-point responses.

### 7. Keep retrieval stable, but verify it with scores
Retrieval appears mostly correct, but it should still be inspected.

Implementation details:
- Use the debug retrieval endpoint or equivalent instrumentation.
- Log retrieved chunk text, source, page, and similarity scores during testing.
- Compare top chunks against the ideal answers in the spreadsheet.

Acceptance criteria:
- You can see exactly which chunks led to each answer.
- Retrieval problems can be separated from generation problems.

### 8. Build a regression test set from the spreadsheet
Use `systemllm.xlsx` as a gold-style evaluation set.

Track these categories:
- false no-information response
- label leakage
- truncated answer
- unsupported answer drift
- incomplete answer despite good sources

Acceptance criteria:
- After each change, run the same question set and compare results.
- The number of false refusals and truncated answers goes down.

## Recommended Metrics
Track these for each question:
- retrieved source count
- top similarity score
- whether fallback was triggered
- whether rescue extraction was triggered
- answer length
- presence of leaked labels
- presence of the no-information sentence

## Suggested File-Level Changes
- `backend/rag_pipeline.py`
  - simplify prompt
  - relax refusal behavior
  - add fallback prompt and fallback generator
- `backend/app.py`
  - add incomplete-answer detection
  - add second-pass retry
  - add extractive rescue path
  - optionally return debug flags like `used_fallback` or `used_rescue`
- `documents/systemllm.xlsx`
  - use as a regression benchmark, not as a runtime dependency

## Done Criteria
The implementation is complete when:
- questions with relevant sources no longer get false refusals
- descriptive answers are not obviously truncated
- internal labels never appear in the user-facing answer
- source-backed questions return grounded answers consistently
- the spreadsheet shows fewer mismatches against the ideal answers

## Next Step
Implement the changes in this order:
1. prompt simplification
2. refusal separation
3. retry and rescue logic
4. regression testing against the spreadsheet
