# CV artifact production

Use the user's selected template as design authority. Record hashes of protected source files before editing. Edit a copy, preserving requested geometry, typography, lists, links and unaffected content. Do not hard-code a personal template, paragraph count or source path into a reusable generator.

Use `cv_draft.md` as canonical tailored wording. Keep generated formats synchronized. If the user edited a DOCX since generation, reconcile it rather than silently replacing it. Formatting-only requests do not authorize wording changes.

Use available document tooling and its instructions. After the final edit, render every page, inspect text wrapping, clipping, page breaks, bullets, dates and headings. Compare extracted document text with Markdown and verify links and changed claims against sources. A character count, XML inspection or number of pages does not prove visual quality.

Run the configured evaluator described in `../evals/rubric.md`. Keep factual and visual review as separate, current, artifact-bound judgments. Never refresh review hashes without rereading changed artifacts and evidence.

Publish verified output under `delivered/<application_id>/` only after the relevant checks pass. The optional `tools/workspace/safe_output.py` helper validates staged bytes before replacing one file and checks its expected prior hash. It is not a multi-file transaction or a lock against non-cooperating editors.

When rendering or another required check is unavailable, keep the artifact labeled as a draft and state the limitation. A verified CV is still not an externally submitted application.
