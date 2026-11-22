#!/usr/bin/env python3
"""Read one snapshot of the session logs. Price estimates use the current catalog, never a guessed historical rate."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
import sys
import uuid

FIELDS = ('input', 'output', 'reasoning', 'cacheRead', 'cacheWrite')


def bucket(name=''):
    return dict(name=name, **{field: 0 for field in FIELDS}, cost=0., withoutCache=0., unpriced=0,
                unreported=0, messages=0, tools=0)


def add(target, usage, price):
    target['messages'] += 1
    target['unreported'] += any(usage[field] is None for field in FIELDS[:2])
    for field in FIELDS:
        target[field] += usage[field] or 0
    if price is None:
        target['unpriced'] += 1
    else:
        target['cost'] += price[0]
        target['withoutCache'] += price[1]


def estimate(usage, costs):
    if usage['input'] is None or usage['output'] is None:
        return None
    bands = [band for band in costs if band['minPromptTokens'] <= usage['input']]
    if not bands:
        return None
    band = bands[-1]
    counts = dict(usage)
    counts['input'] = max(0, usage['input'] - (usage['cacheRead'] or 0) - (usage['cacheWrite'] or 0))
    counts['output'] = max(0, usage['output'] - (usage['reasoning'] or 0))
    cost = 0.
    for field, count in counts.items():
        rate = band.get(field, band.get('output') if field == 'reasoning' else None)
        if count and rate is None:
            return None
        cost += (count or 0) * (rate or 0) / 1_000_000
    if band.get('input') is None or band.get('output') is None:
        return None
    return cost, (usage['input'] * band['input'] + usage['output'] * band['output']) / 1_000_000


def lines(path):
    """The JSON objects of the complete lines of `path`. A torn last line of a running write is no line."""
    with path.open('rb') as file:
        for line in file:
            if line.endswith(b'\n'):
                yield json.loads(line)


def sessions(data):
    """The newest facts of each session in the index, without deleted sessions."""
    facts = {}
    if not (data / 'sessions.jsonl').exists():
        return facts
    for line in lines(data / 'sessions.jsonl'):
        if line.get('deleted'):
            facts.pop(line['id'], None)
        elif line.get('meta') is not None:
            facts[line['id']] = line['meta']
    return facts


def snapshot(request):
    catalog = {(provider['id'], model['id']): model for provider in request['providers'] for model in provider['models']}
    data = Path(request['data']).resolve()
    totals = bucket()
    daily, models, providers = defaultdict(bucket), defaultdict(bucket), defaultdict(bucket)
    tools = defaultdict(lambda: dict(calls=0, errors=0, durationMs=0))
    roles, finishes, outcomes, efforts, skills = Counter(), Counter(), Counter(), Counter(), Counter()
    chats = []
    for ident, meta in sessions(data).items():
        if request.get('workspace') is not None and meta['folder'] != request['workspace']:
            continue
        session = uuid.UUID(ident)
        chat = dict(id=ident, title=meta.get('title') or '(empty chat)', root=meta['folder'],
                    kind='child' if meta.get('parent') else 'chat', input=0, output=0, messages=0,
                    # A version 7 id starts with the millisecond of its creation.
                    created=session.int >> 80, updated=meta['position'] // 1000)
        current = {}
        names = {}
        try:
            events = list(lines(data / 'sessions' / session.hex / 'events.jsonl'))
        except FileNotFoundError:
            continue
        for event in events:
            if event['kind'] == 'settings':
                current = event
                continue
            commit = event['commit']
            for block in commit.get('blocks', []):
                kind = block.get('kind')
                roles[kind] += 1
                if kind == 'toolCall':
                    tools[block['name']]['calls'] += 1
                    names[block['callId']] = block['name']
                if kind == 'toolResult' and block['isError'] and block['callId'] in names:
                    tools[names[block['callId']]]['errors'] += 1
                if kind == 'userText':
                    for name in re.findall(r'<skill name="([^"]+)"', block['text']):
                        skills[name] += 1
            if commit.get('end'):
                outcomes[commit['end']['kind']] += 1
            answer = commit.get('answer')
            if answer is None:
                continue
            usage = {field: answer['usage'].get(field) for field in FIELDS}
            provider = current['model']['provider']
            model = answer['origin']['model']
            # A round hook can change the upstream model. No exact catalog id means no price estimate.
            known = catalog.get((provider, model))
            price = estimate(usage, known.get('cost', [])) if known else None
            day = datetime.fromtimestamp(event['at'] / 1000).astimezone().date().isoformat()
            for target in (totals, daily[day], models[model], providers[provider]):
                add(target, usage, price)
            chat['messages'] += 1
            chat['input'] += usage['input'] or 0
            chat['output'] += usage['output'] or 0
            finishes[answer['finishReason']] += 1
            efforts[(current.get('settings', {}).get('reasoning') or {}).get('effort') or 'default'] += 1
        chats.append(chat)
    days = sorted(daily)
    longest = streak = 0
    previous = None
    for value in days:
        today = date.fromisoformat(value)
        streak = streak + 1 if previous is not None and today - previous == timedelta(days=1) else 1
        longest = max(longest, streak)
        previous = today
    current_streak = streak if previous is not None and date.today() - previous <= timedelta(days=1) else 0
    def ranked(values):
        return sorted((dict(value, name=name) for name, value in values.items()), key=lambda value: -value['input'])
    return dict(totals=totals, daily=[dict(value, date=key) for key, value in sorted(daily.items())],
                models=ranked(models), providers=ranked(providers), roles=dict(roles), finishes=dict(finishes), outcomes=dict(outcomes),
                efforts=dict(efforts), tools=[dict(value, name=name) for name, value in sorted(tools.items())], skills=dict(skills),
                chats=sorted(chats, key=lambda chat: -chat['updated']), currentStreak=current_streak, longestStreak=longest,
                notes=['Costs are estimates at current catalog prices. Unknown rates stay unpriced.',
                       'Input includes cache tokens. Output includes reasoning. Fork copies are counted as retained history.',
                       'Provider labels follow saved session settings. A round hook can use another route.'])


if __name__ == '__main__':
    try:
        print(json.dumps(snapshot(json.loads(Path(sys.argv[1]).read_text()))))
    except (OSError, ValueError, KeyError, TypeError):
        sys.stderr.write('Cannot read the Rust usage snapshot.\n')
        sys.exit(1)
