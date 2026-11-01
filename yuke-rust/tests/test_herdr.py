"""Check the Herdr socket contract with a private server. No user pane is controlled."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import unittest

class Herdr(unittest.TestCase):
    def test_navigation_round_trips_framed_json(self):
        binary = os.environ.get('YUKE_BINARY') or shutil.which('yuke-rust')
        if binary is None:
            self.skipTest('Set YUKE_BINARY to test the native Unix transport.')
        with tempfile.TemporaryDirectory(prefix='yuke-herdr-', dir='/tmp') as directory:
            path = str(Path(directory) / 'ipc.sock')
            server = socket.socket(socket.AF_UNIX)
            server.bind(path)
            server.listen()
            server.settimeout(10)
            requests, errors = [], []
            def serve():
                try:
                    for _ in range(4):
                        connection, _ = server.accept()
                        with connection, connection.makefile('rb') as reader:
                            request = json.loads(reader.readline())
                            requests.append(request)
                            result = dict(type='ok')
                            if request['method'] == 'pane.list':
                                result = dict(type='pane_list', panes=[dict(pane_id='fixture-pane', agent='yuke', tokens=dict(yuke_session_id='019a3d2b-1234-7000-8000-000000000002'))])
                            encoded = (json.dumps(dict(id=request['id'], result=result)) + '\n').encode()
                            connection.sendall(encoded[:12])
                            connection.sendall(encoded[12:])
                except Exception as error:
                    errors.append(error)
            thread = threading.Thread(target=serve, daemon=True)
            thread.start()
            result = subprocess.run([binary, 'test', str(Path(__file__).resolve().parents[1] / 'scripts/herdr.test.ts')], capture_output=True, text=True, timeout=20, env=dict(os.environ, HERDR_ENV='1', HERDR_SOCKET_PATH=path))
            thread.join(timeout=11)
            server.close()
            self.assertFalse(thread.is_alive(), 'The IPC fixture did not finish.')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(errors, [], result.stdout + result.stderr)
            self.assertEqual([request['method'] for request in requests], ['pane.list', 'pane.focus', 'pane.list', 'plugin.action.invoke'])
            self.assertEqual(requests[1]['params'], dict(pane_id='fixture-pane'))
            self.assertEqual(requests[3]['params']['context']['clicked_url'], 'file:///tmp/a%20b.rs#L7C2')

if __name__ == '__main__':
    unittest.main()
