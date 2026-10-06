"""The store's state machine, with network and keyring replaced by fakes."""

import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from claude_usage import api, http, oauth
from claude_usage.credentials import Credentials, CredentialStore
from claude_usage.preferences import Preferences
from claude_usage.snapshot import UsageSnapshot
from claude_usage.store import FAILED, LOADING, READY, SIGNED_OUT, UsageStore
from tests.test_credentials import Memory

SNAPSHOT = UsageSnapshot.from_payload({"five_hour": {"utilization": 42}})


class StoreCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        env = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": self._tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.backend = Memory()

    def make(self, credentials=None) -> UsageStore:
        if credentials:
            self.backend.value = credentials.to_json()
        prefs = Preferences(Path(self._tmp.name) / "s.json", Path(self._tmp.name) / "a.desktop")
        # post and spawn default to synchronous in tests via explicit lambdas
        return UsageStore(
            prefs,
            CredentialStore([self.backend]),
            post=lambda fn: fn(),
            spawn=lambda fn: fn(),
        )


class Startup(StoreCase):
    def test_starts_signed_out_without_credentials(self):
        store = self.make()
        self.assertEqual(store.phase, SIGNED_OUT)
        self.assertFalse(store.is_signed_in)

    def test_starts_loading_with_stored_credentials(self):
        store = self.make(Credentials("at", "rt", time.time() + 3600))
        self.assertEqual(store.phase, LOADING)
        self.assertTrue(store.is_signed_in)

    def test_refresh_while_signed_out_does_nothing(self):
        with mock.patch.object(api, "fetch") as fetch:
            self.make().refresh()
        fetch.assert_not_called()


class Refreshing(StoreCase):
    def test_successful_fetch_becomes_ready(self):
        store = self.make(Credentials("at", "rt", time.time() + 3600))
        changes = []
        store.subscribe(lambda: changes.append(store.phase))

        with mock.patch.object(api, "fetch", return_value=SNAPSHOT) as fetch:
            store.refresh()

        fetch.assert_called_once_with("at")
        self.assertEqual(store.phase, READY)
        self.assertEqual(store.snapshot, SNAPSHOT)
        self.assertIsNotNone(store.last_updated)
        self.assertIn(READY, changes)

    def test_errors_become_failed_with_a_readable_message(self):
        store = self.make(Credentials("at", "rt", time.time() + 3600))

        for error, expected in [
            (api.RateLimited(), "rate-limiting"),
            (api.RequestFailed(503), "HTTP 503"),
            (http.NetworkError("dns"), "Can't reach Anthropic"),
        ]:
            with self.subTest(error=error), mock.patch.object(api, "fetch", side_effect=error):
                store.refresh()
                self.assertEqual(store.phase, FAILED)
                self.assertIn(expected, store.error)

    def test_a_failure_keeps_the_last_good_snapshot(self):
        store = self.make(Credentials("at", "rt", time.time() + 3600))
        with mock.patch.object(api, "fetch", return_value=SNAPSHOT):
            store.refresh()
        with mock.patch.object(api, "fetch", side_effect=http.NetworkError("offline")):
            store.refresh()

        self.assertEqual(store.phase, FAILED)
        self.assertEqual(store.snapshot, SNAPSHOT)

    def test_an_expired_token_is_refreshed_first(self):
        store = self.make(Credentials("old", "rt", time.time() - 10))
        fresh = Credentials("new", "rt2", time.time() + 3600)

        with (
            mock.patch.object(oauth, "refresh", return_value=fresh) as refresh,
            mock.patch.object(api, "fetch", return_value=SNAPSHOT) as fetch,
        ):
            store.refresh()

        refresh.assert_called_once()
        fetch.assert_called_once_with("new")
        self.assertEqual(self.backend.value, fresh.to_json())

    def test_401_triggers_one_refresh_and_retry(self):
        store = self.make(Credentials("old", "rt", time.time() + 3600))
        fresh = Credentials("new", "rt2", time.time() + 3600)

        with (
            mock.patch.object(oauth, "refresh", return_value=fresh),
            mock.patch.object(api, "fetch", side_effect=[api.Unauthorized(), SNAPSHOT]) as fetch,
        ):
            store.refresh()

        self.assertEqual(store.phase, READY)
        self.assertEqual([c.args[0] for c in fetch.call_args_list], ["old", "new"])

    def test_401_that_cannot_be_recovered_signs_out(self):
        store = self.make(Credentials("old", "rt", time.time() + 3600))

        with (
            mock.patch.object(oauth, "refresh", side_effect=oauth.AuthError("revoked")),
            mock.patch.object(api, "fetch", side_effect=api.Unauthorized()),
        ):
            store.refresh()

        self.assertEqual(store.phase, SIGNED_OUT)
        self.assertFalse(store.is_signed_in)
        self.assertIsNone(self.backend.value)

    def test_401_without_a_refresh_token_signs_out(self):
        store = self.make(Credentials("old", None, None))

        with mock.patch.object(api, "fetch", side_effect=api.Unauthorized()):
            store.refresh()

        self.assertEqual(store.phase, SIGNED_OUT)

    def test_unexpected_exceptions_do_not_wedge_the_store(self):
        store = self.make(Credentials("at", "rt", time.time() + 3600))

        with (
            mock.patch.object(api, "fetch", side_effect=RuntimeError("bug")),
            self.assertLogs("claude_usage.store", "ERROR"),
        ):
            store.refresh()
        self.assertEqual(store.phase, FAILED)

        with mock.patch.object(api, "fetch", return_value=SNAPSHOT):
            store.refresh()  # a later refresh must still run
        self.assertEqual(store.phase, READY)

    def test_overlapping_refreshes_are_coalesced(self):
        store = self.make(Credentials("at", "rt", time.time() + 3600))
        pending = []
        store._spawn = pending.append

        store.refresh()
        store.refresh()
        store.refresh()

        self.assertEqual(len(pending), 1)

    def test_refresh_if_stale_skips_recent_data(self):
        store = self.make(Credentials("at", "rt", time.time() + 3600))
        store.last_updated = datetime.now(timezone.utc) - timedelta(seconds=3)

        with mock.patch.object(api, "fetch", return_value=SNAPSHOT) as fetch:
            store.refresh_if_stale(max_age=15)
        fetch.assert_not_called()

        store.last_updated = datetime.now(timezone.utc) - timedelta(seconds=60)
        with mock.patch.object(api, "fetch", return_value=SNAPSHOT) as fetch:
            store.refresh_if_stale(max_age=15)
        fetch.assert_called_once()

    def test_a_stale_result_from_a_previous_login_is_dropped(self):
        store = self.make(Credentials("at", "rt", time.time() + 3600))
        queued = []
        store._post = queued.append  # hold results back, as a busy main loop would

        with mock.patch.object(api, "fetch", return_value=SNAPSHOT):
            store.refresh()
        store.sign_out()
        for fn in queued:
            fn()

        self.assertEqual(store.phase, SIGNED_OUT)
        self.assertIsNone(store.snapshot)


class SigningIn(StoreCase):
    def test_pasted_code_signs_in_and_fetches(self):
        store = self.make()
        session = store.begin_manual_sign_in()
        credentials = Credentials("at", "rt", time.time() + 3600)

        with (
            mock.patch.object(oauth, "sign_in_with_pasted_code", return_value=credentials),
            mock.patch.object(api, "fetch", return_value=SNAPSHOT),
        ):
            store.complete_manual_sign_in("code#state", session)

        self.assertTrue(store.is_signed_in)
        self.assertFalse(store.is_signing_in)
        self.assertEqual(store.phase, READY)
        self.assertEqual(self.backend.value, credentials.to_json())

    def test_a_bad_code_reports_the_error_and_stays_signed_out(self):
        store = self.make()

        with mock.patch.object(oauth, "sign_in_with_pasted_code", side_effect=oauth.AuthError("nope")):
            store.complete_manual_sign_in("x", store.begin_manual_sign_in())

        self.assertEqual(store.sign_in_error, "nope")
        self.assertFalse(store.is_signing_in)
        self.assertFalse(store.is_signed_in)

    def test_browser_sign_in_opens_the_url_and_completes(self):
        store = self.make()
        opened = []
        attempt = mock.Mock()
        attempt.session = oauth.make_session(manual=False)
        attempt.run.return_value = Credentials("at", "rt", time.time() + 3600)

        with (
            mock.patch.object(oauth, "BrowserSignIn", return_value=attempt),
            mock.patch.object(api, "fetch", return_value=SNAPSHOT),
        ):
            store.sign_in_with_browser(opened.append)

        self.assertEqual(opened, [attempt.session.url])
        self.assertEqual(store.phase, READY)

    def test_cancelling_leaves_no_error(self):
        store = self.make()
        attempt = mock.Mock()
        attempt.session = oauth.make_session(manual=False)
        attempt.run.side_effect = oauth.SignInCancelled()

        with mock.patch.object(oauth, "BrowserSignIn", return_value=attempt):
            store.sign_in_with_browser(lambda url: None)

        self.assertFalse(store.is_signing_in)
        self.assertIsNone(store.sign_in_error)

    def test_port_in_use_surfaces_as_an_error(self):
        store = self.make()

        with mock.patch.object(oauth, "BrowserSignIn", side_effect=oauth.AuthError("Port 54545 is in use.")):
            store.sign_in_with_browser(lambda url: self.fail("browser must not open"))

        self.assertIn("in use", store.sign_in_error)
        self.assertFalse(store.is_signing_in)

    def test_importing_the_claude_code_login(self):
        store = self.make()
        (Path(self._tmp.name) / ".credentials.json").write_text(
            json.dumps(
                {
                    "claudeAiOauth": {
                        "accessToken": "cc",
                        "refreshToken": "rt",
                        "expiresAt": (time.time() + 3600) * 1000,
                    }
                }
            )
        )

        with mock.patch.object(api, "fetch", return_value=SNAPSHOT) as fetch:
            self.assertTrue(store.import_claude_code_login())

        fetch.assert_called_once_with("cc")
        self.assertEqual(store.phase, READY)

    def test_importing_without_a_login_reports_it(self):
        store = self.make()

        self.assertFalse(store.import_claude_code_login())
        self.assertIn("No Claude Code login", store.sign_in_error)

    def test_sign_out_forgets_everything(self):
        store = self.make(Credentials("at", "rt", time.time() + 3600))
        with mock.patch.object(api, "fetch", return_value=SNAPSHOT):
            store.refresh()

        store.sign_out()

        self.assertEqual(store.phase, SIGNED_OUT)
        self.assertIsNone(store.snapshot)
        self.assertIsNone(store.last_updated)
        self.assertIsNone(self.backend.value)


class ContextReading(StoreCase):
    def test_context_is_independent_of_being_signed_in(self):
        store = self.make()
        project = Path(self._tmp.name) / "projects" / "-x-demo"
        project.mkdir(parents=True)
        (project / "s.jsonl").write_text(
            json.dumps(
                {"type": "assistant", "cwd": "/x/demo", "message": {"usage": {"input_tokens": 500_000}}}
            )
            + "\n"
        )

        store.refresh_context()

        self.assertEqual(store.context_usage.percent, 50)
        self.assertEqual(store.context_usage.project, "demo")


if __name__ == "__main__":
    unittest.main()
