// Covers the transcript shape Claude Code writes and the limit lookup.

import Foundation
import Testing
@testable import ClaudeUsage

@Suite("Context usage")
struct ContextUsageTests {
    private func usage(_ json: String) throws -> TranscriptLine.Usage? {
        try JSONDecoder().decode(TranscriptLine.self, from: Data(json.utf8)).message?.usage
    }

    @Test func countsCachedTokensTowardTheWindow() throws {
        let usage = try usage("""
        {
          "type": "assistant",
          "message": {
            "model": "claude-opus-5",
            "usage": {
              "input_tokens": 2,
              "cache_creation_input_tokens": 511,
              "cache_read_input_tokens": 49496,
              "output_tokens": 208
            }
          }
        }
        """)

        #expect(usage?.contextTokens == 50_217)
    }

    @Test func toleratesMissingCounters() throws {
        let usage = try usage("""
        { "type": "assistant", "message": { "usage": { "input_tokens": 100 } } }
        """)

        #expect(usage?.contextTokens == 100)
    }

    @Test func ignoresUnknownFields() throws {
        // Claude Code writes many more keys than we model; decoding must not break.
        let line = try JSONDecoder().decode(TranscriptLine.self, from: Data("""
        {
          "type": "assistant", "cwd": "/Users/me/dev/thing", "isSidechain": false,
          "gitBranch": "main", "requestId": "abc", "effort": "high",
          "message": {
            "model": "claude-opus-5",
            "usage": {
              "input_tokens": 1, "output_tokens": 2,
              "server_tool_use": { "web_search_requests": 0 },
              "iterations": [{ "input_tokens": 1 }]
            }
          }
        }
        """.utf8))

        #expect(line.type == "assistant")
        #expect(line.isSidechain == false)
        #expect(line.cwd == "/Users/me/dev/thing")
        #expect(line.message?.usage?.contextTokens == 3)
    }

    @Test func contextLimitsByModel() {
        #expect(ContextReader.contextLimit(for: "claude-opus-5") == 1_000_000)
        #expect(ContextReader.contextLimit(for: "claude-sonnet-5") == 1_000_000)
        #expect(ContextReader.contextLimit(for: "claude-haiku-4-5-20251001") == 200_000)
        // Unknown models fall back to the current generation's window.
        #expect(ContextReader.contextLimit(for: nil) == 1_000_000)
    }

    @Test func fractionIsClampedAndRounded() {
        let context = ContextUsage(
            project: "thing", tokens: 50_009, limit: 1_000_000,
            model: "claude-opus-5", updatedAt: .now
        )
        #expect(context.percent == 5)

        let over = ContextUsage(
            project: "thing", tokens: 2_000_000, limit: 1_000_000,
            model: "claude-opus-5", updatedAt: .now
        )
        #expect(over.fraction == 1)
    }

    @Test func compactTokenFormatting() {
        #expect(Format.compactTokens(1_000_000) == "1M")
        #expect(Format.compactTokens(200_000) == "200K")
        #expect(Format.compactTokens(1_500_000) == "1.5M")
        #expect(Format.compactTokens(512) == "512")
    }
}
