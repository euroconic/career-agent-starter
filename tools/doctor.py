#!/usr/bin/env python3
"""Check template integrity or the current candidate workspace without printing private content."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from template_files import template_files
from onboard import validate_answers

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--template', action='store_true')
    group.add_argument('--workspace', action='store_true')
    args = parser.parse_args()
    try:
        if args.template:
            files = template_files(ROOT)
            if (ROOT / '.git').exists():
                tracked = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-z']).decode().split('\0')
                extras = set(filter(None, tracked)) - {name for name, _ in files}
                if extras:
                    raise ValueError('Git tracks files outside the export manifest; inspect git ls-files before sharing.')
            print(f'Template structure valid: {len(files)} allowlisted text files. No known secret patterns found.')
            print('This is a bounded check, not proof that every statement is free of personal information.')
        else:
            required = ['about.md', 'voice.md', 'config/profile.json', 'inputs/master_cv.md',
                        'inputs/achievements.md', 'memory/pipeline.md', 'memory/lessons.md', 'applications/index.json']
            missing = [name for name in required if not (ROOT / name).is_file()]
            if missing:
                raise ValueError('Onboarding incomplete; missing: ' + ', '.join(missing))
            profile = json.loads((ROOT / 'config/profile.json').read_text(encoding='utf-8'))
            validate_answers(profile['answers'])
            sys.path.insert(0, str(ROOT / 'tools/workspace'))
            from pipeline_check import parse_records, check_event_sources
            records, errors = parse_records((ROOT / 'memory/pipeline.md').read_text(encoding='utf-8'))
            errors += check_event_sources(records, ROOT)
            if errors:
                raise ValueError('Invalid pipeline: ' + '; '.join(errors))
            print('Workspace structure valid. Personal values were not printed.')
            if profile.get('source_cv_review') != 'confirmed':
                print('Next: supply or review source CV with the agent. Career facts remain unverified.')
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f'Check failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
