# Workspace checks

pipeline_check.py validates the declared tracker structure and optionally the existence of event sources. It does not verify whether an event happened. Run it from the candidate workspace root, passing the tracker path if needed.

safe_output.publish_bytes(destination, payload, validator=callable, expected_sha256=old_hash) validates a same-directory temporary file before atomic replacement. For a new destination use must_be_absent=True instead. Validators raise on failure. The destination directory must exist. It detects changes during validation, but cannot guarantee compare-and-swap against non-cooperating external editors; use one coordinator per candidate workflow.

Tests use isolated temporary directories and synthetic candidate facts. They do not submit applications or touch live documents.

Symbolic-link destinations are rejected, including dangling links, so publishing cannot silently replace an alias instead of updating its source.

pipeline_event.apply_event(text, proposal, workspace_root) returns an updated tracker without writing. A proposal needs event_id, application_id, event_date, description, source, expected_stage, stage, next, owner and due. Replaying identical IDs is a no-op; changed payloads, missing local sources, stale stages and implicit reopening are rejected. Publish the returned bytes with the original tracker hash. These checks do not replace source review or user authority.
