# Career workflows

## Review a vacancy

Use the current user's source CV, confirmed evidence and chosen role. Read `skills/job-vacancy-analysis/SKILL.md`. Return source-linked fit, gaps and a next step. Keep files unchanged unless saving is requested.

## Prepare an application

Resolve or create one application ID in `applications/index.json`. Save the supplied JD and provenance, relevant confirmations, requested analysis and CV draft in its folder. Do not copy unrelated application history. Follow the CV skill for factual and artifact review. Record Evaluating or Prepared according to what happened, never Applied because a CV was created.

## Update a pipeline

Only reflect user-supplied or observed events. Use `templates/application-record.md` for a first record. Valid stages: Evaluating, Prepared, Applied, Screening, Interview Loop, Final-Offer, Negotiation, Closed, Superseded. Keep Closed records under `## Closed`; other current records under `## Active`.

Record the source file in backticks, actual event date if known, next action, owner and due date. Use Unknown or Unassigned for missing values. `tools/workspace/pipeline_event.py` can validate and apply a structured event to an existing record without writing. The coordinator saves the result; run `python3 tools/workspace/pipeline_check.py --check-files` afterward. An empty new tracker is valid.

## Interview review

Use the focused skill for ordinary feedback and the deep skill for an explicitly requested question-level debrief. Read the original transcript, preserving speaker uncertainty and exact quotations. Save lessons or change pipeline only within an authorized update.

## Output verification

Separate evidence review from formatting and visual inspection. Use `skills/verify/SKILL.md` for a requested source audit. For Word exports, use the CV skill's artifact procedure and available document tooling. Missing tools or unperformed reviews remain unverified. Do not silently overwrite user-edited files.
