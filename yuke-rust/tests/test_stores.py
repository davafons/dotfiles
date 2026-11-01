"""Check retained inbox drafts, delivery claims, and conservative task ownership."""
import contextlib
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HELPERS = Path(__file__).resolve().parents[1] / '.config/yuke-rust/helpers'

def load(name):
    specification = importlib.util.spec_from_file_location(name, HELPERS / (name + '.py'))
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module

inbox = load('yuke-clarify-store')
work = load('project-work-store')

class Stores(unittest.TestCase):
    def test_pending_adoption_retains_drafts_and_delivery_requires_the_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / 'questions.db')
            question = dict(title='Storage', question='Keep this draft?', context='', options=[], multi_select=False)
            old, new = '1' * 32, '019a3d2b-1234-7000-8000-000000000002'
            record = inbox.operate(database, 'add', dict(session=old, site='fixture', question=question))
            draft = dict(inbox.new_draft(), text='Keep my notes', selected=0)
            inbox.operate(database, 'draft', dict(id=record['id'], draft=draft))
            adopted = inbox.operate(database, 'adopt', dict(id=record['id'], session=new))
            self.assertEqual((adopted['session'], adopted['origin_session'], adopted['draft']), (new, old, draft))
            self.assertEqual(inbox.operate(database, 'list', {})[0]['id'], record['id'])
            claim = inbox.operate(database, 'claim', dict(id=record['id'], kind='dismissed', answer='', responses=[]))
            with self.assertRaisesRegex(ValueError, 'claim'):
                inbox.operate(database, 'finish', dict(id=record['id'], token='wrong', input_id=7))
            with self.assertRaisesRegex(ValueError, 'only a pending'):
                inbox.operate(database, 'adopt', dict(id=record['id'], session=old))
            finished = inbox.operate(database, 'finish', dict(id=record['id'], token=claim['token'], input_id=7))
            self.assertEqual(finished['status'], 'dismissed')
            self.assertEqual(inbox.operate(database, 'list', {}), [])

    def test_batch_adoption_keeps_unanswered_questions_and_their_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / 'questions.db')
            question = dict(title='Scope', question='Choose scope?', context='', options=[], multi_select=False, question_id='scope')
            record = inbox.operate(database, 'add_batch', dict(session='1' * 32, site='batch', questions=[question]))
            draft = dict(inbox.new_draft(), text='Not an approval')
            inbox.operate(database, 'draft', dict(id=record['questions'][0]['id'], draft=draft))
            adopted = inbox.operate(database, 'adopt_batch', dict(id=record['id'], session='2' * 32))
            self.assertEqual(adopted['questions'][0]['draft'], draft)
            with self.assertRaisesRegex(ValueError, 'unanswered'):
                inbox.operate(database, 'claim_batch', dict(id=record['id']))
            claimed = inbox.operate(database, 'claim_batch', dict(id=record['id'], allow_unanswered=True))
            self.assertEqual(claimed['answers'], {'scope': {'answers': []}})

    def test_native_session_locks_distinguish_open_closed_and_legacy_unknown(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_DATA_HOME': directory, 'YUKE_APPNAME': 'yuke-rust'}):
            base = Path(directory) / 'yuke-rust'
            lock = base / 'sessions' / ('1' * 32) / 'lock'
            lock.parent.mkdir(parents=True)
            (base / 'yuke.db').touch()
            with lock.open('w') as owner:
                fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                with contextlib.ExitStack() as guards:
                    self.assertEqual(work.tree_presence('11111111-1111-1111-1111-111111111111', guards), 'open')
                fcntl.flock(owner.fileno(), fcntl.LOCK_UN)
                with contextlib.ExitStack() as guards:
                    self.assertEqual(work.tree_presence('1' * 32, guards), 'closed')
            with contextlib.ExitStack() as guards:
                self.assertEqual(work.tree_presence('2' * 32, guards), 'unknown')

if __name__ == '__main__':
    unittest.main()
