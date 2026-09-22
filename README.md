# Marketplace AML Triage Engine

**Cutting alert review cost with Jev and agentic AI, without losing detection.**

An end to end anti money laundering transaction monitoring system for a synthetic peer to peer resale marketplace. Rules and machine learning create alerts, Jev makes fast and cheap typed decisions, and an LLM investigator agent handles only the cases that need deep reasoning and a draft SAR narrative for human review.

> All data in this project is synthetic. No real people, accounts, companies or transactions are used.

---

## The problem

Transaction monitoring systems are tuned to be sensitive, so most alerts turn out to be normal activity. Every alert still needs a documented decision, and investigations take time. Running a full LLM on every alert and every investigation step is slow and expensive.

## The approach

| Layer | Role | Real world equivalent |
|---|---|---|
| Detection | SQL rules and a LightGBM risk model create alerts | Monitoring system |
| Triage | Jev returns a disposition, typology and confidence for each alert | L1 analyst |
| Investigation | LangGraph agent calls tools, reasons through the case and drafts a SAR | L2 investigator |
| Human review | A person approves or rejects every SAR draft | Compliance officer |

Jev is also used **inside** the agent for small decisions like which tool to call next or whether a linked account is relevant, so the LLM only spends tokens on reasoning and writing.

## What gets measured

1. Rules only vs rules plus ML vs the full system
2. Agent with the LLM making every decision vs agent with Jev handling small decisions
3. For each: tokens, cost, runtime, recall on planted laundering cases, precision and false negatives

## Synthetic typologies

Collusive buy and sell loops, overpriced listings used for trade based laundering, structured payouts under thresholds, dormant account reactivation, and mule seller networks sharing devices. Realistic noise is built in on purpose, including legit look alikes that trigger false positives and careful launderers that slip through. 

## Repo structure

```
data/          synthetic data generator and typology docs
detection/     SQL rules and LightGBM model
triage/        Jev typed questions and confidence routing
agent/         investigator agent and its tools
evaluation/    benchmarks and comparisons
dashboard/     Streamlit app
cache/         saved API responses so reruns cost nothing
docs/          architecture and results write up
notebooks/     exploration and charts
tests/         basic checks for each layer
```

## Compliance controls

- Audit log for every automated decision: input, question, answer, confidence, timestamp, model version
- Every Jev question includes an "other or unclear" option so uncertain cases escalate instead of getting forced into a wrong label
- QC sampling: a share of auto closed alerts is re reviewed
- Human in the loop: the agent drafts SARs, a person approves them
- Input sanitization against prompt injection in seller written listing text

## Quick start

```bash
git clone https://github.com/inara13/marketplace-aml-triage-engine.git
cd marketplace-aml-triage-engine
pip install -r requirements.txt
cp .env.example .env        # add your API keys
```

Run steps for each layer will be added as they are built.

## Results

*Coming soon.*

## Status

- [ ] Synthetic marketplace data
- [ ] Detection layer
- [ ] Jev triage layer
- [ ] Investigator agent
- [ ] Benchmark
- [ ] Dashboard
- [ ] Write up

## Author

Inara Dosani, Data Scientist

## License

MIT
