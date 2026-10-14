"""Regression tests for artifact invariants, not factuality of real CVs."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from xml.sax.saxutils import escape
from zipfile import ZipFile

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/evaluate_cv.py'
SPEC = importlib.util.spec_from_file_location('evaluate_cv', SCRIPT)
CV = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CV)


class CvEvalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.md = self.root / 'cv.md'
        self.docx = self.root / 'cv.docx'
        self.template = self.root / 'template.docx'
        self.source = self.root / 'master.md'
        self.jd = self.root / 'jd.md'
        self.review = self.root / 'review.json'
        self.config = self.root / 'config.json'
        self.md.write_text('# Alex | Trainer\n\n- Trained 36 colleagues.\n\n[Portfolio](https://example.com/)\n')
        self.source.write_text('Confirmed: Alex trained 36 colleagues.\n')
        self.jd.write_text('Trainer: deliver practical workshops.\n')
        self.make_docx(self.template)
        self.make_docx(self.docx)
        self.settings = {
            'schema_version': 1, 'markdown': 'cv.md', 'docx': 'cv.docx', 'jd': 'jd.md',
            'evidence_sources': ['master.md'], 'template': 'template.docx',
            'preserve_geometry': True, 'preserve_source_links': True,
            'preserve_package_parts': ['word/styles.xml'], 'review': 'review.json',
            'protected_files': [{'path': 'master.md', 'sha256': CV.digest(self.source)},
                                {'path': 'template.docx', 'sha256': CV.digest(self.template)}],
        }
        self.write_config()
        self.write_review()

    def make_docx(self, path, count=36, url='https://example.com/', width='12240',
                  style=b'<styles/>', tracked=False, tail='', broken=False, explicit_defaults=False):
        body = [f'<w:p><w:r><w:t>Alex | Trainer</w:t></w:r></w:p>',
                f'<w:p><w:r><w:t>Trained {count} colleagues.{escape(tail)}</w:t></w:r></w:p>',
                '<w:p><w:hyperlink r:id="rId1"><w:r><w:t>Portfolio</w:t></w:r></w:hyperlink></w:p>']
        if tracked:
            body.append('<w:ins><w:p><w:r><w:t>Draft revision</w:t></w:r></w:p></w:ins>')
        xml = (f'<w:document xmlns:w="{CV.W}" xmlns:r="{CV.R}"><w:body>' + ''.join(body) +
               f'<w:sectPr><w:pgSz w:w="{width}" w:h="15840"/><w:pgMar w:left="1008"/>' +
               '</w:sectPr></w:body></w:document>')
        if explicit_defaults:
            xml = xml.replace('w:h="15840"', 'w:h="15840" w:orient="portrait"')
            xml = xml.replace('w:left="1008"', 'w:left="1008" w:gutter="0"')
            xml = xml.replace('</w:sectPr>', '<w:cols w:space="720"/></w:sectPr>')
        rel = '' if broken else (f'<Relationship Id="rId1" Type="{CV.R}/hyperlink" '
                                 f'Target="{escape(url)}" TargetMode="External"/>')
        relations = f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rel}</Relationships>'
        with ZipFile(path, 'w') as package:
            package.writestr('word/document.xml', xml)
            package.writestr('word/_rels/document.xml.rels', relations)
            package.writestr('word/styles.xml', style)

    def write_config(self):
        self.config.write_text(json.dumps(self.settings))

    def write_review(self, fail=None):
        record = {
            'reviewer': 'synthetic fixture, not a real CV review', 'reviewed_at': '2026-10-07',
            'bindings': [{'path': p.name, 'sha256': CV.digest(p)}
                         for p in [self.md, self.docx, self.jd, self.source]],
            'dimensions': [{'id': identifier, 'status': 'fail' if identifier == fail else 'pass',
                            'evidence': ['Synthetic test judgement.'], 'next_action': ''}
                           for identifier in CV.DIMENSIONS],
        }
        self.review.write_text(json.dumps(record))

    def result(self):
        return CV.evaluate(self.config)

    def check_status(self, report, identifier):
        return next(c['status'] for c in report['automatic_checks'] if c['id'] == identifier)

    def test_valid_artifact_with_current_review(self):
        self.assertEqual(self.result()['decision'], 'eligible_for_final_review')

    def test_changed_number_detected_even_with_fresh_review(self):
        self.make_docx(self.docx, count=63)
        self.write_review()
        result = self.result()
        self.assertEqual(self.check_status(result, 'markdown_docx_parity'), 'fail')
        self.assertEqual(result['decision'], 'blocked')

    def test_em_dash_in_docx_detected(self):
        self.make_docx(self.docx, tail='\u2014extra')
        self.assertEqual(self.check_status(self.result(), 'no_em_dash'), 'fail')

    def test_placeholder_detected(self):
        self.md.write_text(self.md.read_text() + '\n[TODO: confirm start date]\n')
        self.assertEqual(self.check_status(self.result(), 'no_placeholders'), 'fail')

    def test_changed_link_target_detected(self):
        self.make_docx(self.docx, url='https://wrong.example/')
        result = self.result()
        self.assertEqual(self.check_status(result, 'hyperlink_parity'), 'fail')
        self.assertEqual(self.check_status(result, 'source_hyperlinks'), 'fail')

    def test_broken_link_relationship_detected(self):
        self.make_docx(self.docx, broken=True)
        self.assertEqual(self.check_status(self.result(), 'hyperlink_parity'), 'fail')

    def test_protected_source_mutation_detected(self):
        self.source.write_text('Changed source')
        self.assertEqual(self.check_status(self.result(), 'protected_source_1'), 'fail')

    def test_stale_review_invalidates_semantic_passes(self):
        self.md.write_text(self.md.read_text() + '\n')
        result = self.result()
        self.assertEqual(self.check_status(result, 'review_freshness'), 'fail')
        self.assertTrue(all(c['status'] == 'unverified' for c in result['semantic_review']))

    def test_changed_jd_invalidates_review(self):
        self.jd.write_text('Different role and requirements')
        self.assertEqual(self.check_status(self.result(), 'review_freshness'), 'fail')

    def test_missing_review_is_not_a_pass(self):
        self.settings.pop('review')
        self.write_config()
        self.assertEqual(self.result()['decision'], 'needs_review')

    def test_geometry_change_detected(self):
        self.make_docx(self.docx, width='11906')
        self.assertEqual(self.check_status(self.result(), 'template_geometry'), 'fail')

    def test_equivalent_word_geometry_defaults_are_not_defects(self):
        self.make_docx(self.docx, explicit_defaults=True)
        self.write_review()
        self.assertEqual(self.check_status(self.result(), 'template_geometry'), 'pass')

    def test_package_diagnostics_do_not_claim_visual_failure(self):
        self.settings.pop('preserve_package_parts')
        self.settings['inspect_package_parts'] = ['word/styles.xml']
        self.write_config()
        self.make_docx(self.docx, style=b'<styles>different</styles>')
        self.write_review()
        result = self.result()
        check = next(c for c in result['automatic_checks'] if c['id'] == 'inspect_package_part_1')
        self.assertEqual(check['status'], 'unverified')
        self.assertFalse(check['gate'])
        self.assertEqual(result['decision'], 'eligible_for_final_review')

    def test_style_part_change_detected(self):
        self.make_docx(self.docx, style=b'<styles>different</styles>')
        self.assertEqual(self.check_status(self.result(), 'preserve_package_part_1'), 'fail')

    def test_tracked_changes_detected(self):
        self.make_docx(self.docx, tracked=True)
        self.assertEqual(self.check_status(self.result(), 'no_tracked_changes'), 'fail')

    def test_known_history_conflict_blocks_release(self):
        self.write_review(fail='career_history')
        self.assertEqual(self.result()['decision'], 'blocked')

    def test_partial_jd_fit_does_not_fabricate_a_hard_requirement(self):
        record = json.loads(self.review.read_text())
        next(d for d in record['dimensions'] if d['id'] == 'jd_alignment')['status'] = 'partial'
        self.review.write_text(json.dumps(record))
        self.assertEqual(self.result()['decision'], 'eligible_for_final_review')

    def test_invalid_semantic_status_rejected(self):
        record = json.loads(self.review.read_text())
        record['dimensions'][0]['status'] = 'looks good'
        self.review.write_text(json.dumps(record))
        with self.assertRaises(CV.ConfigError):
            self.result()

    def test_unsupported_markdown_not_silently_passed(self):
        self.md.write_text('| Column |\n| --- |\n| Value |\n')
        self.write_review()
        self.assertEqual(self.check_status(self.result(), 'markdown_docx_parity'), 'unverified')

    def test_evaluator_preserves_all_inputs(self):
        before = {p: CV.digest(p) for p in self.root.iterdir() if p.is_file()}
        self.result()
        self.assertEqual(before, {p: CV.digest(p) for p in before})

    def test_cli_refuses_output_overwriting_input(self):
        before = CV.digest(self.md)
        completed = subprocess.run([sys.executable, str(SCRIPT), '--config', str(self.config),
                                    '--output', str(self.md)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(CV.digest(self.md), before)


if __name__ == '__main__':
    unittest.main()
