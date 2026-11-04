# 08. Portfolio and Interview Preparation

> **Series:** Becoming an AI Quality Engineer · [Index](../README.md#article-index) · Previous: [07](07-investigating-failures.md)

Hiring managers for AI quality roles want evidence that you can **reason about** an AI system's quality, not just run a tool. A small project you can explain end to end beats a long list of tools on a CV. This article shows how to turn this repo (or your fork of it) into that evidence.

## 1. Make the project yours

A fork with no changes proves little. Before you show it, add at least:

- **your own documents** (a domain you know: banking FAQs, an internal tool's help pages, a public product's docs),
- **15 or more dataset rows you wrote**, including new adversarial and fairness cases,
- **one failure you found, investigated and fixed**, written up in the format from article 07,
- **one real-model run** compared with the fake model, if you can afford a few cents of API usage.

## 2. Explain the architecture in 60 seconds

Practise saying this out loud until it is natural:

> "It's a small retrieval-augmented Q&A service in FastAPI. A question goes through an input guardrail, then a BM25 retriever pulls the top three paragraph chunks from the help docs. Untrusted content is labelled and scrubbed of instruction-like text before it goes into the prompt. The model must answer only from that context, cite chunk IDs, or say it doesn't know. Every request is traced per stage. The model sits behind a one-method interface, so CI uses a deterministic fake and I can swap in OpenAI or Anthropic with an environment variable."

Then be ready to draw it (the diagram in article 06) and to say **where each kind of failure would show up**.

## 3. Explain your test choices

Interviewers want to hear *why*, not just *what*. A good structure is "risk → test → evidence":

| Risk | Test choice | Why this layer |
|---|---|---|
| API contract breaks the UI or clients | pytest API tests for fields, 422s, 502 on provider failure | deterministic, fast, runs on every commit |
| The UI does not show answers or sources | 3 Playwright tests, role/label locators | covers the user journey without asserting on LLM wording |
| Wrong or invented answers | golden dataset with key-fact correctness and groundedness | many valid wordings, so check facts and support, not strings |
| Search returns the wrong documents | hit rate and MRR on labelled `expected_sources` | separates search bugs from model bugs |
| Prompt injection | direct and indirect attack cases, 100% gate | one failure can be a security incident |
| Unequal treatment | counterfactual persona groups | cheap, targeted, explainable |
| The evaluator is wrong | judge vs 16 human labels, Cohen's kappa | you cannot trust a gate you have not measured |
| The gate itself is broken | negative control: hallucinating model must fail CI | protects against loosened thresholds |

## 4. Present results honestly

Quote numbers, and quote the failures alongside them. For the baseline fake model:

> "34 cases, 31 pass. Correctness 0.93, groundedness 1.0, retrieval hit rate 1.0, injection resistance 1.0, consistency 0.75. Three known failures, each investigated: a ranking-plus-generation error on 'how long' questions, a failure to refuse on an out-of-scope question, and over-refusal on a paraphrase. The heuristic groundedness judge agrees with my human labels at kappa 0.62, and its false positives are a flipped negation and a changed number, so I back it with key-fact checks."

That paragraph shows more seniority than "all tests green".

## 5. Know and state the limitations

Every interviewer will probe this. Say it before they do:

- **The fake model is not a real model.** It makes CI deterministic and free, but its failure patterns differ. Real-model evals belong in a scheduled job with trend tracking.
- **The dataset is small.** 34 cases give a smoke signal, not statistical confidence. One case moves correctness by about 4 points. I would grow it from production traces and report confidence intervals.
- **Token-overlap metrics are crude.** They miss negation and changed numbers (measured in the judge check). An LLM judge needs its own validation.
- **Keyword retrieval misses synonyms.** The synonym table is a patch; semantic or hybrid retrieval is the real fix.
- **Pattern-based guardrails are bypassable.** A unit test documents one bypass. Defence relies on layering, not on the regex list.
- **No load, latency or cost testing yet.** The next step would be p95 latency and cost-per-answer budgets with a real provider.

## 6. Common interview questions, with answer outlines

**"How do you test something non-deterministic?"**
Control what you can (temperature 0, pinned model versions, fixed seeds, a fake for CI); for the rest, test properties rather than exact strings (facts present, grounded, cites a source, refuses when it should); run multiple times and gate on rates with thresholds set from measured variance.

**"What is the difference between correctness and groundedness?"**
Correctness compares the answer with the truth; groundedness compares it with the retrieved context. A grounded answer can be wrong (wrong chunk, case `fact-002`), and a correct answer can be ungrounded (the model knew it from training). RAG systems need both.

**"How do you know your LLM-as-judge is reliable?"**
Label a sample by hand, run the judge on it, compute agreement and kappa, read every disagreement, especially false positives. Re-validate on any change to the judge model or prompt.

**"How would you test for prompt injection?"**
Direct attacks in user input; indirect attacks planted in documents, web pages or tool outputs; check that forbidden content never appears and that the model does not take actions it should not. Gate at 100%. Document known bypasses and rely on layered defences: least privilege, untrusted-content labelling, output checks, human approval for risky actions.

**"Where do evals go in CI?"**
Deterministic evals on every PR, after unit and API tests. Expensive real-model evals on a schedule or on demand, tracked as trends. And test the gate with a negative control.

**"A user reports a wrong answer. What do you do?"**
Reproduce, pull the trace, localise to a stage, classify, fix, and add the case to the golden set (article 07).

**"Which tools have you used, and which would you choose?"**
Choose by purpose: pytest and Playwright for the application, Promptfoo or DeepEval for evals, Langfuse or LangSmith for tracing. Explain what problem each solved in your project, not a feature list.

## 7. Behavioural stories (STAR)

Prepare two or three stories from this project and your QA past:

- **Situation:** "Our eval said groundedness was 100%, but a manual review found a wrong answer."
- **Task:** "Work out whether the model or the metric was wrong."
- **Action:** "Traced it, found the right chunk ranked third, and saw that groundedness can't detect a grounded-but-wrong answer; added key-fact correctness and a ranking metric."
- **Result:** "The case now fails as it should, and the team trusts the report because each metric has a known purpose and known blind spots."

## 8. Portfolio README checklist

- [ ] One paragraph: what the system does and who it is for
- [ ] Architecture diagram
- [ ] How to run it in under five minutes, with no paid key
- [ ] Test strategy table (risk → test → layer)
- [ ] Latest eval results with known failures
- [ ] Evaluator validation result
- [ ] Limitations and next steps
- [ ] A green CI badge

---
Back to the [index](../README.md#article-index).
