"""Tests for bin/run and tree_logic.js (stdlib only; the JS tests need node and skip without it).

Runs the plugin as a subprocess against a temporary Dropbox root and a fake
dropbox-cli. FLEA_DROPBOX_NO_SPAWN=1 keeps GUI/browser/clipboard children off.
"""
import importlib.machinery
import importlib.util
import json
import os
import select
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
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

    def session(self, language="en"):
        """Start bin/run and send hello; `language` None omits the language field."""
        s = Session(self.env)
        self.addCleanup(s.close)
        hello = {"op": "hello", "protocolVersion": 1}
        if language is not None:
            hello["language"] = language
        self.assertEqual(s.send(hello), {"op": "ready", "protocolVersion": 1})
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

    def test_path_outside_root_error_english(self):
        s = self.session("en")
        reply = s.send({"op": "run", "action": "sharelink", "paths": ["/etc"]})
        self.assertEqual(reply, {"op": "error",
                                 "message": "The path is not inside the Dropbox folder."})

    def test_path_outside_root_error_italian(self):
        s = self.session("it")
        reply = s.send({"op": "run", "action": "sharelink", "paths": ["/etc"]})
        self.assertEqual(reply, {"op": "error",
                                 "message": "Il percorso non è nella cartella Dropbox."})

    def test_english_when_hello_has_no_language(self):
        s = self.session(None)
        reply = s.send({"op": "run", "action": "sharelink", "paths": ["/etc"]})
        self.assertEqual(reply["message"], "The path is not inside the Dropbox folder.")

    def test_english_before_any_hello(self):
        s = Session(self.env)
        self.addCleanup(s.close)
        reply = s.send({"op": "run", "action": "sharelink", "paths": ["/etc"]})
        self.assertEqual(reply["message"], "The path is not inside the Dropbox folder.")

    def test_language_is_matched_by_prefix(self):
        s = self.session("it-IT")
        reply = s.send({"op": "run", "action": "sharelink", "paths": ["/etc"]})
        self.assertEqual(reply["message"], "Il percorso non è nella cartella Dropbox.")
        self.assertEqual(s.send({"op": "hello", "protocolVersion": 1, "language": "fr"}),
                         {"op": "ready", "protocolVersion": 1})
        reply = s.send({"op": "run", "action": "sharelink", "paths": ["/etc"]})
        self.assertEqual(reply["message"], "The path is not inside the Dropbox folder.")

    def test_unknown_op_english_and_italian(self):
        s = self.session("en")
        self.assertEqual(s.send({"op": "bogus"}),
                         {"op": "error", "message": "Unsupported operation: bogus"})
        s = self.session("it")
        self.assertEqual(s.send({"op": "bogus"}),
                         {"op": "error", "message": "Operazione non supportata: bogus"})

    def test_manage_without_excluded_done_without_spawn(self):
        s = self.session("en")
        reply = s.send({"op": "run", "action": "manage", "paths": [self.empty]})
        self.assertEqual(reply, {"op": "done", "message": "Window opened."})

    def test_manage_with_excluded_done_without_spawn(self):
        self.mark_excluded(self.excl)
        s = self.session("it")
        reply = s.send({"op": "run", "action": "manage", "paths": [self.docs]})
        self.assertEqual(reply, {"op": "done", "message": "Finestra aperta."})

    def test_manage_uses_folder_field_for_background_menu(self):
        self.mark_excluded(self.excl)
        s = self.session("en")
        reply = s.send({"op": "run", "action": "manage", "paths": [], "folder": self.docs})
        self.assertEqual(reply, {"op": "done", "message": "Window opened."})

    def test_manage_outside_dropbox_done(self):
        s = self.session("en")
        reply = s.send({"op": "run", "action": "manage", "paths": ["/etc"]})
        self.assertEqual(reply, {"op": "done", "message": "Window opened."})

    def test_manage_folder_outside_dropbox_done(self):
        s = self.session("it")
        reply = s.send({"op": "run", "action": "manage", "paths": [], "folder": "/etc"})
        self.assertEqual(reply, {"op": "done", "message": "Finestra aperta."})

    def test_view_outside_dropbox_opens_home_english(self):
        s = self.session("en")
        reply = s.send({"op": "run", "action": "view", "paths": ["/etc"]})
        self.assertEqual(reply, {"op": "done", "message": "Opened on dropbox.com."})

    def test_view_outside_dropbox_opens_home_italian(self):
        s = self.session("it")
        reply = s.send({"op": "run", "action": "view", "paths": ["/etc"]})
        self.assertEqual(reply, {"op": "done", "message": "Aperto su dropbox.com."})

    def test_view_background_inside_opens_folder(self):
        s = self.session("en")
        reply = s.send({"op": "run", "action": "view", "paths": [], "folder": self.docs})
        self.assertEqual(reply["op"], "done", reply)
        self.assertIn("https://www.dropbox.com/home/", reply["message"])
        self.assertTrue(reply["message"].startswith("Opened on dropbox.com: "), reply)

    def test_view_background_inside_opens_folder_italian(self):
        s = self.session("it")
        reply = s.send({"op": "run", "action": "view", "paths": [], "folder": self.docs})
        self.assertEqual(reply["op"], "done", reply)
        self.assertTrue(reply["message"].startswith("Aperto su dropbox.com: "), reply)

    def test_view_background_outside_opens_home(self):
        s = self.session("en")
        reply = s.send({"op": "run", "action": "view", "paths": [], "folder": "/etc"})
        self.assertEqual(reply, {"op": "done", "message": "Opened on dropbox.com."})

    def test_view_several_items_english_error(self):
        s = self.session("en")
        reply = s.send({"op": "run", "action": "view", "paths": [self.docs, self.empty]})
        self.assertEqual(reply, {"op": "error", "message": "Select only one item."})

    def test_sharelink_done(self):
        s = self.session("en")
        reply = s.send({"op": "run", "action": "sharelink", "paths": [self.empty]})
        self.assertEqual(reply["op"], "done", reply)
        self.assertIn("https://www.dropbox.com/scl/fo/fake/", reply["message"])
        self.assertTrue(reply["message"].startswith("Link copied to the clipboard: "), reply)

    def test_sharelink_done_italian(self):
        s = self.session("it")
        reply = s.send({"op": "run", "action": "sharelink", "paths": [self.empty]})
        self.assertEqual(reply["op"], "done", reply)
        self.assertTrue(reply["message"].startswith("Link copiato negli appunti: "), reply)

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


class LanguageTest(unittest.TestCase):
    """In-process checks of the language tables and the dialog arguments."""

    def setUp(self):
        self.saved_lang = run.LANG
        self.addCleanup(setattr, run, "LANG", self.saved_lang)

    def test_every_english_key_has_italian_and_back(self):
        self.assertEqual(set(run.STRINGS["en"]), set(run.STRINGS["it"]))

    def test_no_empty_texts(self):
        for lang in ("en", "it"):
            for key, text in run.STRINGS[lang].items():
                self.assertTrue(text.strip(), (lang, key))

    def test_dialog_strings_follow_language(self):
        run.LANG = "en"
        english = run.dialog_strings()
        self.assertEqual(english["dlg_cancel"], "Cancel")
        self.assertTrue(all(k.startswith("dlg_") for k in english))
        run.LANG = "it"
        italian = run.dialog_strings()
        self.assertEqual(italian["dlg_cancel"], "Annulla")
        self.assertEqual(set(italian), set(english))

    def test_normalize_lang(self):
        self.assertEqual(run.normalize_lang("it"), "it")
        self.assertEqual(run.normalize_lang("it_IT.UTF-8"), "it")
        self.assertEqual(run.normalize_lang("en-US"), "en")
        self.assertEqual(run.normalize_lang("fr"), "en")
        self.assertEqual(run.normalize_lang(None), "en")
        self.assertEqual(run.normalize_lang(7), "en")

    def test_parse_manage_args(self):
        self.assertEqual(run.parse_manage_args(["--manage", "/x"]), ("/x", "en"))
        self.assertEqual(run.parse_manage_args(["--manage", "/x", "--lang", "it"]),
                         ("/x", "it"))
        self.assertEqual(run.parse_manage_args(["--manage", "/x", "--lang", "de"]),
                         ("/x", "en"))
        for bad in (["--manage"], ["--manage", "/x", "--lang"],
                    ["--manage", "/x", "--other", "it"], ["--lang", "it"]):
            with self.assertRaises(ValueError, msg=repr(bad)):
                run.parse_manage_args(bad)

    def test_manage_child_gets_session_language(self):
        tmp = tempfile.mkdtemp(prefix="flea-dropbox-lang-")
        self.addCleanup(shutil.rmtree, tmp, True)
        info = os.path.join(tmp, "info.json")
        with open(info, "w", encoding="utf-8") as fh:
            json.dump({"personal": {"path": tmp}}, fh)
        saved_info = run.INFO_PATH
        run.INFO_PATH = info
        self.addCleanup(setattr, run, "INFO_PATH", saved_info)
        spawned = []
        saved_spawn = run.spawn_detached
        run.spawn_detached = spawned.append
        self.addCleanup(setattr, run, "spawn_detached", saved_spawn)
        run.handle_request({"op": "hello", "protocolVersion": 1, "language": "it"})
        reply = run.handle_request({"op": "run", "action": "manage", "paths": []})
        self.assertEqual(reply, {"op": "done", "message": "Finestra aperta."})
        self.assertEqual(len(spawned), 1, spawned)
        self.assertEqual(spawned[0][-4:-2], ["--manage", tmp])
        self.assertEqual(spawned[0][-2:], ["--lang", "it"])


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
        nodes = [{"rel": "A", "synced": True, "parent": None},
                 {"rel": "A/B", "synced": True, "parent": "A"},
                 {"rel": "AB", "synced": True, "parent": None},
                 {"rel": "C", "synced": False, "parent": None},
                 {"rel": "D", "synced": True, "parent": None}]
        add, remove = run.plan_exclusions(nodes, ["C"], ["A/B", "A", "D", "C", "nope", 7],
                                          ["C", "D", "nope"])
        self.assertEqual(add, ["A", "D"])
        self.assertEqual(remove, ["C"])

    def test_plan_prefix_is_component_boundary(self):
        nodes = [{"rel": "A", "synced": True, "parent": None},
                 {"rel": "AB", "synced": True, "parent": None}]
        add, remove = run.plan_exclusions(nodes, [], ["AB", "A"], [])
        self.assertEqual(add, ["A", "AB"])
        self.assertEqual(remove, [])


# ---- Remote tree (Dropbox's nucleus.sqlite3) ----------------------------------

def varint(n):
    out = bytearray()
    while True:
        byte = n & 0x7F
        n >>= 7
        out.append(byte | (0x80 if n else 0))
        if not n:
            return bytes(out)


def f_bytes(field, data):
    return varint(field << 3 | 2) + varint(len(data)) + data


def f_varint(field, n):
    return varint(field << 3) + varint(n)


def nid(n):
    return n.to_bytes(16, "big")


ROOT_ID = b"\xff" * 16


def record(node, parent, name, kind="dir", sizes=()):
    """A `remote_tree` value: field 1 holds the node (id, parent, name, dir or file)."""
    inner = f_bytes(1, node) + f_bytes(2, parent)
    if name is not None:
        inner += f_bytes(3, name.encode("utf-8"))
    inner += f_bytes(4, b"")
    if kind == "dir":
        inner += f_bytes(6, b"\\n\\x02\\n\\x00")
    else:
        blocks = b"".join(f_bytes(1, f_bytes(1, b"h" * 32) + f_varint(2, s) + f_bytes(3, b""))
                          for s in sizes)
        inner += f_bytes(5, blocks)
    return f_bytes(1, inner)


# Remote namespace of the fixtures.
REMOTE_ROWS = [
    (nid(1), record(nid(1), ROOT_ID, "PERSONAL")),            # local excluded name: Personal
    (nid(2), record(nid(2), nid(1), "Dotfiles")),
    (nid(3), record(nid(3), nid(1), "Docs")),
    (nid(4), record(nid(4), nid(3), "Sub")),
    (nid(5), record(nid(5), ROOT_ID, "Manor")),
    (nid(6), record(nid(6), nid(5), "Taxes")),
    (nid(7), record(nid(7), ROOT_ID, "Photos")),
    (nid(8), record(nid(8), nid(5), "A")),
    (nid(9), record(nid(9), nid(5), "Ghost")),               # remote only, parent synced
    (nid(20), record(nid(20), nid(1), "notes.pdf", "file", (100, 50))),
    (nid(21), record(nid(21), nid(1), "zeta.txt", "file", (10,))),
    (nid(22), record(nid(22), nid(2), "wall.png", "file", (1000,))),
    (nid(23), record(nid(23), nid(2), "empty.bin", "file", ())),
    (nid(30), record(nid(30), nid(1), None)),                # no name: skipped
    (nid(31), b"\\x08\\x01garbage\\xff\\xff\\xff"),             # not a record: skipped
]


def make_nucleus(path, rows=REMOTE_ROWS):
    """A WAL-mode database like Dropbox's, left open with its data only in the -wal file."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute("CREATE TABLE remote_tree (key BLOB PRIMARY KEY, value BLOB)")
    conn.executemany("INSERT INTO remote_tree VALUES (?, ?)", rows)
    conn.commit()
    return conn


class RemoteTest(unittest.TestCase):

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="flea-dropbox-remote-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = os.path.join(self.tmp, "nucleus.sqlite3")

    def test_pb_fields(self):
        buf = f_varint(1, 300) + f_bytes(2, b"abc") + varint(3 << 3 | 5) + b"wxyz"
        self.assertEqual(run.pb_fields(buf),
                         [(1, 0, 300), (2, 2, b"abc"), (3, 5, b"wxyz")])
        self.assertEqual(run.pb_fields(b""), [])

    def test_pb_fields_rejects_malformed(self):
        for bad in (b"\\x80", f_bytes(1, b"abc")[:-1], b"\\x0b", b"\\x00\\x01", varint(1 << 3 | 1) + b"12"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                run.pb_fields(bad)

    def test_record_directory_and_file_size_is_sum_of_blocks(self):
        d = run.parse_remote_record(record(nid(1), ROOT_ID, "Dir"))
        self.assertEqual(d, (nid(1), ROOT_ID, "Dir", True, 0))
        f = run.parse_remote_record(record(nid(2), nid(1), "ü.txt", "file", (4194304, 1000)))
        self.assertEqual(f, (nid(2), nid(1), "ü.txt", False, 4195304))
        empty = run.parse_remote_record(record(nid(3), nid(1), "e", "file", ()))
        self.assertEqual(empty[3:], (False, 0))

    def test_record_without_name_or_garbage_is_skipped(self):
        self.assertIsNone(run.parse_remote_record(record(nid(1), ROOT_ID, None)))
        self.assertIsNone(run.parse_remote_record(b"\\xff\\xff"))
        self.assertIsNone(run.parse_remote_record(f_bytes(2, b"x")))
        self.assertIsNone(run.parse_remote_record(None))

    def test_load_reads_a_copy_and_cleans_up(self):
        conn = make_nucleus(self.db)
        self.addCleanup(conn.close)
        self.assertTrue(os.path.getsize(self.db + "-wal") > 0)  # data only in the WAL
        before = {n: os.stat(os.path.join(self.tmp, n)).st_mtime_ns for n in os.listdir(self.tmp)}
        scratch = os.path.join(self.tmp, "run")
        os.mkdir(scratch)
        saved = os.environ.get("XDG_RUNTIME_DIR")
        os.environ["XDG_RUNTIME_DIR"] = scratch
        self.addCleanup(lambda: os.environ.__setitem__("XDG_RUNTIME_DIR", saved)
                        if saved is not None else os.environ.pop("XDG_RUNTIME_DIR", None))
        remote = run.load_remote_tree(self.db)
        self.assertIsNotNone(remote)
        self.assertEqual([n for n, _i in remote.subdirs(ROOT_ID)],
                         ["Manor", "PERSONAL", "Photos"])
        self.assertEqual(os.listdir(scratch), [])  # temporary copy removed
        after = {n: os.stat(os.path.join(self.tmp, n)).st_mtime_ns for n in before}
        self.assertEqual(before, after)  # the live files were not touched

    def test_load_failures_return_none(self):
        self.assertIsNone(run.load_remote_tree(os.path.join(self.tmp, "missing.sqlite3")))
        with open(self.db, "wb") as fh:
            fh.write(b"not a database at all")
        self.assertIsNone(run.load_remote_tree(self.db))
        other = os.path.join(self.tmp, "other.sqlite3")
        conn = sqlite3.connect(other)
        conn.execute("CREATE TABLE something_else (a)")
        conn.commit()
        conn.close()
        self.assertIsNone(run.load_remote_tree(other))  # schema changed

    def test_find_nucleus_picks_newest(self):
        for name, stamp in (("instance1", 1000), ("instance2", 2000)):
            d = os.path.join(self.tmp, name, "sync")
            os.makedirs(d)
            p = os.path.join(d, "nucleus.sqlite3")
            open(p, "wb").close()
            os.utime(p, (stamp, stamp))
        os.environ["FLEA_DROPBOX_NUCLEUS"] = os.path.join(self.tmp, "instance*", "sync",
                                                           "nucleus.sqlite3")
        self.addCleanup(os.environ.pop, "FLEA_DROPBOX_NUCLEUS", None)
        self.assertEqual(run.find_nucleus(),
                         os.path.join(self.tmp, "instance2", "sync", "nucleus.sqlite3"))
        os.environ["FLEA_DROPBOX_NUCLEUS"] = os.path.join(self.tmp, "none*")
        self.assertIsNone(run.find_nucleus())

    def remote(self):
        return run.RemoteTree.from_rows(REMOTE_ROWS)

    def test_lookup_is_case_insensitive(self):
        remote = self.remote()
        self.assertEqual(remote.find("personal/DOTFILES"), nid(2))
        self.assertEqual(remote.find(""), ROOT_ID)
        self.assertIsNone(remote.find("Personal/Nope"))
        self.assertEqual(remote.files(nid(1)), [("notes.pdf", 150), ("zeta.txt", 10)])

    def test_loose_info(self):
        remote = self.remote()
        info = run.loose_info(remote, nid(1))
        self.assertEqual(info, {"count": 2, "bytes": 160,
                                "files": [{"name": "notes.pdf", "size": 150},
                                          {"name": "zeta.txt", "size": 10}]})
        self.assertEqual(run.loose_info(remote, nid(1), sample=1)["files"],
                         [{"name": "notes.pdf", "size": 150}])
        self.assertEqual(run.loose_info(remote, nid(1), sample=1)["count"], 2)
        self.assertIsNone(run.loose_info(remote, nid(3)))
        self.assertIsNone(run.loose_info(None, nid(1)))
        self.assertIsNone(run.loose_info(remote, None))


class PartialTreeTest(unittest.TestCase):
    """build_tree with a remote tree, plan_exclusions and apply_changes."""

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="flea-dropbox-partial-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = os.path.join(self.tmp, "Dropbox")
        os.makedirs(os.path.join(self.root, "Manor", "A"))
        os.makedirs(os.path.join(self.root, "Local only"))
        self.remote = run.RemoteTree.from_rows(REMOTE_ROWS)
        self.excluded = [os.path.join(self.root, p)
                         for p in ("Personal", "Photos", "Manor/Taxes")]

    def tree(self, **kw):
        return run.build_tree(self.root, self.excluded, remote=self.remote, **kw)

    def nodes(self):
        return {n["rel"]: n for n in self.tree()["nodes"]}

    def test_excluded_folders_get_remote_subfolders(self):
        tree = self.tree()
        self.assertEqual([n["rel"] for n in tree["nodes"]],
                         ["Local only", "Manor", "Manor/A", "Manor/Taxes",
                          "Personal", "Personal/Docs", "Personal/Docs/Sub",
                          "Personal/Dotfiles", "Photos"])
        self.assertFalse(tree["truncated"])
        nodes = self.nodes()
        self.assertTrue(nodes["Personal"]["hasChildren"])
        self.assertFalse(nodes["Personal"]["synced"])
        self.assertFalse(nodes["Personal/Docs/Sub"]["synced"])
        self.assertEqual(nodes["Personal/Docs"]["parent"], "Personal")
        self.assertIsNone(nodes["Personal"]["parent"])
        self.assertEqual(nodes["Personal/Docs/Sub"]["depth"], 2)
        self.assertFalse(nodes["Photos"]["hasChildren"])  # nothing below it remotely

    def test_name_comes_from_the_exclusion_not_the_remote_case(self):
        self.assertEqual(self.nodes()["Personal"]["name"], "Personal")  # remote: PERSONAL

    def test_synced_folder_ignores_remote_only_subfolders(self):
        self.assertNotIn("Manor/Ghost", self.nodes())
        self.assertTrue(self.nodes()["Manor"]["synced"])
        self.assertFalse(self.nodes()["Manor/Taxes"]["synced"])

    def test_loose_files_only_on_excluded_nodes(self):
        nodes = self.nodes()
        loose = nodes["Personal"]["loose"]
        self.assertEqual(loose["count"], 2)
        self.assertEqual(loose["bytes"], 160)
        self.assertEqual(nodes["Personal/Dotfiles"]["loose"]["count"], 2)  # wall.png, empty.bin
        self.assertNotIn("loose", nodes["Personal/Docs"])
        self.assertNotIn("loose", nodes["Manor"])

    def test_without_remote_only_local_and_excluded_nodes(self):
        tree = run.build_tree(self.root, self.excluded)
        self.assertEqual([n["rel"] for n in tree["nodes"]],
                         ["Local only", "Manor", "Manor/A", "Manor/Taxes",
                          "Personal", "Photos"])
        self.assertTrue(all("loose" not in n for n in tree["nodes"]))

    def test_remote_expansion_respects_depth_and_node_caps(self):
        shallow = run.build_tree(self.root, self.excluded, remote=self.remote, max_depth=2)
        self.assertNotIn("Personal/Docs/Sub", [n["rel"] for n in shallow["nodes"]])
        capped = self.tree(max_nodes=3)
        self.assertTrue(capped["truncated"])
        rels = [n["rel"] for n in capped["nodes"]]
        for must in ("Manor/Taxes", "Personal", "Photos"):  # exclusions always listed
            self.assertIn(must, rels)

    # plan_exclusions

    def plan(self, excl, incl, extra=None):
        current = [run.rel_of(p, self.root) for p in self.excluded]
        return run.plan_exclusions(self.tree()["nodes"], current, excl, incl, extra)

    def test_plan_tick_under_excluded_makes_parent_partial(self):
        add, remove = self.plan([], ["Personal", "Personal/Dotfiles"])
        self.assertEqual(remove, ["Personal"])
        self.assertEqual(add, ["Personal/Docs"])

    def test_plan_partial_excludes_unlisted_remote_subfolders(self):
        nodes = [n for n in self.tree()["nodes"] if n["rel"] != "Personal/Docs"
                 and not n["rel"].startswith("Personal/Docs/")]
        current = [run.rel_of(p, self.root) for p in self.excluded]
        extra = lambda rel: [n for n, _i in self.remote.subdirs(self.remote.find(rel))]
        add, remove = run.plan_exclusions(nodes, current, [], ["Personal", "Personal/Dotfiles"],
                                          ["Personal"], extra)
        self.assertEqual(remove, ["Personal"])
        self.assertEqual(add, ["Personal/Docs"])  # not listed, still excluded
        # without a listed excluded child nothing is added: the folder is fully on
        add, remove = run.plan_exclusions(nodes, current, [],
                                          ["Personal", "Personal/Dotfiles"], ["Personal"],
                                          lambda rel: ["Dotfiles"])
        self.assertEqual((add, remove), ([], ["Personal"]))

    def test_plan_full_include_only_removes(self):
        add, remove = self.plan([], ["Personal", "Personal/Docs", "Personal/Docs/Sub",
                                     "Personal/Dotfiles"])
        self.assertEqual((add, remove), ([], ["Personal"]))

    def test_plan_deep_tick_keeps_every_level_partial(self):
        add, remove = self.plan([], ["Personal", "Personal/Docs", "Personal/Docs/Sub"])
        self.assertEqual(remove, ["Personal"])
        self.assertEqual(add, ["Personal/Dotfiles"])

    def test_plan_include_inside_partial_folder(self):
        self.assertEqual(self.plan([], ["Manor/Taxes"]), ([], ["Manor/Taxes"]))

    def test_plan_exclude_inside_synced_folder(self):
        self.assertEqual(self.plan(["Manor/A"], []), (["Manor/A"], []))

    def test_plan_excluding_a_partial_folder_replaces_its_exclusions(self):
        add, remove = self.plan(["Manor", "Manor/A"], [])
        self.assertEqual(add, ["Manor"])
        self.assertEqual(remove, ["Manor/Taxes"])

    def test_plan_ignores_invalid_and_orphan_rels(self):
        self.assertEqual(self.plan(["Photos", "nope", 7], ["Manor", None]), ([], []))
        # a child cannot be on while its parent stays off
        self.assertEqual(self.plan([], ["Personal/Dotfiles"]), ([], []))

    def test_plan_is_case_insensitive_against_the_current_list(self):
        nodes = self.tree()["nodes"]
        self.assertEqual(run.plan_exclusions(nodes, ["personal", "PHOTOS", "manor/taxes"],
                                             [], []), ([], []))

    def test_plan_leaves_exclusions_it_does_not_list_alone(self):
        nodes = self.tree()["nodes"]
        add, remove = run.plan_exclusions(nodes, ["Personal", "Hidden/.cache"], [], [])
        self.assertEqual(remove, [])
        self.assertNotIn("Hidden/.cache", remove)

    def test_describe_changes(self):
        run_lang = run.LANG
        self.addCleanup(setattr, run, "LANG", run_lang)
        run.LANG = "en"
        self.assertEqual(run.describe_changes(["A"], []), "1 folder excluded")
        self.assertEqual(run.describe_changes([], ["A", "B"]), "2 folders re-included")
        self.assertEqual(run.describe_changes(["P/X", "P/Y", "Z"], ["P"]),
                         "1 folder excluded, 1 folder partly synced")
        run.LANG = "it"
        self.assertEqual(run.describe_changes(["P/X"], ["P"]), "1 parzialmente sincronizzata")


FAKE_PY_CLI = """#!/usr/bin/python3
import json, os, sys
st = os.environ["FAKE_STATE"]
d = json.load(open(st)) if os.path.exists(st) else {"excluded": [], "attempts": {}, "log": []}
args = sys.argv[1:]
d["log"].append(args)
if args[:2] == ["exclude", "list"]:
    print("Excluded: ")
    for p in d["excluded"]:
        print(p.lstrip("/"))
elif args[:2] == ["exclude", "remove"]:
    d["excluded"] = [e for e in d["excluded"] if e not in args[2:]]
elif args[:2] == ["exclude", "add"]:
    for p in args[2:]:
        if os.path.dirname(p) in d["excluded"]:
            continue  # parent still excluded: silently does nothing
        n = d["attempts"].get(p, 0) + 1
        d["attempts"][p] = n
        if n >= int(os.environ.get("FAKE_APPEARS", "2")):  # the folder shows up locally later
            d["excluded"].append(p)
            print("Excluded:")
            print(p)
json.dump(d, open(st, "w"))
"""


class ApplyTest(unittest.TestCase):

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="flea-dropbox-apply-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cli = os.path.join(self.tmp, "dropbox-cli")
        with open(self.cli, "w", encoding="utf-8") as fh:
            fh.write(FAKE_PY_CLI)
        os.chmod(self.cli, 0o755)
        self.state = os.path.join(self.tmp, "state.json")
        os.environ["FAKE_STATE"] = self.state
        self.addCleanup(os.environ.pop, "FAKE_STATE", None)
        self.addCleanup(os.environ.pop, "FAKE_APPEARS", None)
        for name, value in (("DBX_CLI", self.cli), ("LANG", "en")):
            self.addCleanup(setattr, run, name, getattr(run, name))
            setattr(run, name, value)
        self.notes = []
        self.addCleanup(setattr, run, "notify", run.notify)
        run.notify = lambda title, body: self.notes.append(body)
        self.sleeps = []
        self.clock_now = 0.0

    def set_excluded(self, rels):
        with open(self.state, "w", encoding="utf-8") as fh:
            json.dump({"excluded": ["/dbx/" + r for r in rels], "attempts": {}, "log": []}, fh)

    def data(self):
        with open(self.state, encoding="utf-8") as fh:
            return json.load(fh)

    def clock(self):
        self.clock_now += 1.0
        return self.clock_now

    def apply(self, to_add, to_remove, **kw):
        return run.apply_changes("/dbx", to_add, to_remove, sleep=self.sleeps.append,
                                 clock=self.clock, **kw)

    def test_partial_include_removes_first_then_retries_adds(self):
        self.set_excluded(["Personal", "Photos"])
        rc = self.apply(["Personal/Docs", "Personal/Pepa"], ["Personal"])
        self.assertEqual(rc, 0)
        data = self.data()
        self.assertEqual(sorted(data["excluded"]),
                         ["/dbx/Personal/Docs", "/dbx/Personal/Pepa", "/dbx/Photos"])
        verbs = [a[1] for a in data["log"] if a[:1] == ["exclude"]]
        self.assertEqual(verbs[0], "remove")
        self.assertIn("add", verbs)
        self.assertEqual(data["log"][0], ["exclude", "remove", "/dbx/Personal"])
        self.assertGreaterEqual(len(self.sleeps), 1)  # first add did nothing: retried
        self.assertEqual(len(self.notes), 1)
        self.assertTrue(self.notes[0].startswith("Sync updated"))

    def test_simple_exclusion_is_one_add_call(self):
        self.set_excluded([])
        os.environ["FAKE_APPEARS"] = "1"
        self.assertEqual(self.apply(["Docs"], []), 0)
        adds = [a for a in self.data()["log"] if a[:2] == ["exclude", "add"]]
        self.assertEqual(adds, [["exclude", "add", "/dbx/Docs"]])
        self.assertEqual(self.sleeps, [])

    def test_gives_up_after_the_budget_and_says_which(self):
        self.set_excluded(["Personal"])
        os.environ["FAKE_APPEARS"] = "999"
        rc = self.apply(["Personal/Docs"], ["Personal"], budget=5.0)
        self.assertEqual(rc, 1)
        self.assertEqual(len(self.notes), 1)
        self.assertIn("Personal/Docs", self.notes[0])
        self.assertTrue(self.notes[0].startswith("Could not exclude in time"))
        # rollback: the re-included parent is excluded again
        self.assertEqual(self.data()["log"][-1], ["exclude", "add", "/dbx/Personal"])

    def test_nothing_to_do(self):
        self.assertEqual(self.apply([], []), 0)
        self.assertEqual(self.notes, ["No change to sync settings."])
        self.assertFalse(os.path.exists(self.state))


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TreeLogicTest(unittest.TestCase):
    """tree_logic.js (the tick rules of picker.qml) run under node."""

    SCRIPT = r"""
const L = require(process.argv[2]);
const n = (rel, synced, parent, loose) => ({rel, synced, parent, loose});
const nodes = [
  n("M", true, null), n("M/A", true, "M"), n("M/T", false, "M"),
  n("P", false, null, {count: 2, bytes: 160, files: [{name: "x", size: 150}]}),
  n("P/D", false, "P", {count: 1, bytes: 5, files: [{name: "y", size: 5}]}), n("P/D/S", false, "P/D"),
  n("P/O", false, "P"),
  n("X", false, null),
];
const ix = L.buildIndex(nodes);
function run(clicks) {
  let own = L.initialOwn(nodes), auto = {};
  for (const c of clicks) ({own, auto} = L.toggle(ix, own, auto, c));
  const p = L.plan(ix, nodes, own, auto);
  return {state: p.state, excl: p.excl, incl: p.incl, exclTop: p.exclTop, inclTop: p.inclTop,
          partial: p.partial, opened: p.opened, warn: p.warn.map(w => w.rel)};
}
const scenarios = JSON.parse(process.argv[3]);
console.log(JSON.stringify(scenarios.map(run)));
"""

    def run_clicks(self, *scenarios):
        script = os.path.join(tempfile.mkdtemp(prefix="flea-dropbox-js-"), "t.js")
        self.addCleanup(shutil.rmtree, os.path.dirname(script), True)
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(self.SCRIPT)
        proc = subprocess.run(["node", script, os.path.join(ROOT, "tree_logic.js"),
                               json.dumps(list(scenarios))], capture_output=True, text=True,
                              timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_initial_states_and_no_changes(self):
        (r,) = self.run_clicks([])
        self.assertEqual(r["state"]["M"], "partial")
        self.assertEqual(r["state"]["M/A"], "on")
        self.assertEqual(r["state"]["P"], "off")
        self.assertEqual((r["excl"], r["incl"], r["warn"]), ([], [], []))

    def test_tick_under_excluded_makes_ancestors_partial(self):
        (r,) = self.run_clicks(["P/O"])
        self.assertEqual((r["state"]["P"], r["state"]["P/O"], r["state"]["P/D"]),
                         ("partial", "on", "off"))
        self.assertEqual(r["incl"], ["P", "P/O"])
        self.assertEqual((r["inclTop"], r["exclTop"]), (1, 0))
        self.assertEqual(r["partial"], ["P"])
        self.assertEqual(r["warn"], ["P"])

    def test_deep_tick_opens_every_level(self):
        (r,) = self.run_clicks(["P/D/S"])
        # P/D has a single subfolder, now on: it shows as fully on, but it was opened by
        # the tick below it, so its loose files are announced too
        self.assertEqual((r["state"]["P"], r["state"]["P/D"], r["state"]["P/D/S"], r["state"]["P/O"]),
                         ("partial", "on", "on", "off"))
        self.assertEqual(r["partial"], ["P"])
        self.assertEqual(r["opened"], ["P", "P/D"])
        self.assertEqual(r["warn"], ["P", "P/D"])
        self.assertEqual(r["inclTop"], 1)

    def test_unticking_the_last_one_reverts_the_auto_folders(self):
        (r,) = self.run_clicks(["P/D/S", "P/D/S"])
        self.assertEqual(r["state"]["P"], "off")
        self.assertEqual(r["state"]["P/D"], "off")
        self.assertEqual((r["incl"], r["excl"], r["partial"], r["warn"]), ([], [], [], []))

    def test_unticking_one_of_two_keeps_the_partial_parent(self):
        (r,) = self.run_clicks(["P/O", "P/D/S", "P/O"])
        self.assertEqual((r["state"]["P"], r["state"]["P/D"], r["state"]["P/O"]),
                         ("partial", "on", "off"))
        (r2,) = self.run_clicks(["P/O", "P/D/S", "P/D/S"])
        self.assertEqual((r2["state"]["P"], r2["state"]["P/D"], r2["state"]["P/O"]),
                         ("partial", "off", "on"))

    def test_click_on_partial_includes_everything(self):
        (r,) = self.run_clicks(["P/O", "P"])
        self.assertEqual({r["state"][k] for k in ("P", "P/D", "P/D/S", "P/O")}, {"on"})
        self.assertEqual((r["inclTop"], r["partial"], r["warn"]), (1, [], []))
        # an unticked descendant of a ticked folder does not revert anything
        (r2,) = self.run_clicks(["P/O", "P", "P/O"])
        self.assertEqual(r2["state"]["P"], "partial")

    def test_click_on_excluded_folder_includes_it_fully(self):
        (r,) = self.run_clicks(["P"])
        self.assertEqual({r["state"][k] for k in ("P", "P/D", "P/D/S", "P/O")}, {"on"})
        self.assertEqual((r["inclTop"], r["incl"].__len__(), r["warn"]), (1, 4, []))
        # ticking the partial parent does not leave an auto mark behind
        (r2,) = self.run_clicks(["P/D/S", "P", "P"])
        self.assertEqual(r2["state"]["P"], "off")

    def test_include_inside_a_partial_synced_folder(self):
        (r,) = self.run_clicks(["M/T"])
        self.assertEqual((r["state"]["M"], r["state"]["M/T"]), ("on", "on"))
        self.assertEqual((r["incl"], r["inclTop"], r["partial"]), (["M/T"], 1, []))

    def test_untick_inside_synced_folder_and_restore(self):
        (r,) = self.run_clicks(["M/A"])
        self.assertEqual((r["excl"], r["exclTop"], r["state"]["M"]), (["M/A"], 1, "partial"))
        (r2,) = self.run_clicks(["M"])  # a partial folder first becomes fully synced...
        self.assertEqual((r2["state"]["M"], r2["state"]["M/T"], r2["incl"]), ("on", "on", ["M/T"]))
        (r3,) = self.run_clicks(["M", "M"])  # ...and only the next click excludes it
        self.assertEqual(r3["excl"], ["M", "M/A"])
        self.assertEqual(r3["exclTop"], 1)
        (r4,) = self.run_clicks(["M", "M", "M"])  # ticked again: back to fully synced
        self.assertEqual((r4["state"]["M"], r4["excl"]), ("on", []))

    def test_tick_below_an_unchecked_synced_folder(self):
        (r,) = self.run_clicks(["M", "M", "M/T"])
        self.assertEqual((r["state"]["M"], r["state"]["M/A"], r["state"]["M/T"]),
                         ("partial", "off", "on"))
        self.assertEqual(r["excl"], ["M/A"])

    def test_no_warning_without_loose_files_or_when_fully_included(self):
        (r,) = self.run_clicks(["X"])
        self.assertEqual((r["incl"], r["warn"]), (["X"], []))
        (r2,) = self.run_clicks(["P", "P/O"])  # fully included, then one unticked: partial again
        self.assertEqual((r2["state"]["P"], r2["warn"]), ("partial", ["P"]))


if __name__ == "__main__":
    unittest.main()
