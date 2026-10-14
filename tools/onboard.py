#!/usr/bin/env python3
"""Local, non-overwriting onboarding. No network or AI requests."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('name', 'target', 'language', 'location', 'constraints', 'style')
DEFAULTS = {'language': 'ru', 'location': '', 'constraints': '',
            'style': 'Кратко и конкретно. Только подтверждённые факты.'}
PROMPTS = {'name': 'Как к вам обращаться', 'target': 'Желаемые роли и уровень',
           'language': 'Язык общения и материалов', 'location': 'Локация и формат работы (необязательно)',
           'constraints': 'Важные ограничения (необязательно)', 'style': 'Предпочтения по стилю'}


def validate_answers(value):
    if not isinstance(value, dict) or set(value) - set(FIELDS):
        raise ValueError('Анкета должна содержать только поля из templates/answers.example.json.')
    result = {**DEFAULTS, **value}
    for key in FIELDS:
        item = result.get(key, '')
        if not isinstance(item, str) or len(item) > 3000 or any(c in item for c in ('\x00', '\r', '\n')):
            raise ValueError(f'Поле {key}: ожидается одна строка длиной до 3000 символов.')
        result[key] = item.strip()
    if not result['name'] or not result['target'] or not result['language']:
        raise ValueError('Заполните name, target и language. Пустое имя или цель не заменяются примером.')
    return result


def initialize(root, answers, cv=None):
    root = Path(root).resolve()
    answers = validate_answers(answers)
    templates = root / 'templates'
    if not (root / 'AGENTS.md').is_file() or not templates.is_dir():
        raise ValueError('Запускайте онбординг из распакованного проекта.')
    files = {}
    for name in ('voice', 'master_cv', 'achievements', 'pipeline', 'lessons'):
        target = {'voice': 'voice.md', 'master_cv': 'inputs/master_cv.md',
                  'achievements': 'inputs/achievements.md', 'pipeline': 'memory/pipeline.md',
                  'lessons': 'memory/lessons.md'}[name]
        files[target] = (templates / (name + '.md')).read_bytes()
    source_name = None
    if cv:
        cv = Path(cv)
        if cv.suffix.lower() not in ('.md', '.txt') or not cv.is_file():
            raise ValueError('Для CLI нужен существующий текстовый .md или .txt. PDF/DOCX импортируйте через агента.')
        if cv.stat().st_size > 1000000:
            raise ValueError('Текстовое CV должно быть не больше 1 МБ.')
        data = cv.read_bytes()
        content = data.decode('utf-8-sig')
        if '\x00' in content or len(content.strip()) < 30:
            raise ValueError('CV пустое, слишком короткое или не является текстовым документом.')
        source_name = 'inputs/originals/imported_cv' + cv.suffix.lower()
        files[source_name] = data
        files['inputs/master_cv.md'] = content.encode('utf-8')
    files['about.md'] = ('# Candidate profile\n\nUser-provided setup answers, not verified career evidence.\n\n'
                         + '```json\n' + json.dumps(answers, ensure_ascii=False, indent=2) + '\n```\n').encode('utf-8')
    files['applications/index.json'] = b'{"applications": []}\n'
    profile = {'schema_version': 1, 'answers': answers,
               'source_cv': source_name, 'source_cv_review': 'unverified' if cv else 'not_supplied'}
    files['config/profile.json'] = (json.dumps(profile, ensure_ascii=False, indent=2) + '\n').encode('utf-8')

    # Refuse any existing managed file or symlink before writing the first byte.
    for name in files:
        path = root / name
        if path.exists() or path.is_symlink():
            raise FileExistsError(f'Уже существует {name}. Ничего не перезаписано; продолжите настройку с агентом.')
        for parent in path.parents:
            if parent == root:
                break
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                raise ValueError(f'Недопустимый родительский путь для {name}.')
    lock = root / '.onboarding.lock'
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    created = []
    try:
        for name, data in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            created.append(path)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
    except BaseException:
        for path in reversed(created):
            path.unlink()
        raise
    finally:
        lock.unlink()
    return list(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--answers', type=Path, help='Private JSON questionnaire; keep it under config/')
    parser.add_argument('--cv', type=Path, help='UTF-8 source CV (.md or .txt); the original is unchanged')
    args = parser.parse_args()
    try:
        if args.answers:
            if args.answers.stat().st_size > 64000:
                raise ValueError('Файл анкеты слишком большой.')
            answers = json.loads(args.answers.read_text(encoding='utf-8'))
        else:
            print('Настройка отдельного карьерного проекта. Данные сохраняются только локально.')
            answers = {}
            for field in FIELDS:
                default = DEFAULTS.get(field, '')
                answer = input(PROMPTS[field] + (f' [{default}]' if default else '') + ': ').strip()
                answers[field] = answer or default
            answers = validate_answers(answers)
            if input('Создать личные файлы с этими ответами? [да/нет]: ').strip().lower() not in ('да', 'yes', 'y'):
                print('Файлы не созданы.')
                return 0
        paths = initialize(ROOT, answers, args.cv)
        print(f'Создано личных файлов: {len(paths)}. Они исключены из обычных Git-коммитов.')
        print('Далее: python3 tools/doctor.py --workspace')
        print('Проверьте исходное CV с агентом. Импорт не означает проверку карьерных фактов.')
        return 0
    except (OSError, ValueError, UnicodeError) as error:
        print(f'Ошибка: {error}', file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print('\nАнкета отменена.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
