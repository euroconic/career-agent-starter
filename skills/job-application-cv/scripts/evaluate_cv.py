#!/usr/bin/env python3
"""Read-only CV artifact checks plus an explicitly supplied evidence review.

Standard library only. Semantic judgements are imported, not auto-generated.
"""

import argparse
import difflib
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS = {'w': W}
DIMENSIONS = {
    'factual_support': True,
    'metric_attribution': True,
    'career_history': True,
    'jd_alignment': False,
    'audience_and_adoption': False,
    'voice_and_clarity': False,
    'scope_and_authority': True,
    'visual_layout': True,
}
STATUSES = {'pass', 'partial', 'fail', 'unverified'}
LINK = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
PLACEHOLDER = re.compile(r'\[(?:TODO|TBD|TBC|INSERT|PLACEHOLDER)\b[^\]]*\]|\{\{[^}]+\}\}', re.I)


class ConfigError(ValueError):
    pass


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def load_json(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ConfigError(f'Expected a JSON object: {path}')
    return value


def normalise(text):
    text = text.replace('\u00a0', ' ').replace('\t', ' ')
    return re.sub(r'\s+', ' ', text.replace('|', ' ')).strip()


def markdown_text(text):
    text = LINK.sub(lambda m: m.group(1), text)
    text = re.sub(r'^\s{0,3}#{1,6}\s+', '', text, flags=re.M)
    text = re.sub(r'^\s*(?:[-*+] |\d+\. )', '', text, flags=re.M)
    return text.replace('**', '')


def xml_text(root):
    return '\n'.join(
        ''.join((node.text or '') if node.tag == f'{{{W}}}t' else ' '
                for node in p.iter() if node.tag in {f'{{{W}}}t', f'{{{W}}}tab', f'{{{W}}}br'})
        for p in root.findall('.//w:p', NS)
    )


def section_geometry(section):
    """Compare effective geometry, including common implicit Word defaults."""
    result = {}
    for name in ['pgSz', 'pgMar']:
        element = section.find('w:' + name, NS)
        result[name] = dict(element.attrib) if element is not None else None
    if result['pgSz'] is not None:
        result['pgSz'].setdefault(f'{{{W}}}orient', 'portrait')
    if result['pgMar'] is not None:
        result['pgMar'].setdefault(f'{{{W}}}gutter', '0')
    columns = section.find('w:cols', NS)
    attrs = {f'{{{W}}}{key}': value for key, value in
             {'num': '1', 'space': '720', 'sep': '0', 'equalWidth': '1'}.items()}
    children = []
    if columns is not None:
        attrs.update(columns.attrib)
        children = [dict(child.attrib) for child in columns]
    # Inter-column spacing has no effect for a single ordinary column.
    if attrs[f'{{{W}}}num'] == '1' and not children:
        attrs.pop(f'{{{W}}}space', None)
    result['cols'] = {'attributes': attrs, 'columns': children}
    return result


def text_differences(markdown, document):
    left, right = markdown.split(), document.split()
    differences = []
    for tag, a, b, c, d in difflib.SequenceMatcher(None, left, right, autojunk=False).get_opcodes():
        if tag != 'equal':
            context = ' '.join(left[max(0, a - 5):a])
            differences.append(f'After "{context}": Markdown="{" ".join(left[a:b])[:180]}"; '
                               f'DOCX="{" ".join(right[c:d])[:180]}"')
    return differences[:12]


def docx_data(path):
    with ZipFile(path) as package:
        root = ET.fromstring(package.read('word/document.xml'))
        relations = ET.fromstring(package.read('word/_rels/document.xml.rels'))
        targets = {r.get('Id'): r.get('Target') for r in relations
                   if r.get('Type') == R + '/hyperlink' and r.get('TargetMode') == 'External'}
        linked_ids = {h.get(f'{{{R}}}id') for h in root.findall('.//w:hyperlink', NS)
                      if h.get(f'{{{R}}}id')}
        geometry = [section_geometry(section) for section in root.findall('.//w:sectPr', NS)]
        extra = []
        for name in package.namelist():
            if re.fullmatch(r'word/(?:header|footer)\d+\.xml', name):
                extra.append(xml_text(ET.fromstring(package.read(name))))
        return {
            'text': xml_text(root), 'extra_text': '\n'.join(extra),
            'urls': {targets[rid] for rid in linked_ids if rid in targets},
            'broken_link_ids': sorted(linked_ids - set(targets)),
            'geometry': geometry,
            'has_revisions': bool(root.findall('.//w:ins', NS) or root.findall('.//w:del', NS)),
            'parts': {name: package.read(name) for name in package.namelist()},
        }


def finding(identifier, status, evidence, *, gate=True, method='automatic', next_action=''):
    return dict(id=identifier, status=status, gate=gate, method=method,
                evidence=evidence, next_action=next_action)


def evaluate(config_path):
    config_path = Path(config_path).resolve()
    config = load_json(config_path)
    if config.get('schema_version') != 1:
        raise ConfigError('schema_version must be 1')

    def resolve(value):
        if not isinstance(value, str) or not value:
            raise ConfigError('File paths must be nonempty strings')
        return (config_path.parent / value).resolve()

    for key in ['markdown', 'docx', 'jd']:
        if key not in config:
            raise ConfigError(f'Missing {key}')
    md_path, docx_path, jd_path = [resolve(config[key]) for key in ['markdown', 'docx', 'jd']]
    evidence_paths = [resolve(p) for p in config.get('evidence_sources', [])]
    required_bindings = {md_path, docx_path, jd_path, *evidence_paths}
    protected = config.get('protected_files', [])
    protected_paths = [resolve(item['path']) for item in protected]
    inputs = {config_path, *required_bindings, *protected_paths}
    if config.get('template'):
        inputs.add(resolve(config['template']))
    if config.get('review'):
        inputs.add(resolve(config['review']))
    for path in inputs:
        if not path.is_file():
            raise ConfigError(f'Input file does not exist: {path}')

    before = {str(p): digest(p) for p in inputs}
    markdown = md_path.read_text(encoding='utf-8')
    docx = docx_data(docx_path)
    checks = []

    def check(identifier, passed, success, failure):
        checks.append(finding(identifier, 'pass' if passed else 'fail', [success if passed else failure]))

    supported = not re.search(r'^\s*(?:```|~~~|\||<)|!\[', markdown, re.M)
    checks.append(finding('markdown_format_supported', 'pass' if supported else 'unverified',
                          ['Basic CV Markdown supported.' if supported else
                           'Complex Markdown requires a format-aware parity review.']))
    combined = markdown + '\n' + docx['text'] + '\n' + docx['extra_text']
    check('no_em_dash', '\u2014' not in combined, 'No em dashes in Markdown or DOCX text.',
          'An em dash occurs in the candidate artifact.')
    placeholders = PLACEHOLDER.findall(combined)
    check('no_placeholders', not placeholders, 'No recognised draft placeholders.',
          f'Draft placeholders found: {placeholders[:5]}')
    if supported:
        md_text, document_text = normalise(markdown_text(markdown)), normalise(docx['text'])
        check('markdown_docx_parity', md_text == document_text,
              'Markdown and main DOCX text agree after formatting normalisation.',
              'Markdown and DOCX content differ. Inspect numbers, titles and omitted text.')
        if md_text != document_text:
            checks[-1]['evidence'].extend(text_differences(md_text, document_text))
    else:
        checks.append(finding('markdown_docx_parity', 'unverified', ['Unsupported Markdown structure.']))
    check('no_unreviewed_header_footer_text', not normalise(docx['extra_text']),
          'No additional header/footer text outside the canonical Markdown.',
          'Header/footer text needs explicit comparison with the canonical content.')
    md_urls = {match.group(2) for match in LINK.finditer(markdown)}
    missing = sorted(md_urls - docx['urls'])
    extra = sorted(docx['urls'] - md_urls)
    check('hyperlink_parity', not missing and not extra and not docx['broken_link_ids'],
          f'{len(md_urls)} external link targets match.',
          f'Missing targets={missing}; unexpected targets={extra}; broken IDs={docx["broken_link_ids"]}')
    check('no_tracked_changes', not docx['has_revisions'], 'No tracked insertions/deletions.',
          'Tracked changes remain in the final document.')
    if not protected:
        checks.append(finding('protected_sources', 'unverified', ['No baseline source hashes configured.']))
    for index, item in enumerate(protected):
        expected = item.get('sha256', '')
        if not re.fullmatch(r'[a-f0-9]{64}', expected):
            raise ConfigError('Protected files need a valid lowercase SHA-256')
        path = resolve(item['path'])
        check(f'protected_source_{index + 1}', digest(path) == expected,
              f'Protected source unchanged: {path}', f'Protected source hash mismatch: {path}')

    if config.get('template'):
        template = docx_data(resolve(config['template']))
        if config.get('preserve_geometry', False):
            check('template_geometry', docx['geometry'] == template['geometry'],
                  'Section page geometry matches the selected template.', 'Template page geometry changed.')
        if config.get('preserve_source_links', False):
            check('source_hyperlinks', template['urls'] <= docx['urls'],
                  'Original active external links preserved.', 'An original active external link was removed or changed.')
        for index, part in enumerate(config.get('preserve_package_parts', [])):
            if part not in template['parts']:
                raise ConfigError(f'Configured preserve-only part not in template: {part}')
            check(f'preserve_package_part_{index + 1}', docx['parts'].get(part) == template['parts'][part],
                  f'Preserved package part: {part}', f'Package part changed or missing: {part}')
        for index, part in enumerate(config.get('inspect_package_parts', [])):
            if part not in template['parts']:
                raise ConfigError(f'Configured inspection part not in template: {part}')
            same = docx['parts'].get(part) == template['parts'][part]
            checks.append(finding(f'inspect_package_part_{index + 1}', 'pass' if same else 'unverified',
                                  [f'Byte-identical template part: {part}' if same else
                                   f'Part changed or missing: {part}. XML serialization can change without '
                                   'a visual defect; inspect rendered formatting before concluding.'],
                                  gate=False, next_action='' if same else 'Review visual preservation.'))

    review = None
    dimensions = {}
    review_current = False
    if config.get('review'):
        review = load_json(resolve(config['review']))
        if not review.get('reviewer') or not review.get('reviewed_at'):
            raise ConfigError('Review needs reviewer and reviewed_at')
        bindings = {}
        review_base = resolve(config['review']).parent
        for item in review.get('bindings', []):
            path = (review_base / item['path']).resolve()
            if path in bindings:
                raise ConfigError(f'Duplicate review binding: {path}')
            bindings[path] = item['sha256']
        missing_bindings = required_bindings - set(bindings)
        stale = [str(path) for path, expected in bindings.items()
                 if not path.is_file() or digest(path) != expected]
        review_current = not missing_bindings and not stale
        check('review_freshness', review_current, 'Evidence review is bound to current artifacts and sources.',
              f'Missing bindings={sorted(str(p) for p in missing_bindings)}; stale files={stale}')
        for dimension in review.get('dimensions', []):
            identifier = dimension.get('id')
            if identifier not in DIMENSIONS or identifier in dimensions:
                raise ConfigError(f'Unknown or duplicate review dimension: {identifier}')
            if dimension.get('status') not in STATUSES:
                raise ConfigError(f'Invalid review status for {identifier}')
            evidence = dimension.get('evidence')
            if not isinstance(evidence, list) or not evidence or not all(isinstance(s, str) and s.strip() for s in evidence):
                raise ConfigError(f'Review dimension needs nonempty evidence: {identifier}')
            dimensions[identifier] = dimension
    semantic = []
    for identifier, gate in DIMENSIONS.items():
        entry = dimensions.get(identifier) if review_current else None
        semantic.append(finding(identifier, entry['status'] if entry else 'unverified',
                                entry['evidence'] if entry else ['No current, artifact-bound judgement supplied.'],
                                gate=gate, method='supplied_review',
                                next_action=entry.get('next_action', '') if entry else 'Complete this evidence review.'))

    check('evaluation_read_only', all(digest(p) == value for p, value in before.items()),
          'All inputs unchanged by evaluation.', 'An input changed during evaluation.')
    gated = [result for result in checks + semantic if result['gate']]
    if any(result['status'] == 'fail' for result in gated):
        decision = 'blocked'
    elif any(result['status'] != 'pass' for result in gated):
        decision = 'needs_review'
    else:
        decision = 'eligible_for_final_review'
    return {
        'schema_version': 1, 'decision': decision,
        'label': 'CV quality evaluation, not an ATS score or submission authorisation',
        'inputs': before, 'automatic_checks': checks, 'semantic_review': semantic,
        'reviewer': review.get('reviewer') if review else None,
        'reviewed_at': review.get('reviewed_at') if review else None,
        'limitations': ['Semantic findings are supplied reviewer judgements, not machine-verified truth.',
                        'XML, hashes and page count do not establish visual layout quality.'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        report = evaluate(args.config)
        encoded = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        if args.output:
            output = args.output.resolve()
            if str(output) in report['inputs']:
                raise ConfigError('Output must not overwrite an input')
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(encoded, encoding='utf-8')
        print(encoded, end='')
        return 0 if report['decision'] == 'eligible_for_final_review' else 1
    except (ConfigError, OSError, ValueError, KeyError, TypeError, ET.ParseError, BadZipFile) as error:
        print(f'EVAL ERROR: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
