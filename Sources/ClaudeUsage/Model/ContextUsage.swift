// Context-window usage for the Claude Code session you touched most recently.
//
// Claude Code appends one JSON object per line to
// ~/.claude/projects/<slug>/<session-id>.jsonl. Each assistant line carries a
// `usage` block, and the last one describes the context the model just saw.
// Nothing here talks to the network — this is all local, read-only.

import Foundation

struct ContextUsage: Equatable {
    /// Directory the session runs in, e.g. "claude-usage-on-menu-bar".
    let project: String
    /// Tokens occupying the context window as of the last assistant turn.
    let tokens: Int
    /// Context window for the model that produced that turn.
    let limit: Int
    let model: String?
    /// Last write to the transcript, used to show staleness.
    let updatedAt: Date

    var fraction: Double { min(max(Double(tokens) / Double(limit), 0), 1) }
    var percent: Int { Int((fraction * 100).rounded()) }
}

enum ContextReader {
    /// Bytes read from the tail of a transcript on the first pass. Transcripts
    /// reach tens of MB, so we never read one whole.
    private static let tailWindow = 256 * 1024
    /// Second pass, for when a few very large tool results fill the first.
    private static let deepTailWindow = 4 * 1024 * 1024

    private static let projectsDirectory = URL.homeDirectory.appending(path: ".claude/projects")

    /// Context windows by model. Unknown models fall back to the current
    /// generation's 1M window.
    static func contextLimit(for model: String?) -> Int {
        guard let model else { return 1_000_000 }
        if model.contains("haiku") { return 200_000 }
        return 1_000_000
    }

    /// Reads the most recently modified transcript across every project.
    /// Returns nil when Claude Code has never run here, or the tail held no
    /// usable assistant turn. Blocking; call it off the main actor.
    static func currentSession() -> ContextUsage? {
        guard let transcript = newestTranscript() else { return nil }

        for window in [tailWindow, deepTailWindow] {
            guard let text = tail(of: transcript.url, bytes: window) else { return nil }
            if let usage = lastAssistantTurn(in: text) {
                return ContextUsage(
                    project: usage.project ?? projectName(from: transcript.url),
                    tokens: usage.tokens,
                    limit: contextLimit(for: usage.model),
                    model: usage.model,
                    updatedAt: transcript.modified
                )
            }
            // A single line larger than the window means we sliced mid-record;
            // the deeper pass gets another chance.
            if window == deepTailWindow { break }
        }
        return nil
    }

    // MARK: - Locating the transcript

    private static func newestTranscript() -> (url: URL, modified: Date)? {
        let keys: [URLResourceKey] = [.contentModificationDateKey, .isDirectoryKey]
        guard let projects = try? FileManager.default.contentsOfDirectory(
            at: projectsDirectory,
            includingPropertiesForKeys: keys,
            options: [.skipsHiddenFiles]
        ) else { return nil }

        var newest: (url: URL, modified: Date)?
        for project in projects {
            guard let files = try? FileManager.default.contentsOfDirectory(
                at: project,
                includingPropertiesForKeys: keys,
                options: [.skipsHiddenFiles]
            ) else { continue }

            for file in files where file.pathExtension == "jsonl" {
                guard let modified = try? file.resourceValues(forKeys: [.contentModificationDateKey])
                    .contentModificationDate else { continue }
                if newest == nil || modified > newest!.modified {
                    newest = (file, modified)
                }
            }
        }
        return newest
    }

    private static func projectName(from transcript: URL) -> String {
        // Slug form: "-Users-me-dev-thing". The trailing segment is the closest
        // we can get to a directory name without a `cwd` to read.
        let slug = transcript.deletingLastPathComponent().lastPathComponent
        return slug.split(separator: "-").last.map(String.init) ?? slug
    }

    // MARK: - Reading

    /// Last `bytes` of the file, trimmed forward to the first newline so the
    /// leading partial record is discarded.
    private static func tail(of url: URL, bytes: Int) -> String? {
        guard let handle = try? FileHandle(forReadingFrom: url) else { return nil }
        defer { try? handle.close() }

        guard let size = try? handle.seekToEnd() else { return nil }
        let offset = size > UInt64(bytes) ? size - UInt64(bytes) : 0
        try? handle.seek(toOffset: offset)
        guard let data = try? handle.readToEnd() else { return nil }

        var text = String(decoding: data, as: UTF8.self)
        if offset > 0, let firstBreak = text.firstIndex(of: "\n") {
            text = String(text[text.index(after: firstBreak)...])
        }
        return text
    }

    private struct Turn {
        let tokens: Int
        let model: String?
        let project: String?
    }

    /// Scans backwards for the newest main-thread assistant turn. Sidechain
    /// lines are subagent traffic and do not occupy the session's own context.
    private static func lastAssistantTurn(in text: String) -> Turn? {
        for line in text.split(separator: "\n", omittingEmptySubsequences: true).reversed() {
            guard line.first == "{",
                  let record = try? JSONDecoder().decode(TranscriptLine.self, from: Data(line.utf8)),
                  record.type == "assistant",
                  record.isSidechain != true,
                  let usage = record.message?.usage
            else { continue }

            return Turn(
                tokens: usage.contextTokens,
                model: record.message?.model,
                project: record.cwd.map { URL(fileURLWithPath: $0).lastPathComponent }
            )
        }
        return nil
    }
}

// MARK: - Transcript shape

/// Only the fields we need; Claude Code writes many more.
struct TranscriptLine: Decodable {
    struct Message: Decodable {
        let model: String?
        let usage: Usage?
    }

    struct Usage: Decodable {
        let input_tokens: Int?
        let output_tokens: Int?
        let cache_creation_input_tokens: Int?
        let cache_read_input_tokens: Int?

        /// Everything the model saw or produced on this turn. Cached tokens
        /// still occupy the window, so they count.
        var contextTokens: Int {
            (input_tokens ?? 0)
                + (cache_creation_input_tokens ?? 0)
                + (cache_read_input_tokens ?? 0)
                + (output_tokens ?? 0)
        }
    }

    let type: String?
    let cwd: String?
    let isSidechain: Bool?
    let message: Message?
}
