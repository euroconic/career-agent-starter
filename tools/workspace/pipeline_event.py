"""Pure, replay-safe pipeline proposal application. The coordinator owns writes."""
from pathlib import Path
import hashlib
import json
import re

from pipeline_check import parse_records, VALID_STAGES


def apply_event(text, event, root):
    """Return new Markdown; reject conflicting/stale proposals without writing.

    A caller still needs explicit task authority and safe_output.publish_bytes
    with the previous file hash. This function verifies structure, not truth.
    """
    required = {'event_id', 'application_id', 'event_date', 'description', 'source',
                'expected_stage', 'stage', 'next', 'owner', 'due'}
    if not required <= event.keys():
        raise ValueError('Missing event fields: ' + ', '.join(sorted(required - event.keys())))
    if any(not isinstance(event[k], str) or not event[k].strip() or '\n' in event[k] or '\r' in event[k] for k in required):
        raise ValueError('Event fields must be nonempty single-line strings')
    if not re.fullmatch(r'[A-Za-z0-9_.:-]+', event['event_id']):
        raise ValueError('Invalid event ID')
    if event['stage'] not in VALID_STAGES:
        raise ValueError('Unknown stage')
    root = Path(root).resolve()
    source = (root / event['source']).resolve()
    if root not in source.parents or not source.is_file():
        raise ValueError('Event source must be an existing file in the selected workspace')
    digest = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
    marker = '- Processed event: ' + event['event_id'] + ' '
    for line in text.splitlines():
        if line.startswith(marker):
            if line == marker + digest:
                return text
            raise ValueError('Event ID reused with different content')
    records, errors = parse_records(text)
    if errors:
        raise ValueError('Invalid current pipeline: ' + '; '.join(errors))
    matches = [r for r in records if r['heading_id'] == event['application_id']]
    if len(matches) != 1:
        raise ValueError('Proposal must identify one existing application')
    current = matches[0]
    stage = current['fields']['Stage'][0]
    if stage != event['expected_stage']:
        raise ValueError('Stage changed since proposal was prepared')
    if stage == 'Closed' and event['stage'] != 'Closed':
        raise ValueError('Reopening a closed application needs a separately reviewed edit')
    lines = text.splitlines(True)
    start = current['line'] - 1
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith(('### ', '## ')):
            end = index
            break
    content_end = end
    while content_end > start and not lines[content_end - 1].strip():
        content_end -= 1
    block = ''.join(lines[start:content_end])
    updates = {'Stage': event['stage'], 'Last event': event['description'] + ' (' + event['event_date'] + ')',
               'Event source': '`' + event['source'] + '`', 'Next': event['next'],
               'Owner': event['owner'], 'Due': event['due']}
    for key, value in updates.items():
        block = re.sub(r'^- ' + re.escape(key) + r':[^\r\n]*',
                       lambda _, key=key, value=value: '- ' + key + ': ' + value,
                       block, flags=re.M)
    line_ending = '\r\n' if '\r\n' in text else '\n'
    if not block.endswith(('\n', '\r')):
        block += line_ending
    block += marker + digest + line_ending
    prefix = ''.join(lines[:start])
    suffix = ''.join(lines[content_end:])
    if event['stage'] != 'Closed' or current['area'] == 'Closed':
        updated = prefix + block + suffix
    else:
        # Remove only the selected record block. All surrounding notes, headings,
        # and separators remain byte-for-byte in the original prefix or suffix.
        remaining = prefix + suffix
        closed_heading = re.search(r'(?m)^## Closed[ \t]*(?:\r?\n|$)', remaining)
        if closed_heading is None:
            separator = '' if not remaining or remaining.endswith(('\n\n', '\r\n\r\n')) else '\n\n'
            updated = remaining + separator + '## Closed\n\n' + block.rstrip('\r\n') + '\n'
        else:
            closed_start = closed_heading.end()
            next_section = re.search(r'(?m)^## (?!Closed(?:[ \t]*$)).*$', remaining[closed_start:])
            closed_end = closed_start + next_section.start() if next_section else len(remaining)
            closed_content = remaining[closed_start:closed_end]
            trailing_space = re.search(r'(?:[ \t]*\r?\n)*\Z', closed_content)
            insertion = closed_start + trailing_space.start()
            before = remaining[:insertion]
            after = remaining[insertion:]
            left = '' if not before or before.endswith(('\n\n', '\r\n\r\n')) else '\n'
            right = '' if not after or after.startswith(('\n', '\r')) else '\n'
            updated = before + left + block.rstrip('\r\n') + '\n' + right + after
    _, errors = parse_records(updated)
    if errors:
        raise ValueError('Invalid proposed pipeline: ' + '; '.join(errors))
    return updated
