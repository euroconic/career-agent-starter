# Career Agent Starter

Read `AGENTS.md` and `.context/rules.md`. Start with `ONBOARDING.md` when the candidate profile is absent. Never use a profile from outside the selected workspace.

Candidate evidence belongs in `about.md`, `inputs/` and the matching application context. Writing preferences belong in `voice.md`. No default career level, geography, salary, language fluency or ownership is assumed. Never use em dash punctuation.

## Skill registry

| Skill | Route |
|---|---|
| `skills/job-vacancy-analysis/SKILL.md` | Read-only vacancy fit and gaps |
| `skills/job-application-cv/SKILL.md` | Requested application materials and CV updates |
| `skills/ats-cv-fit-review/SKILL.md` | Existing CV comparison and parsing risks |
| `skills/interview-transcript-analysis/SKILL.md` | Focused interview review |
| `skills/interview-deep-analysis/SKILL.md` | Question-by-question interview review |
| `skills/verify/SKILL.md` | Audit an existing artifact against sources |

Load only the skill relevant to the request. If tools or a required format are unavailable, state the limitation and deliver the supported portion without pretending a check ran.

## Command adapters

`/onboard`, `/gap-analysis`, `/prepare-cv`, `/interview-analysis`, `/interview-deep-analysis`, `/verify`, `/morning-dump`.

These are local text adapters in `.claude/commands/`. Other agents can read the corresponding skill by path. No global plugin installation is assumed.

## Source hierarchy

Current explicit user corrections take precedence over older drafts. `inputs/master_cv.md` is the protected baseline, `inputs/achievements.md` records evidence and caveats, `memory/pipeline.md` tracks actual application stages, and `memory/lessons.md` contains lessons saved at the user's request. Generated summaries are not independent evidence.

Follow `.context/workflows.md` for preparation and tracking. A prepared document does not mean an application was sent. Before marking a Word export verified, inspect every rendered final page and perform the source-based review described in the CV skill.
