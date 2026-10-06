"""PKCE, the token endpoint, and the loopback redirect listener."""

import json
import socket
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from claude_usage import http, oauth
from claude_usage.loopback import LoopbackCancelled, LoopbackError, LoopbackServer, LoopbackTimeout


class Pkce(unittest.TestCase):
    def test_challenge_matches_the_rfc7636_example(self):
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        self.assertEqual(oauth.challenge_for(verifier), "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")

    def test_session_url_carries_the_pkce_parameters(self):
        session = oauth.make_session(manual=False)
        url = urlsplit(session.url)
        query = {k: v[0] for k, v in parse_qs(url.query).items()}

        self.assertEqual(url.netloc, "claude.ai")
        self.assertEqual(query["client_id"], oauth.CLIENT_ID)
        self.assertEqual(query["code_challenge"], oauth.challenge_for(session.verifier))
        self.assertEqual(query["code_challenge_method"], "S256")
        self.assertEqual(query["state"], session.state)
        self.assertEqual(query["redirect_uri"], oauth.LOOPBACK_REDIRECT)

    def test_manual_sessions_use_the_hosted_callback(self):
        self.assertEqual(oauth.make_session(manual=True).redirect_uri, oauth.MANUAL_REDIRECT)

    def test_sessions_are_unique(self):
        a, b = oauth.make_session(False), oauth.make_session(False)
        self.assertNotEqual(a.verifier, b.verifier)
        self.assertNotEqual(a.state, b.state)


def token_response(**fields):
    body = {
        "access_token": "at",
        "refresh_token": "rt",
        "expires_in": 3600,
        "scope": "user:profile user:inference",
    }
    body.update(fields)
    return http.Response(200, json.dumps(body).encode())


class TokenEndpoint(unittest.TestCase):
    def test_pasted_code_exchanges_for_credentials(self):
        session = oauth.make_session(manual=True)
        with mock.patch.object(http, "request", return_value=token_response()) as request:
            credentials = oauth.sign_in_with_pasted_code(f"  abc#{session.state}\n", session)

        sent = json.loads(request.call_args.kwargs["body"])
        self.assertEqual(sent["code"], "abc")
        self.assertEqual(sent["code_verifier"], session.verifier)
        self.assertEqual(sent["redirect_uri"], oauth.MANUAL_REDIRECT)
        self.assertEqual(credentials.access_token, "at")
        self.assertEqual(credentials.scopes, ["user:profile", "user:inference"])
        self.assertAlmostEqual(credentials.expires_at, time.time() + 3600, delta=5)

    def test_pasted_code_with_the_wrong_state_is_rejected(self):
        session = oauth.make_session(manual=True)
        with mock.patch.object(http, "request") as request, self.assertRaises(oauth.AuthError):
            oauth.sign_in_with_pasted_code("abc#someone-elses-state", session)
        request.assert_not_called()

    def test_pasted_code_without_state_is_accepted(self):
        session = oauth.make_session(manual=True)
        with mock.patch.object(http, "request", return_value=token_response()):
            self.assertEqual(oauth.sign_in_with_pasted_code("abc", session).access_token, "at")

    def test_empty_code_is_rejected(self):
        with self.assertRaises(oauth.AuthError):
            oauth.sign_in_with_pasted_code("   ", oauth.make_session(manual=True))

    def test_falls_back_to_the_second_token_endpoint(self):
        failure = http.Response(500, b'{"error": "boom"}')
        with mock.patch.object(http, "request", side_effect=[failure, token_response()]) as request:
            oauth.refresh(oauth.Credentials("old", "rt"))

        urls = [call.args[0] for call in request.call_args_list]
        self.assertEqual(urls, oauth.TOKEN_URLS)

    def test_surfaces_the_servers_error_description(self):
        failure = http.Response(
            400, b'{"error": "invalid_grant", "error_description": "Refresh token expired"}'
        )
        with (
            mock.patch.object(http, "request", return_value=failure),
            self.assertRaisesRegex(oauth.AuthError, "Refresh token expired"),
        ):
            oauth.refresh(oauth.Credentials("old", "rt"))

    def test_network_failure_is_an_auth_error(self):
        with (
            mock.patch.object(http, "request", side_effect=http.NetworkError("offline")),
            self.assertRaisesRegex(oauth.AuthError, "offline"),
        ):
            oauth.refresh(oauth.Credentials("old", "rt"))

    def test_refresh_keeps_the_old_refresh_token_when_none_is_returned(self):
        with mock.patch.object(http, "request", return_value=token_response(refresh_token=None)):
            refreshed = oauth.refresh(oauth.Credentials("old", "keep-me"))

        self.assertEqual(refreshed.refresh_token, "keep-me")

    def test_refresh_requires_a_refresh_token(self):
        with self.assertRaises(oauth.AuthError):
            oauth.refresh(oauth.Credentials("old", None))


class BrowserFlow(unittest.TestCase):
    """The whole browser sign-in: a real loopback socket, a faked token endpoint."""

    def run_flow(self, query_for):
        with mock.patch.object(oauth, "LOOPBACK_PORT", 0):
            attempt = oauth.BrowserSignIn()
        result = {}

        def work():
            try:
                result["credentials"] = attempt.run()
            except oauth.AuthError as error:
                result["error"] = error

        thread = threading.Thread(target=work)
        thread.start()
        port = attempt._server.port
        get(port, "/callback?" + query_for(attempt.session))
        thread.join(5)
        return result

    def test_valid_callback_yields_credentials(self):
        with mock.patch.object(http, "request", return_value=token_response()) as request:
            result = self.run_flow(lambda session: f"code=abc&state={session.state}")

        self.assertEqual(result["credentials"].access_token, "at")
        self.assertEqual(json.loads(request.call_args.kwargs["body"])["code"], "abc")

    def test_callback_with_the_wrong_state_is_rejected(self):
        with mock.patch.object(http, "request") as request:
            result = self.run_flow(lambda session: "code=abc&state=forged")

        self.assertIn("did not match", str(result["error"]))
        request.assert_not_called()

    def test_denied_authorization_is_reported(self):
        result = self.run_flow(lambda session: "error=access_denied")

        self.assertIn("did not return an authorization code", str(result["error"]))

    def test_cancelling_raises_sign_in_cancelled(self):
        with mock.patch.object(oauth, "LOOPBACK_PORT", 0):
            attempt = oauth.BrowserSignIn()
        errors = []

        def work():
            try:
                attempt.run()
            except oauth.SignInCancelled as error:
                errors.append(error)

        thread = threading.Thread(target=work)
        thread.start()
        attempt.cancel()
        thread.join(5)

        self.assertEqual(len(errors), 1)

    def test_a_busy_port_is_an_auth_error(self):
        blocker = LoopbackServer(0)
        self.addCleanup(blocker._server.server_close)

        with (
            mock.patch.object(oauth, "LOOPBACK_PORT", blocker.port),
            self.assertRaisesRegex(oauth.AuthError, "in use"),
        ):
            oauth.BrowserSignIn()


def get(port: int, path: str) -> int:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


class Loopback(unittest.TestCase):
    def serve(self, **kwargs):
        server = LoopbackServer(0)
        result = {}

        def wait():
            try:
                result["query"] = server.wait_for_callback(**kwargs)
            except LoopbackError as error:
                result["error"] = error

        thread = threading.Thread(target=wait)
        thread.start()
        self.addCleanup(thread.join, 5)
        return server, result, thread

    def test_delivers_the_callback_query(self):
        server, result, thread = self.serve(timeout=5)

        self.assertEqual(get(server.port, "/callback?code=abc&state=xyz"), 200)
        thread.join(5)

        self.assertEqual(result["query"], {"code": "abc", "state": "xyz"})

    def test_a_callback_without_a_code_reports_failure_but_still_finishes(self):
        server, result, thread = self.serve(timeout=5)

        self.assertEqual(get(server.port, "/callback?error=access_denied"), 400)
        thread.join(5)

        self.assertEqual(result["query"], {"error": "access_denied"})

    def test_stray_requests_do_not_end_the_wait(self):
        server, result, thread = self.serve(timeout=5)

        self.assertEqual(get(server.port, "/favicon.ico"), 404)
        self.assertNotIn("query", result)
        self.assertEqual(get(server.port, "/callback?code=abc"), 200)
        thread.join(5)

        self.assertEqual(result["query"]["code"], "abc")

    def test_request_split_across_tcp_segments_is_parsed(self):
        server, result, thread = self.serve(timeout=5)

        with socket.create_connection(("127.0.0.1", server.port), timeout=5) as client:
            for chunk in (
                b"GET /call",
                b"back?code=ab",
                b"c&state=s HTTP/1.1\r\n",
                b"Host: localhost\r\n\r\n",
            ):
                client.sendall(chunk)
                time.sleep(0.05)
            client.recv(4096)
        thread.join(5)

        self.assertEqual(result["query"], {"code": "abc", "state": "s"})

    def test_binds_to_loopback_only(self):
        server = LoopbackServer(0)
        self.addCleanup(server._server.server_close)

        self.assertEqual(server._server.server_address[0], "127.0.0.1")

    def test_cancel_stops_the_wait(self):
        server, result, thread = self.serve(timeout=30)

        server.cancel()
        thread.join(5)

        self.assertIsInstance(result["error"], LoopbackCancelled)

    def test_times_out(self):
        server = LoopbackServer(0)

        with self.assertRaises(LoopbackTimeout):
            server.wait_for_callback(timeout=0.3)

    def test_a_silent_connection_does_not_block_cancellation(self):
        server, result, thread = self.serve(timeout=30)

        with socket.create_connection(("127.0.0.1", server.port), timeout=5):
            time.sleep(0.2)
            started = time.monotonic()
            server.cancel()
            thread.join(10)

        self.assertIsInstance(result.get("error"), LoopbackCancelled)
        self.assertLess(time.monotonic() - started, 3)

    def test_port_in_use_is_reported_plainly(self):
        first = LoopbackServer(0)
        self.addCleanup(first._server.server_close)

        # allow_reuse_address lets a second socket share a TIME_WAIT port but not a live listener.
        with self.assertRaisesRegex(LoopbackError, "in use"):
            LoopbackServer(first.port)


if __name__ == "__main__":
    unittest.main()
