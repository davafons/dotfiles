#!/usr/bin/env python3
"""Read one SQLite snapshot. Price estimates use the current catalog, never a guessed historical rate."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sqlite3
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


def snapshot(request):
    catalog = {(provider['id'], model['id']): model for provider in request['providers'] for model in provider['models']}
    database = Path(request['database']).resolve()
    db = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    totals = bucket()
    daily, models, providers = defaultdict(bucket), defaultdict(bucket), defaultdict(bucket)
    tools = defaultdict(lambda: dict(calls=0, errors=0, durationMs=0))
    roles, finishes, outcomes, efforts, skills = Counter(), Counter(), Counter(), Counter(), Counter()
    chats = []
    try:
        db.execute('BEGIN')
        for session in db.execute('SELECT * FROM sessions WHERE (? IS NULL OR cwd=?)', (request.get('workspace'), request.get('workspace'))):
            current = json.loads(session['settings'])
            chat = dict(id=str(uuid.UUID(bytes=session['id'])), title=session['preview'] or '(empty chat)', root=session['cwd'],
                        kind='child' if session['parent'] else 'chat', input=0, output=0, messages=0,
                        created=session['created_at'], updated=session['updated_at'])
            for event in db.execute('SELECT * FROM events WHERE session_id=? ORDER BY seq', (session['id'],)):
                if event['kind'] == 'settings':
                    current = json.loads(event['settings'])
                    continue
                blocks = json.loads(event['blocks'] or '[]')
                display = json.loads(event['display'] or '{}')
                for block in blocks:
                    for kind in block:
                        roles[kind] += 1
                    if 'tool_call' in block:
                        name = block['tool_call']['name']
                        tools[name]['calls'] += 1
                    if 'tool_result' in block and block['tool_result']['isError']:
                        call_id = block['tool_result']['callId']
                        # A bounded lookup inside the session identifies a result, without reading another store.
                        row = db.execute("SELECT json_extract(value, '$.tool_call.name') FROM events, json_each(events.blocks) WHERE session_id=? AND json_extract(value, '$.tool_call.callId')=? LIMIT 1", (session['id'], call_id)).fetchone()
                        if row:
                            tools[row[0]]['errors'] += 1
                    if 'user_text' in block:
                        import re
                        for name in re.findall(r'<skill name="([^"]+)"', block['user_text']):
                            skills[name] += 1
                if event['end_kind']:
                    outcomes[event['end_kind']] += 1
                if event['model'] is None:
                    continue
                usage = {field: event[column] for field, column in zip(FIELDS, ('input_tokens', 'output_tokens', 'reasoning_tokens', 'cache_read_tokens', 'cache_write_tokens'))}
                provider = current['model']['provider']
                model = event['model']
                # A round hook can change the upstream model. No exact catalog id means no price estimate.
                known = catalog.get((provider, model))
                price = estimate(usage, known.get('cost', [])) if known else None
                day = datetime.fromtimestamp(event['created_at'] / 1000).astimezone().date().isoformat()
                for target in (totals, daily[day], models[model], providers[provider]):
                    add(target, usage, price)
                chat['messages'] += 1
                chat['input'] += usage['input'] or 0
                chat['output'] += usage['output'] or 0
                finishes[event['finish_reason']] += 1
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
    finally:
        db.close()


if __name__ == '__main__':
    try:
        print(json.dumps(snapshot(json.loads(Path(sys.argv[1]).read_text()))))
    except (sqlite3.Error, OSError, ValueError, KeyError, TypeError):
        sys.stderr.write('Cannot read the Rust usage snapshot.\n')
        sys.exit(1)
