"""Protocol tests for bin/run (stdlib only).

Runs the plugin as a subprocess against a temporary Dropbox root and a fake
dropbox-cli. FLEA_DROPBOX_NO_SPAWN=1 keeps GUI/browser/clipboard children off.
"""
import json
import os
import select
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin", "run")

FAKE_CLI = """#!/bin/sh
echo "$*" >> "$FAKE_DBX_LOG"
case "$1 $2" in
  "exclude list")
    echo "Excluded folders:"
    if [ -f "$FAKE_DBX_STATE" ]; then sed 's#^/##' "$FAKE_DBX_STATE"; fi
    ;;
  "exclude add")
    shift 2
    for p in "$@"; do echo "$p" >> "$FAKE_DBX_STATE"; done
    ;;
  "exclude remove")
    exit 0
    ;;
  "sharelink "*)
    echo "https://www.dropbox.com/scl/fo/fake/$(basename "$2")?dl=0"
    ;;
  *)
    echo "fake cli: unsupported $*" >&2
    exit 2
    ;;
esac
exit 0
"""


class Session:
    """One running bin/run process speaking JSON lines."""

    def __init__(self, env):
        self.proc = subprocess.Popen([BIN], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, env=env)

    def send(self, obj):
        self.proc.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
        self.proc.stdin.flush()
        ready, _, _ = select.select([self.proc.stdout], [], [], 15)
        if not ready:
            raise AssertionError("no reply within 15 s for %r" % (obj,))
        line = self.proc.stdout.readline()
        if not line:
            raise AssertionError("plugin closed stdout")
        return json.loads(line.decode("utf-8"))

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        for pipe in (self.proc.stdout, self.proc.stderr):
            pipe.close()


class PluginTest(unittest.TestCase):

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="flea-dropbox-test-"))
        self.dbx = os.path.join(self.tmp, "Dropbox")
        self.docs = os.path.join(self.dbx, "Docs")
        self.excl = os.path.join(self.docs, "Excl")
        self.empty = os.path.join(self.dbx, "Empty")
        self.notes = os.path.join(self.dbx, "Notes.txt")
        for d in (self.excl, self.empty, os.path.join(self.docs, "Other")):
            os.makedirs(d)
        with open(self.notes, "w", encoding="utf-8") as fh:
            fh.write("x")
        self.info = os.path.join(self.tmp, "info.json")
        with open(self.info, "w", encoding="utf-8") as fh:
            json.dump({"personal": {"path": self.dbx, "host": 1, "is_team": False}}, fh)
        self.cli = os.path.join(self.tmp, "dropbox-cli")
        with open(self.cli, "w", encoding="utf-8") as fh:
            fh.write(FAKE_CLI)
        os.chmod(self.cli, 0o755)
        self.state = os.path.join(self.tmp, "excluded.txt")
        self.log = os.path.join(self.tmp, "cli.log")
        self.env = dict(os.environ,
                        FLEA_DROPBOX_CLI=self.cli,
                        FLEA_DROPBOX_INFO=self.info,
                        FLEA_DROPBOX_NO_SPAWN="1",
                        FAKE_DBX_STATE=self.state,
                        FAKE_DBX_LOG=self.log)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def session(self):
        s = Session(self.env)
        self.addCleanup(s.close)
        return s

    def cli_log(self):
        if not os.path.exists(self.log):
            return ""
        with open(self.log, encoding="utf-8") as fh:
            return fh.read()

    def mark_excluded(self, path):
        with open(self.state, "a", encoding="utf-8") as fh:
            fh.write(path + "\n")

    def test_hello_ready(self):
        s = self.session()
        self.assertEqual(s.send({"op": "hello", "protocolVersion": 1}),
                         {"op": "ready", "protocolVersion": 1})

    def test_settings_done(self):
        s = self.session()
        self.assertEqual(s.send({"op": "settings", "settings": {}}), {"op": "done"})

    def test_exclude_folder_calls_cli_add(self):
        s = self.session()
        reply = s.send({"op": "run", "action": "exclude", "paths": [self.empty]})
        self.assertEqual(reply["op"], "done", reply)
        self.assertIn("exclude add " + self.empty, self.cli_log())

    def test_exclude_root_is_refused_without_cli_call(self):
        s = self.session()
        reply = s.send({"op": "run", "action": "exclude", "paths": [self.dbx]})
        self.assertEqual(reply["op"], "error", reply)
        self.assertNotIn("exclude add", self.cli_log())

    def test_path_outside_root_error(self):
        s = self.session()
        reply = s.send({"op": "run", "action": "sharelink", "paths": ["/etc"]})
        self.assertEqual(reply, {"op": "error",
                                 "message": "Il percorso non è nella cartella Dropbox."})

    def test_manage_without_excluded_error(self):
        s = self.session()
        reply = s.send({"op": "run", "action": "manage", "paths": [self.empty]})
        self.assertEqual(reply, {"op": "error",
                                 "message": "Nessuna cartella esclusa in questa posizione."})

    def test_manage_with_excluded_done_without_spawn(self):
        self.mark_excluded(self.excl)
        s = self.session()
        reply = s.send({"op": "run", "action": "manage", "paths": [self.docs]})
        self.assertEqual(reply, {"op": "done", "message": "Finestra aperta."})

    def test_manage_uses_folder_field_for_background_menu(self):
        self.mark_excluded(self.excl)
        s = self.session()
        reply = s.send({"op": "run", "action": "manage", "paths": [], "folder": self.docs})
        self.assertEqual(reply, {"op": "done", "message": "Finestra aperta."})

    def test_sharelink_done(self):
        s = self.session()
        reply = s.send({"op": "run", "action": "sharelink", "paths": [self.empty]})
        self.assertEqual(reply["op"], "done", reply)
        self.assertIn("https://www.dropbox.com/scl/fo/fake/", reply["message"])

    def test_view_done_without_spawn(self):
        s = self.session()
        reply = s.send({"op": "run", "action": "view", "paths": [self.docs]})
        self.assertEqual(reply["op"], "done", reply)
        self.assertIn("https://www.dropbox.com/home/", reply["message"])

    def test_unknown_op_error_then_process_alive(self):
        s = self.session()
        reply = s.send({"op": "bogus"})
        self.assertEqual(reply["op"], "error")
        self.assertIsNone(s.proc.poll())
        self.assertEqual(s.send({"op": "hello", "protocolVersion": 1}),
                         {"op": "ready", "protocolVersion": 1})

    def test_cancel_exits_zero(self):
        s = self.session()
        s.proc.stdin.write(b'{"op":"cancel"}\n')
        s.proc.stdin.flush()
        self.assertEqual(s.proc.wait(timeout=10), 0)

    def test_eof_exits_zero(self):
        s = self.session()
        s.proc.stdin.close()
        self.assertEqual(s.proc.wait(timeout=10), 0)


if __name__ == "__main__":
    unittest.main()
