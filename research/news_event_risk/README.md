# Verifiable news/event risk policy research

This directory is an isolated research fixture. It does not integrate with
application code, live feeds, strategies, portfolios, orders, brokers, or UI.

Run the complete contract validation and deterministic test suite:

```bash
python3 -m unittest discover -s research/news_event_risk -p 'test_*.py'
```

Regenerate the committed policy, test vectors, traceability report, and gap
report:

```bash
python3 research/news_event_risk/generate_artifacts.py
```

The generator is deterministic and uses only the Python standard library. It
also emits `artifact_manifest.json` with SHA-256 hashes for the policy, schema,
and vectors. Generated artifacts must be reviewed and committed together. The
policy is a research contract, not a live-ready, compliant, or predictive
system.
