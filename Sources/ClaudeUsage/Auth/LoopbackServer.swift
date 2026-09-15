// Minimal one-shot HTTP listener used as the OAuth redirect target.
// It serves a single response and then tears itself down.

import Foundation
import Network

actor LoopbackServer {
    struct CallbackQuery {
        let items: [String: String]
    }

    private var listener: NWListener?
    private var continuation: CheckedContinuation<CallbackQuery, Error>?

    let port: UInt16

    init(port: UInt16) {
        self.port = port
    }

    func waitForCallback() async throws -> CallbackQuery {
        let listener = try NWListener(
            using: .tcp,
            on: NWEndpoint.Port(rawValue: port) ?? .any
        )
        self.listener = listener

        return try await withTaskCancellationHandler {
            try await withCheckedThrowingContinuation { continuation in
                self.continuation = continuation
                listener.newConnectionHandler = { connection in
                    connection.start(queue: .main)
                    connection.receive(minimumIncompleteLength: 1, maximumLength: 8192) { data, _, _, _ in
                        let request = data.flatMap { String(data: $0, encoding: .utf8) } ?? ""
                        Task { await self.handle(request: request, on: connection) }
                    }
                }
                listener.stateUpdateHandler = { state in
                    if case .failed(let error) = state {
                        Task { await self.finish(with: .failure(error)) }
                    }
                }
                listener.start(queue: .main)
            }
        } onCancel: {
            Task { await self.finish(with: .failure(CancellationError())) }
        }
    }

    private func handle(request: String, on connection: NWConnection) {
        guard let line = request.split(separator: "\r\n").first,
              let path = line.split(separator: " ").dropFirst().first
        else {
            respond(on: connection, status: "400 Bad Request", body: Self.failureHTML)
            return
        }

        let components = URLComponents(string: "http://localhost\(path)")
        let items = Dictionary(
            (components?.queryItems ?? []).compactMap { item in
                item.value.map { (item.name, $0) }
            },
            uniquingKeysWith: { first, _ in first }
        )

        let succeeded = items["code"] != nil
        respond(
            on: connection,
            status: succeeded ? "200 OK" : "400 Bad Request",
            body: succeeded ? Self.successHTML : Self.failureHTML
        )
        finish(with: .success(CallbackQuery(items: items)))
    }

    private func respond(on connection: NWConnection, status: String, body: String) {
        let payload = """
        HTTP/1.1 \(status)\r
        Content-Type: text/html; charset=utf-8\r
        Content-Length: \(body.utf8.count)\r
        Connection: close\r
        \r
        \(body)
        """
        connection.send(
            content: Data(payload.utf8),
            completion: .contentProcessed { _ in connection.cancel() }
        )
    }

    private func finish(with result: Result<CallbackQuery, Error>) {
        guard let continuation else { return }
        self.continuation = nil
        listener?.cancel()
        listener = nil
        continuation.resume(with: result)
    }

    private static func page(title: String, message: String, glyph: String) -> String {
        """
        <!doctype html><meta charset="utf-8"><title>\(title)</title>
        <style>
          :root { color-scheme: light dark; }
          body { margin:0; min-height:100vh; display:grid; place-items:center;
                 font:15px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text",sans-serif;
                 background:#f5f5f7; color:#1d1d1f; }
          @media (prefers-color-scheme: dark) { body { background:#1c1c1e; color:#f5f5f7; } }
          .card { text-align:center; padding:48px 40px; max-width:360px; }
          .glyph { font-size:44px; line-height:1; }
          h1 { font-size:20px; margin:20px 0 8px; letter-spacing:-0.01em; }
          p { margin:0; opacity:0.6; }
        </style>
        <div class="card"><div class="glyph">\(glyph)</div><h1>\(title)</h1><p>\(message)</p></div>
        """
    }

    private static let successHTML = page(
        title: "Signed in",
        message: "You can close this tab and return to Claude Usage.",
        glyph: "&#10003;"
    )

    private static let failureHTML = page(
        title: "Sign-in failed",
        message: "No authorization code was returned. Please try again.",
        glyph: "&#9888;"
    )
}
