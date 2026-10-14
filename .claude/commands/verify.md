# /verify

Load `skills/verify/SKILL.md` and audit the named output against its original inputs. `$ARGUMENTS` may identify an artifact, source files, and whether to apply corrections. Use the supplied files and matching workspace context; do not assume an existing report is its own evidence.

Return source-located findings and unresolved checks. Keep specialists read-only. Apply corrections only when the request or an ongoing authorized write task includes that update; the coordinator is the sole writer.
