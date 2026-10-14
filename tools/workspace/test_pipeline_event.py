import tempfile
import unittest
from pathlib import Path
from pipeline_event import apply_event
from pipeline_check import parse_records
from test_pipeline_check import record


class PipelineEventTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'event.md').write_text('User confirmed an interview.')
        self.text = '# Pipeline\n\n' + record()
        self.event = dict(event_id='synthetic-1', application_id='example_app', event_date='2026-10-08',
                          description='Interview confirmed', source='event.md', expected_stage='Prepared',
                          stage='Interview Loop', next='Prepare interview', owner='Candidate', due='Unknown')

    def test_replay_has_no_effect(self):
        result = apply_event(self.text, self.event, self.root)
        self.assertEqual(result, apply_event(result, self.event, self.root))

    def test_eof_without_newline_separates_and_replays_marker(self):
        text = self.text.rstrip('\n')
        result = apply_event(text, self.event, self.root)
        self.assertIn('- Due: Unknown\n- Processed event: synthetic-1 ', result)
        self.assertEqual(result, apply_event(result, self.event, self.root))

    def test_reused_id_with_new_content_rejected(self):
        result = apply_event(self.text, self.event, self.root)
        with self.assertRaisesRegex(ValueError, 'reused'):
            apply_event(result, {**self.event, 'description': 'Different event'}, self.root)

    def test_stale_stage_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Stage changed'):
            apply_event(self.text, {**self.event, 'expected_stage': 'Screening'}, self.root)

    def test_close_moves_record_and_preserves_other_record(self):
        text = self.text + '\n' + record('other_app')
        result = apply_event(text, {**self.event, 'stage': 'Closed'}, self.root)
        records, errors = parse_records(result)
        self.assertEqual(errors, [])
        self.assertEqual({r['heading_id']: r['area'] for r in records}, {'other_app': 'Active', 'example_app': 'Closed'})

    def _text_with_unrelated_sections(self):
        app = record().split('## Active\n\n', 1)[1]
        return ('# Pipeline\n\n'
                '## Workspace Notes\n\nKeep this section byte-for-byte.\n\n'
                '## Active\n\nActive section introduction stays here.\n\n'
                + app + '\n\n'
                '## Closed\n\nClosed section introduction stays here.\n')

    def test_update_preserves_unrelated_sections_and_section_notes(self):
        text = self._text_with_unrelated_sections()
        result = apply_event(text, self.event, self.root)
        for note in (
            '## Workspace Notes\n\nKeep this section byte-for-byte.\n\n',
            '## Active\n\nActive section introduction stays here.\n\n',
            '## Closed\n\nClosed section introduction stays here.\n',
        ):
            self.assertIn(note, result)
        self.assertLess(result.index('## Workspace Notes'), result.index('## Active'))

    def test_closing_preserves_unrelated_sections_and_section_notes(self):
        text = self._text_with_unrelated_sections()
        result = apply_event(text, {**self.event, 'stage': 'Closed'}, self.root)
        for note in (
            '## Workspace Notes\n\nKeep this section byte-for-byte.\n\n',
            '## Active\n\nActive section introduction stays here.\n\n',
            '## Closed\n\nClosed section introduction stays here.\n',
        ):
            self.assertIn(note, result)
        records, errors = parse_records(result)
        self.assertEqual(errors, [])
        self.assertEqual({r['heading_id']: r['area'] for r in records}, {'example_app': 'Closed'})

    def test_missing_source_rejected(self):
        with self.assertRaisesRegex(ValueError, 'source'):
            apply_event(self.text, {**self.event, 'source': 'missing.md'}, self.root)

    def test_embedded_field_injection_rejected(self):
        with self.assertRaisesRegex(ValueError, 'single-line'):
            apply_event(self.text, {**self.event, 'description': 'Hello\n- Stage: Applied'}, self.root)


if __name__ == '__main__':
    unittest.main()
