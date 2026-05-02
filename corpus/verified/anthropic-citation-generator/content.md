# Anthropic Citation Generator: Content Notes

## Short Excerpt

The prompt casts the model as an expert research assistant and asks it to answer questions about a provided document. It first asks for short relevant quotes, then an answer that references quote numbers.

Representative short phrases from the source prompt:

- "First, find the quotes"
- "Quotes should be relatively short"
- "If there are no relevant quotes"
- "Answer:"

## Structure Summary

The prompt uses this structure:

1. Role: expert research assistant.
2. Context: a source document is placed in the system prompt.
3. Retrieval step: find the most relevant short quotes from the document.
4. Fallback: say there are no relevant quotes if none exist.
5. Answer step: answer after the quote list.
6. Citation syntax: attach bracketed quote numbers to relevant answer claims.
7. Anti-verbatim constraint: do not repeat quoted content verbatim in the answer.
8. Unanswerable protocol: say when the document cannot answer the question.
9. Format example: shows `Quotes:` followed by numbered quotes, then `Answer:`.

## Prompt Mechanisms

- Separates evidence selection from answer generation.
- Forces the model to expose the evidence set before writing the final answer.
- Uses compact bracket citations instead of prose references like "according to Quote 1."
- Adds a no-answer path to reduce pressure to infer beyond the source.
- Gives a concrete output skeleton so the response format is predictable.

## Assumptions

- The full source document is available in the prompt or request context.
- Relevant evidence can be represented by short text quotes.
- The model can reliably select quotes before composing the answer.
- The user wants document-grounded answers rather than general knowledge.

## Failure Modes

- Prompt-only citations can still be invalid if the model fabricates, misquotes, or selects weak evidence.
- Long documents may make quote selection incomplete.
- The prompt does not provide API-level enforcement that cited spans truly exist.
- If the document is omitted, truncated, or stale, the answer may look grounded while being unsupported.

## Reusable Pattern

Use a two-stage evidence-first answer contract:

1. Extract short relevant evidence from the provided source.
2. Answer only after the evidence list.
3. Attach compact evidence IDs to claims.
4. Include an explicit no-evidence/no-answer path.

This pattern is useful for document QA, due diligence notes, policy review, and source-grounded summaries.

## Reuse Boundary

Do not treat this sample as a license to copy the full Anthropic prompt. Reuse the mechanism and structure, with attribution to the official source. For production citation workflows, prefer API-level or retrieval-system citation enforcement when available.
