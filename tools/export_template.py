#!/usr/bin/env python3
"""Export only reviewed reusable template paths, excluding candidate data and Git metadata."""
import argparse
from pathlib import Path
import sys
from zipfile import ZipFile, ZIP_DEFLATED

from template_files import template_files

ROOT = Path(__file__).resolve().parents[1]


def export_template(root, output):
    files = template_files(root)
    output = Path(output)
    if output.is_symlink() or output.exists():
        raise FileExistsError('Archive already exists; choose a new output filename')
    # Exclusive creation avoids silently replacing an existing handoff.
    with output.open('xb') as stream:
        try:
            with ZipFile(stream, 'w', ZIP_DEFLATED) as archive:
                for name, data in files:
                    archive.writestr('career-agent-starter/' + name, data)
        except BaseException:
            output.unlink()
            raise
    return len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        count = export_template(ROOT, args.output)
        print(f'Exported {count} allowlisted files to {args.output}. Candidate data and .git excluded.')
        return 0
    except (OSError, ValueError) as error:
        print(f'Export refused: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
