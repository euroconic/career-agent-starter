"""Explicit export allowlist. Never discover candidate files recursively."""
from pathlib import Path, PurePosixPath
import json
import re

ROOT_FILES = {'README.md', 'AGENTS.md', 'CLAUDE.md', 'ONBOARDING.md', '.gitignore', 'template-manifest.json'}
ROOT_DIRS = {'.context', 'skills', 'tools', 'tests', 'templates'}
SAFE_EMAIL = re.compile(r'^[^@]+@(?:[a-z0-9-]+\.)*(?:example\.(?:com|org|net|invalid|test)|example|test|invalid)$', re.I)


def template_files(root):
    root = Path(root).resolve()
    manifest = root / 'template-manifest.json'
    if manifest.is_symlink():
        raise ValueError('Manifest must not be a symlink')
    value = json.loads(manifest.read_text(encoding='utf-8'))
    names = value.get('files', [])
    if value.get('schema_version') != 1 or not names or len(names) != len(set(names)):
        raise ValueError('Invalid template manifest')
    result = []
    for name in names:
        if not isinstance(name, str) or '\\' in name:
            raise ValueError('Manifest paths must be relative POSIX strings')
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or str(relative) != name:
            raise ValueError('Unsafe manifest path')
        if not (name in ROOT_FILES or relative.parts[0] in ROOT_DIRS or name.startswith('.claude/commands/')):
            raise ValueError(f'Not a reusable template path: {name}')
        if any(part in ('.git', '__pycache__', 'node_modules', '.venv') for part in relative.parts):
            raise ValueError(f'Runtime file in manifest: {name}')
        path = root / name
        for part in (path, *path.parents):
            if part == root:
                break
            if part.is_symlink():
                raise ValueError(f'Symlink in template path: {name}')
        if not path.is_file():
            raise ValueError(f'Missing template file: {name}')
        data = path.read_bytes()
        text = data.decode('utf-8')
        if '\x00' in text:
            raise ValueError(f'Binary data in template: {name}')
        # Findings identify the file, never echo potentially secret content.
        secrets = [r'sk-[A-Za-z0-9_-]{20,}', r'gh[pousr]_[A-Za-z0-9]{20,}',
                   r'-----BEGIN [A-Z ]*PRIVATE KEY-----', r'(?:/Users/|/home/)[A-Za-z0-9_.-]+/']
        if any(re.search(pattern, text) for pattern in secrets):
            raise ValueError(f'Possible secret or personal machine path in {name}')
        emails = re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', text)
        if any(not SAFE_EMAIL.fullmatch(email) for email in emails):
            raise ValueError(f'Non-example email in {name}')
        result.append((name, data))
    if set(ROOT_FILES) - set(names):
        raise ValueError('Missing required root files in manifest')
    return result
