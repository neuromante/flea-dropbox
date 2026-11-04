"""Protocol tests for bin/run (stdlib only).

Runs the plugin as a subprocess against a temporary Dropbox root and a fake
dropbox-cli. FLEA_DROPBOX_NO_SPAWN=1 keeps GUI/browser/clipboard children off.
"""
import importlib.machinery
import importlib.util
import json
import os
import select
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin", "run")


def load_run():
    """bin/run has no .py suffix, so load it with an explicit SourceFileLoader."""
    loader = importlib.machinery.SourceFileLoader("flea_dropbox_run", BIN)
    spec = importlib.util.spec_from_loader("flea_dropbox_run", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


run = load_run()

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

    def test_manage_without_excluded_done_without_spawn(self):
        s = self.session()
        reply = s.send({"op": "run", "action": "manage", "paths": [self.empty]})
        self.assertEqual(reply, {"op": "done", "message": "Finestra aperta."})

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

    def test_manage_outside_dropbox_done(self):
        s = self.session()
        reply = s.send({"op": "run", "action": "manage", "paths": ["/etc"]})
        self.assertEqual(reply, {"op": "done", "message": "Finestra aperta."})

    def test_manage_folder_outside_dropbox_done(self):
        s = self.session()
        reply = s.send({"op": "run", "action": "manage", "paths": [], "folder": "/etc"})
        self.assertEqual(reply, {"op": "done", "message": "Finestra aperta."})

    def test_view_outside_dropbox_opens_home(self):
        s = self.session()
        reply = s.send({"op": "run", "action": "view", "paths": ["/etc"]})
        self.assertEqual(reply, {"op": "done", "message": "Aperto su dropbox.com."})

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


class TreeTest(unittest.TestCase):
    """Pure functions of bin/run: build_tree and plan_changes."""

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="flea-dropbox-tree-"))
        self.root = os.path.join(self.tmp, "Dropbox")
        for d in ("A/B/C/D/E", "alpha", "Beta", "Z", ".hidden/x"):
            os.makedirs(os.path.join(self.root, d))
        with open(os.path.join(self.root, "file.txt"), "w", encoding="utf-8") as fh:
            fh.write("x")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def path(self, rel):
        return os.path.join(self.root, rel)

    def rels(self, tree):
        return [n["rel"] for n in tree["nodes"]]

    def test_depth_limit_hidden_skipped_and_files_ignored(self):
        tree = run.build_tree(self.root, [])
        self.assertEqual(self.rels(tree), ["A", "A/B", "A/B/C", "A/B/C/D", "alpha", "Beta", "Z"])
        self.assertFalse(tree["truncated"])
        d = [n for n in tree["nodes"] if n["rel"] == "A/B/C/D"][0]
        self.assertEqual(d["depth"], 3)
        self.assertFalse(d["hasChildren"])  # E would be depth 4: not listed

    def test_order_is_depth_first_case_insensitive(self):
        tree = run.build_tree(self.root, [])
        self.assertEqual(self.rels(tree)[-3:], ["alpha", "Beta", "Z"])
        self.assertEqual(self.rels(tree)[0:2], ["A", "A/B"])
        self.assertTrue(all(n["synced"] for n in tree["nodes"]))

    def test_has_children_flags(self):
        tree = run.build_tree(self.root, [self.path("A/B")])
        nodes = {n["rel"]: n for n in tree["nodes"]}
        self.assertTrue(nodes["A"]["hasChildren"])
        self.assertFalse(nodes["A/B"]["hasChildren"])
        self.assertFalse(nodes["A/B"]["synced"])

    def test_excluded_below_excluded_parent_is_not_walked(self):
        tree = run.build_tree(self.root, [self.path("A/B")])
        self.assertNotIn("A/B/C", self.rels(tree))

    def test_excluded_deep_path_inserted_under_listed_ancestor(self):
        deep = self.path("A/B/C/D/E/Gone")  # not on disk, deeper than the limit
        tree = run.build_tree(self.root, [deep])
        nodes = {n["rel"]: n for n in tree["nodes"]}
        self.assertIn("A/B/C/D/E/Gone", nodes)
        node = nodes["A/B/C/D/E/Gone"]
        self.assertEqual(node["name"], "Gone")
        self.assertEqual(node["depth"], 4)
        self.assertFalse(node["synced"])
        self.assertFalse(node["hasChildren"])
        self.assertTrue(nodes["A/B/C/D"]["hasChildren"])

    def test_excluded_outside_root_or_root_ignored(self):
        tree = run.build_tree(self.root, ["/etc", self.root])
        self.assertTrue(all(n["synced"] for n in tree["nodes"]))

    def test_truncation(self):
        tree = run.build_tree(self.root, [], max_nodes=3)
        self.assertEqual(len(tree["nodes"]), 3)
        self.assertTrue(tree["truncated"])
        full = run.build_tree(self.root, [], max_nodes=100)
        self.assertFalse(full["truncated"])

    def test_truncation_keeps_every_top_level_folder(self):
        # Breadth-first: the cap drops deep levels, never a later top-level folder.
        tree = run.build_tree(self.root, [], max_nodes=4)
        self.assertEqual(self.rels(tree), ["A", "alpha", "Beta", "Z"])
        self.assertTrue(tree["truncated"])

    def test_excluded_nodes_survive_truncation(self):
        tree = run.build_tree(self.root, [self.path("Z")], max_nodes=0)
        self.assertTrue(tree["truncated"])
        self.assertEqual(self.rels(tree), ["Z"])

    def test_plan_top_most_only_and_invalid_rels_ignored(self):
        nodes = [{"rel": "A", "synced": True}, {"rel": "A/B", "synced": True},
                 {"rel": "AB", "synced": True}, {"rel": "C", "synced": False},
                 {"rel": "D", "synced": True}]
        add, remove = run.plan_changes(nodes, {"C"},
                                       ["A/B", "A", "D", "C", "nope", 7],
                                       ["C", "D", "nope"])
        self.assertEqual(add, ["A", "D"])
        self.assertEqual(remove, ["C"])

    def test_plan_prefix_is_component_boundary(self):
        nodes = [{"rel": "A", "synced": True}, {"rel": "AB", "synced": True}]
        add, remove = run.plan_changes(nodes, set(), ["AB", "A"], [])
        self.assertEqual(add, ["A", "AB"])
        self.assertEqual(remove, [])


if __name__ == "__main__":
    unittest.main()
