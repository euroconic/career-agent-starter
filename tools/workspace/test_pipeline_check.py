import unittest
from pathlib import Path

from pipeline_check import VALID_STAGES, check_event_sources, parse_records


def record(app_id="example_app", stage="Prepared", area="Active", extra=""):
    return f'''## {area}\n\n### {app_id} | Example - Role\n- Application ID: {app_id}\n- Stage: {stage}\n- Last event: Unknown (not evidenced)\n- Event source: `archive/source.md`\n- Next: Review the application\n- Owner: Candidate\n- Due: Unassigned\n{extra}'''


class PipelineCheckTests(unittest.TestCase):
    def test_all_supported_stages_are_accepted(self):
        for index, stage in enumerate(sorted(VALID_STAGES)):
            with self.subTest(stage=stage):
                text = record(f"app_{index}", stage, "Closed" if stage == "Closed" else "Active")
                _, errors = parse_records(text)
                self.assertEqual(errors, [])

    def test_duplicate_ids_are_rejected(self):
        text = record() + "\n" + record()
        _, errors = parse_records(text)
        self.assertTrue(any("duplicate Application ID" in error for error in errors))

    def test_duplicate_current_field_is_rejected(self):
        _, errors = parse_records(record(extra="- Next: Conflicting duplicate\n"))
        self.assertTrue(any("expected one Next field, found 2" in error for error in errors))

    def test_closed_stage_cannot_be_active(self):
        _, errors = parse_records(record(stage="Closed"))
        self.assertTrue(any("closed application appears under Active" in error for error in errors))

    def test_missing_required_fields_are_rejected(self):
        text = record().replace("- Owner: Candidate\n", "")
        _, errors = parse_records(text)
        self.assertTrue(any("expected one Owner field, found 0" in error for error in errors))

    def test_event_source_check_is_narrow_and_explicit(self):
        records, errors = parse_records(record())
        self.assertEqual(errors, [])
        self.assertEqual(check_event_sources(records, Path("/workspace")), [
            "example_app: Event source file does not exist: archive/source.md"
        ])

    def test_stage_values_are_exact(self):
        _, errors = parse_records(record(stage="Ghosted"))
        self.assertTrue(any("invalid stage 'Ghosted'" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
