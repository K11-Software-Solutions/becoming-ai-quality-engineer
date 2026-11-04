"""NimbusNotes Help Assistant: a small RAG app used as the hands-on project.

The app answers questions about a fictional product (NimbusNotes) using only
the Markdown documents in ``app/data/docs``. It runs fully offline with a
deterministic fake LLM, so every test and eval in this repo passes without an
API key. Set ``LLM_PROVIDER=openai`` or ``LLM_PROVIDER=anthropic`` to use a
real model.
"""
