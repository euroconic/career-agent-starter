import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tools/workspace'))
from onboard import initialize
from export_template import export_template
from template_files import template_files
from pipeline_check import parse_records


class StarterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'client'
        self.root.mkdir()
        for name, data in template_files(ROOT):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        self.answers = {'name': 'Synthetic ' + uuid.uuid4().hex, 'target': 'Technical Writer', 'language': 'en'}

    def test_onboarding_uses_answers_and_starts_empty(self):
        initialize(self.root, self.answers)
        profile = json.loads((self.root / 'config/profile.json').read_text())
        self.assertEqual(profile['answers']['target'], 'Technical Writer')
        self.assertEqual(profile['source_cv_review'], 'not_supplied')
        self.assertEqual(json.loads((self.root / 'applications/index.json').read_text()), {'applications': []})
        records, errors = parse_records((self.root / 'memory/pipeline.md').read_text())
        self.assertEqual((records, errors), ([], []))

    def test_import_preserves_original_and_does_not_claim_verification(self):
        source = self.base / 'source.txt'
        original = 'Synthetic candidate. Worked on documented technical writing projects.\n'
        source.write_text(original)
        initialize(self.root, self.answers, source)
        self.assertEqual(source.read_text(), original)
        self.assertEqual((self.root / 'inputs/originals/imported_cv.txt').read_text(), original)
        self.assertEqual((self.root / 'inputs/master_cv.md').read_text(), original)
        self.assertEqual(json.loads((self.root / 'config/profile.json').read_text())['source_cv_review'], 'unverified')

    def test_repeat_onboarding_does_not_overwrite(self):
        initialize(self.root, self.answers)
        before = (self.root / 'about.md').read_bytes()
        with self.assertRaises(FileExistsError):
            initialize(self.root, {**self.answers, 'name': 'Another candidate'})
        self.assertEqual((self.root / 'about.md').read_bytes(), before)

    def test_existing_baseline_causes_no_partial_profile_write(self):
        (self.root / 'inputs').mkdir()
        baseline = self.root / 'inputs/master_cv.md'
        baseline.write_text('Existing source')
        with self.assertRaises(FileExistsError):
            initialize(self.root, self.answers)
        self.assertFalse((self.root / 'about.md').exists())
        self.assertEqual(baseline.read_text(), 'Existing source')

    def test_symlinked_private_directory_is_rejected(self):
        outside = self.base / 'outside'
        outside.mkdir()
        (self.root / 'inputs').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            initialize(self.root, self.answers)
        self.assertEqual(list(outside.iterdir()), [])

    def test_invalid_answers_do_not_create_personal_files(self):
        for answers in ({'name': '', 'target': 'Writer'}, {'name': 'Test', 'target': 'Writer', 'unknown': 'x'}):
            with self.assertRaises(ValueError):
                initialize(self.root, answers)
        self.assertFalse((self.root / 'about.md').exists())

    def test_export_from_used_workspace_excludes_all_candidate_files_and_git(self):
        initialize(self.root, self.answers)
        (self.root / '.git').mkdir()
        (self.root / '.git/secret-history').write_text(self.answers['name'])
        (self.root / '.env').write_text('TEST_ONLY=value')
        (self.root / 'unlisted-private-note.txt').write_text(self.answers['name'])
        output = self.base / 'clean.zip'
        export_template(self.root, output)
        with ZipFile(output) as archive:
            names = archive.namelist()
            for private in ('about.md', 'voice.md', '.env', '.git/secret-history', 'config/profile.json', 'unlisted-private-note.txt'):
                self.assertNotIn('career-agent-starter/' + private, names)
            for name in names:
                self.assertNotIn(self.answers['name'].encode(), archive.read(name))
            extracted = self.base / 'extracted'
            archive.extractall(extracted)
        other = extracted / 'career-agent-starter'
        initialize(other, {**self.answers, 'name': 'Different synthetic candidate'})
        self.assertNotIn(self.answers['name'], (other / 'about.md').read_text())

    def test_export_does_not_replace_existing_archive(self):
        output = self.base / 'existing.zip'
        output.write_bytes(b'existing')
        with self.assertRaises(FileExistsError):
            export_template(self.root, output)
        self.assertEqual(output.read_bytes(), b'existing')

    def test_manifest_cannot_opt_in_private_paths_or_parent_paths(self):
        manifest = self.root / 'template-manifest.json'
        original = json.loads(manifest.read_text())
        for unsafe in ('about.md', '../outside.md', '.git/config', '/tmp/absolute.md'):
            manifest.write_text(json.dumps({**original, 'files': original['files'] + [unsafe]}))
            with self.assertRaises(ValueError):
                template_files(self.root)

    def test_export_rejects_symlink_and_secret_in_shared_file(self):
        shared = self.root / 'README.md'
        shared.unlink()
        source = self.base / 'private.md'
        source.write_text('Private test note')
        shared.symlink_to(source)
        with self.assertRaises(ValueError):
            template_files(self.root)
        shared.unlink()
        shared.write_text('sk-' + 'x' * 30)
        with self.assertRaises(ValueError):
            template_files(self.root)

    @unittest.skipUnless(shutil.which('git'), 'Git not available')
    def test_git_add_does_not_stage_onboarded_personal_data(self):
        initialize(self.root, self.answers)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), 'add', '.'], check=True)
        tracked = subprocess.check_output(['git', '-C', str(self.root), 'ls-files', '-z']).decode().split('\0')
        allowed = {name for name, _ in template_files(self.root)}
        self.assertTrue(set(filter(None, tracked)) <= allowed)
        self.assertNotIn('about.md', tracked)

    def test_malformed_pipeline_does_not_pass_as_empty(self):
        _, errors = parse_records('# Application pipeline\n\n## Active\n### broken entry\n## Closed\n')
        self.assertTrue(errors)

    def test_onboarding_and_doctor_cli(self):
        answers = self.base / 'answers.json'
        answers.write_text(json.dumps(self.answers))
        subprocess.run([sys.executable, str(self.root / 'tools/onboard.py'), '--answers', str(answers)], check=True, capture_output=True)
        result = subprocess.run([sys.executable, str(self.root / 'tools/doctor.py'), '--workspace'], check=True, capture_output=True, text=True)
        self.assertIn('Workspace structure valid', result.stdout)
        self.assertNotIn(self.answers['name'], result.stdout)


if __name__ == '__main__':
    unittest.main()
