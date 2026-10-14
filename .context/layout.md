# Workspace layout

Reusable files: `AGENTS.md`, `CLAUDE.md`, `README.md`, `ONBOARDING.md`, `.context/`, `.claude/commands/`, `skills/`, `tools/`, `tests/`, `templates/` and `template-manifest.json`.

Private files created during onboarding:

- `about.md`: identity, chosen target, language and constraints.
- `voice.md`: writing preferences.
- `config/profile.json`: onboarding answers and source-review state.
- `inputs/master_cv.md`: protected source text, or an explicit no-source marker.
- `inputs/originals/`: unmodified source copies.
- `inputs/achievements.md`: evidence, ownership, metrics and open questions.
- `memory/pipeline.md`: current application stages and next actions.
- `memory/lessons.md`: durable lessons saved on request.
- `applications/index.json`: `{ "applications": [] }` initially. Add objects with `id`, `company`, `role`, `folder`; one role per ID.

Private task folders are created only when needed: `applications/<company__role>/`, `vacancies/`, `delivered/`, `content/`, `archive/`. Use lowercase ASCII IDs with underscores. Different roles at the same company need different IDs; distinguish repeated applications when necessary.

Application files: `jd.md`, `application_context.md`, `match_analysis.md`, `cv_draft.md`, `interviews/`, `artifacts/`, `evals/`. Put unverified exports in `artifacts/`. Only verified exports belong in `delivered/<application_id>/`; a filename is not proof of verification.
