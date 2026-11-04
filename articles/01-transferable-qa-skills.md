# 01. Transferable QA Skills: What You Already Know About Testing AI

> **Series:** Becoming an AI Quality Engineer · [Index](../README.md#article-index) · Next: [02. Python Essentials for QA](02-python-essentials-for-qa.md)

If you have tested web apps, APIs or data pipelines, you are not starting from zero. Most of AI quality engineering is ordinary quality engineering applied to a system whose outputs are **probabilistic, open-ended text** instead of fixed values. The skills carry over. What changes is the shape of the oracle (how you decide pass or fail) and how much you rely on statistics instead of single assertions.

This article maps six core QA skills to AI testing. Each section ends with where you can practise it in this repo.

## The map at a glance

| QA skill you have | What it becomes in AI testing | Practise it in |
|---|---|---|
| Test design | Designing **eval datasets**: categories, edge cases, adversarial cases | [`evals/datasets/golden_qa.jsonl`](../evals/datasets/golden_qa.jsonl) |
| Exploratory testing | **Probing model behaviour** with charters: refusals, injections, paraphrases | [`app/static/index.html`](../app/static/index.html) UI, `uvicorn app.main:app` |
| API testing | Testing the **AI service contract** and the **LLM provider** as a dependency | [`tests/api/test_api.py`](../tests/api/test_api.py) |
| SQL and data skills | Querying **traces and eval results**, checking **dataset quality** | [`evals/results/report.json`](../evals/run_evals.py), `TRACE_FILE` |
| Automation | **Evals in CI** as quality gates; handling **non-determinism** | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) |
| Risk assessment | **AI risk analysis**: harm, likelihood, who is affected | Section 6 below |

## 1. Test design becomes eval dataset design

Equivalence partitioning, boundary values and decision tables still work. You apply them to *questions* instead of form fields.

- **Equivalence classes.** Group inputs by the behaviour they should trigger. For a help assistant: answerable factual questions, multi-fact questions, unanswerable questions, prompt injections, paraphrases. The golden dataset in this repo uses a `category` field for exactly this.
- **Boundary values.** The maximum question length (500 characters here), the retrieval cut-off (`top_k`), the context window budget. Test just inside and just outside each one.
- **Negative testing.** Questions the system must refuse are as important as questions it must answer. A bot that answers everything confidently is worse than one that says "I don't know".
- **The oracle problem.** In classic testing the expected result is usually exact. With LLMs, many different answers can be correct. You replace `assertEqual` with checks such as "contains the key fact `30 days`", "every sentence is supported by the retrieved document", or a rubric graded by a person or a model. Article 04 covers these.

```jsonl
{"id": "fact-001", "category": "factual", "question": "Within how many days of the first payment can I get a full refund?", "expected_facts": ["30 days"], "expected_sources": ["refund-policy#1"], "should_refuse": false}
{"id": "unans-002", "category": "unanswerable", "question": "Can I pay with cryptocurrency?", "expected_facts": [], "should_refuse": true}
```

## 2. Exploratory testing becomes behaviour probing

Session-based exploratory testing is one of the most valuable skills you can bring. LLM systems have huge input spaces and surprising failure modes that scripted tests miss. Write short charters and time-box them:

- *Explore refusal behaviour with questions that are almost covered by the docs.* (You will find that "Does NimbusNotes have a Linux desktop app?" gets a confident, wrong answer in this repo.)
- *Explore how the assistant handles instructions hidden inside documents.*
- *Explore paraphrases, typos, shouting and other languages for the top five questions.*
- *Explore what happens when two documents disagree.*

Keep notes. Every interesting finding becomes a new row in the eval dataset, which is how exploratory work turns into regression protection.

## 3. API testing carries over almost unchanged

An AI feature is usually an HTTP service that calls another HTTP service (the model provider). Everything you know about API testing applies:

- **Contract tests:** response schema, required fields, types. See `test_ask_returns_contract_fields`.
- **Input validation:** empty, too long, wrong type, wrong field name, wrong content type. See `test_ask_validates_input`.
- **Dependency failures:** the provider times out, rate-limits you (HTTP 429) or returns 5xx. Your service should fail predictably. See `test_provider_failure_returns_502` and the retry helper in article 02.
- **Mocking the dependency:** `httpx.MockTransport` lets you test the provider client with no network and no API key.

The difference is that the *body* of a 200 response can still be wrong, which is why API tests are necessary but not sufficient.

## 4. SQL and data skills: datasets and traces are data

Two things in AI quality are pure data work.

**Dataset quality.** Your eval set is test data, and it can have bugs: duplicate IDs, wrong expected answers, questions that leak the answer, categories that are missing. Treat it like a database you need to validate. The loader in article 02 rejects duplicate IDs for this reason.

**Results and traces.** Eval results and request traces are tables. When a metric drops you will slice it: by category, by model, by prompt version, by retrieval rank. You can load the JSON report into SQLite with the standard library and query it with the SQL you already know:

```python
import json, sqlite3

report = json.load(open("evals/results/report.json"))
db = sqlite3.connect(":memory:")
db.execute("create table results (id text, category text, passed int, refused int)")
db.executemany("insert into results values (?, ?, ?, ?)",
               [(r["id"], r["category"], r["passed"], r["refused"]) for r in report["results"]])
for row in db.execute("select category, avg(passed), count(*) from results group by category order by 2"):
    print(row)
```

## 5. Automation: same pipelines, new kinds of checks

You already know how to put tests in CI and block a merge on failure. In AI projects you add **evaluation runs** to the same pipeline and gate on **metrics with thresholds** instead of (or as well as) individual assertions. The workflow in this repo has three jobs: traditional tests, AI evals with quality gates, and a Promptfoo suite.

Two automation habits matter more than before:

- **Control non-determinism.** Use temperature 0 for evals, fix random seeds, pin model versions, and, for CI, use a deterministic fake model so tests are repeatable and free. This repo's `FakeLLM` exists for that reason.
- **Test your gates.** A gate that always passes is worse than no gate. The CI workflow runs the eval suite against a deliberately hallucinating model and fails the build if the gate *does not* catch it.

Flaky-test experience transfers directly: an eval that passes 9 times out of 10 against a real model is a flaky test. Measure the pass rate over several runs before you set a threshold.

## 6. Risk assessment becomes AI risk analysis

Risk-based testing is the skill that most separates a senior AI quality engineer from someone who just runs tools. For every AI feature ask:

| Question | Example for a help assistant |
|---|---|
| What is the worst plausible output? | Tells a user that refunds last 365 days, or to email their password |
| Who is harmed, and how badly? | Customer loses money; support gets angry tickets; legal exposure |
| How likely is it? | Depends on retrieval quality and whether untrusted content is indexed |
| How would we detect it? | Forbidden-content checks, groundedness evals, production trace review |
| What limits the damage? | Refuse when unsure, cite sources, never let docs carry instructions |

Rank risks by harm × likelihood and spend your eval budget on the top of the list. In this repo that is why prompt injection resistance has a gate of 100% while consistency has a lower gate.

## What is genuinely new

Be honest with yourself about the gaps you need to fill. These are covered in the next articles:

1. **Python** fluency, because most AI tooling is Python-first (article 02).
2. **How models and RAG systems work** well enough to predict where they break (article 03).
3. **Statistical evaluation**: metrics, datasets, thresholds, and validating the evaluator itself (article 04).
4. **A small, focused tool set** (article 05).

## Try it

1. Run the app (`uvicorn app.main:app`) and spend 20 minutes on one charter from section 2.
2. Add one new row to `evals/datasets/golden_qa.jsonl` for the most interesting thing you found.
3. Run `python -m evals.run_evals` and see where your case lands in the report.

---
Next: [02. Python Essentials for QA](02-python-essentials-for-qa.md)
