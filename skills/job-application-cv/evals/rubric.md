# Artifact verification

Run from the current candidate workspace:

```sh
python3 skills/job-application-cv/scripts/evaluate_cv.py --config applications/example__role/evals/config.json
```

`example__role` is a placeholder for the selected application, not an existing candidate. Create a config for actual artifacts. Config paths are relative to the config file. The evaluator is read-only and uses only Python's standard library.

The config requires `schema_version: 1` and declares `markdown`, `docx`, `jd`, `evidence_sources`, `protected_files` (path and original sha256), and optionally `template` and `review`. Read `scripts/evaluate_cv.py` for supported template checks and exact input validation. An evidence review binds source and output paths with their SHA-256 hashes and records `reviewer`, `reviewed_at` and `dimensions`.

Dimensions: factual_support, metric_attribution, career_history, jd_alignment, audience_and_adoption, voice_and_clarity, scope_and_authority, visual_layout. Each entry has `id`, `status` (pass, partial, fail, unverified), nonempty `evidence` and `next_action`. Bindings are relative to the review file and cover all declared source and output files. The evaluator imports these judgments; it cannot establish their truth.

Missing review remains unverified. Changes to bound files invalidate review. Mechanical tests cover text parity, placeholders, links, source protection, tracked changes and configured template constraints. Source-grounded judgment and visual inspection are separate requirements.

Exit codes: 0 means eligible for final review, 1 means failed or incomplete checks, 2 means invalid configuration/input. None authorizes submission or constitutes an ATS score. The test suite uses generated synthetic documents; passing it does not verify a real candidate's CV.
