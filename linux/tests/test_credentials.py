"""Credential storage, the file fallback, and importing a Claude Code login."""

import json
import os
import stat
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from claude_usage import credentials
from claude_usage.credentials import Credentials, CredentialStore, FileBackend


class Memory:
    """In-memory stand-in for a keyring backend."""

    def __init__(self, works=True):
        self.value, self.works = None, works

    def read(self):
        return self.value

    def write(self, value):
        if self.works:
            self.value = value
        return self.works

    def delete(self):
        self.value = None


class Serialization(unittest.TestCase):
    def test_round_trip(self):
        original = Credentials("at", "rt", 1_800_000_000.5, ["a", "b"])
        self.assertEqual(Credentials.from_json(original.to_json()), original)

    def test_rejects_garbage(self):
        for text in ("", "nope", "[]", '{"accessToken": ""}', '{"accessToken": 5}', "{}"):
            with self.subTest(text=text):
                self.assertIsNone(Credentials.from_json(text))

    def test_expiry_has_a_minute_of_margin(self):
        self.assertTrue(Credentials("a", expires_at=time.time() + 30).is_expired)
        self.assertFalse(Credentials("a", expires_at=time.time() + 600).is_expired)
        self.assertFalse(Credentials("a", expires_at=None).is_expired)


class Store(unittest.TestCase):
    def test_saves_to_the_first_working_backend_and_clears_the_rest(self):
        keyring, file = Memory(), Memory()
        file.value = "stale"
        store = CredentialStore([keyring, file])

        store.save(Credentials("at", "rt"))

        self.assertEqual(store.load().access_token, "at")
        self.assertIsNone(file.value)

    def test_falls_back_when_the_keyring_cannot_write(self):
        keyring, file = Memory(works=False), Memory()
        store = CredentialStore([keyring, file])

        store.save(Credentials("at"))

        self.assertIsNone(keyring.value)
        self.assertEqual(store.load().access_token, "at")

    def test_clear_removes_every_copy(self):
        a, b = Memory(), Memory()
        a.value = b.value = Credentials("at").to_json()
        store = CredentialStore([a, b])

        store.clear()

        self.assertIsNone(store.load())

    def test_unreadable_entries_are_skipped(self):
        a, b = Memory(), Memory()
        a.value = "corrupt"
        b.value = Credentials("good").to_json()

        self.assertEqual(CredentialStore([a, b]).load().access_token, "good")


class Files(unittest.TestCase):
    def test_file_backend_is_private_to_the_user(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = FileBackend(Path(directory) / "nested" / "credentials.json")

            self.assertTrue(backend.write("secret"))

            self.assertEqual(backend.read(), "secret")
            self.assertEqual(stat.S_IMODE(backend.path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(backend.path.parent.stat().st_mode), 0o700)

            backend.delete()
            self.assertIsNone(backend.read())

    def test_file_backend_overwrites_in_place(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = FileBackend(Path(directory) / "c.json")
            backend.write("one")
            backend.write("two")

            self.assertEqual(backend.read(), "two")
            self.assertEqual(os.listdir(directory), ["c.json"])


class ClaudeCodeImport(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": self._tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, data):
        (Path(self._tmp.name) / ".credentials.json").write_text(json.dumps(data))

    def test_missing_file(self):
        self.assertFalse(credentials.claude_code_login_available())
        self.assertIsNone(credentials.import_from_claude_code())

    def test_imports_and_converts_millisecond_expiry(self):
        self.write(
            {
                "claudeAiOauth": {
                    "accessToken": "at",
                    "refreshToken": "rt",
                    "expiresAt": 1_800_000_000_000,
                    "scopes": ["user:inference"],
                }
            }
        )

        imported = credentials.import_from_claude_code()

        self.assertTrue(credentials.claude_code_login_available())
        self.assertEqual(imported, Credentials("at", "rt", 1_800_000_000.0, ["user:inference"]))

    def test_rejects_unexpected_shapes(self):
        for data in ({}, {"claudeAiOauth": {}}, {"claudeAiOauth": {"accessToken": ""}}, []):
            with self.subTest(data=data):
                self.write(data)
                self.assertIsNone(credentials.import_from_claude_code())


if __name__ == "__main__":
    unittest.main()
