import Foundation
import Security

public struct LLMPreferences: Codable, Sendable, Equatable {
    public var fitModel: String
    public var rewriteModel: String
    public var visionModel: String
    public var httpReferer: String
    public var appTitle: String

    public init(
        fitModel: String = "",
        rewriteModel: String = "",
        visionModel: String = "",
        httpReferer: String = "",
        appTitle: String = "ML Job Swarm"
    ) {
        self.fitModel = fitModel
        self.rewriteModel = rewriteModel
        self.visionModel = visionModel
        self.httpReferer = httpReferer
        self.appTitle = appTitle
    }

    enum CodingKeys: String, CodingKey {
        case fitModel = "fit_model"
        case rewriteModel = "rewrite_model"
        case visionModel = "vision_model"
        case httpReferer = "http_referer"
        case appTitle = "app_title"
    }
}

public enum LLMSettingsStoreError: Error, LocalizedError {
    case keychainError(OSStatus)
    case preferencesWriteFailed

    public var errorDescription: String? {
        switch self {
        case .keychainError(let status):
            return "Keychain error (\(status)) while saving the OpenRouter API key."
        case .preferencesWriteFailed:
            return "Could not save LLM preferences."
        }
    }
}

public struct LegacyLLMImportResult: Sendable {
    public let imported: Bool
    public let sourcePath: String?

    public init(imported: Bool, sourcePath: String?) {
        self.imported = imported
        self.sourcePath = sourcePath
    }
}

public struct LegacyLLMImportRecord: Codable, Sendable {
    public let sourcePath: String
    public let importedAt: String

    enum CodingKeys: String, CodingKey {
        case sourcePath = "source_path"
        case importedAt = "imported_at"
    }
}

public struct LLMSettingsStore: Sendable {
    public static let shared = LLMSettingsStore()

    private let service = "com.davidlifschitz.ml-job-swarm.openrouter"
    private let account = "api-key"

    public init() {}

    public var legacyImportRecordURL: URL {
        Self.applicationSupportDirectory()
            .appendingPathComponent("legacy-llm-import.json")
    }

    public var preferencesURL: URL {
        Self.applicationSupportDirectory()
            .appendingPathComponent("llm-settings.json")
    }

    public var importedKeySourceURL: URL {
        Self.applicationSupportDirectory()
            .appendingPathComponent("llm-key-source.txt")
    }

    public func importedKeySourcePath() -> String? {
        guard FileManager.default.fileExists(atPath: importedKeySourceURL.path),
              let source = try? String(contentsOf: importedKeySourceURL, encoding: .utf8) else {
            return nil
        }
        let trimmed = source.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    /// Imports `OPENROUTER_API_KEY` from a legacy project `.env` into Keychain once.
    public func importLegacyAPIKeyIfNeeded() -> LegacyLLMImportResult {
        if hasStoredAPIKey() {
            return LegacyLLMImportResult(imported: false, sourcePath: importedKeySourcePath())
        }
        if hasCompletedLegacyImportAttempt() {
            return LegacyLLMImportResult(imported: false, sourcePath: nil)
        }
        for candidate in Self.legacyEnvCandidatePaths() {
            guard let apiKey = Self.parseOpenRouterAPIKey(from: candidate) else {
                continue
            }
            do {
                try saveAPIKey(apiKey)
                try recordLegacyImport(sourcePath: candidate.path)
                try recordImportedKeySource(candidate.path)
                return LegacyLLMImportResult(imported: true, sourcePath: candidate.path)
            } catch {
                continue
            }
        }
        try? recordLegacyImport(sourcePath: "")
        return LegacyLLMImportResult(imported: false, sourcePath: nil)
    }

    public func hasStoredAPIKey() -> Bool {
        loadAPIKey() != nil
    }

    public func loadAPIKey() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess,
              let data = item as? Data,
              let key = String(data: data, encoding: .utf8),
              !key.isEmpty else {
            return nil
        }
        return key
    }

    public func loadPreferences() -> LLMPreferences {
        guard FileManager.default.fileExists(atPath: preferencesURL.path),
              let data = try? Data(contentsOf: preferencesURL),
              let preferences = try? JSONDecoder().decode(LLMPreferences.self, from: data) else {
            return LLMPreferences()
        }
        return preferences
    }

    public func save(apiKey: String?, preferences: LLMPreferences) throws {
        if let apiKey {
            try saveAPIKey(apiKey)
        }
        try savePreferences(preferences)
    }

    public func clearAPIKey() throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        let status = SecItemDelete(query as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw LLMSettingsStoreError.keychainError(status)
        }
    }

    public func openRouterEnvironment() -> [String: String] {
        var environment: [String: String] = [:]
        if let apiKey = resolvedAPIKey() {
            environment["OPENROUTER_API_KEY"] = apiKey
        }
        let preferences = loadPreferences()
        if !preferences.fitModel.isEmpty {
            environment["OPENROUTER_FIT_MODEL"] = preferences.fitModel
        }
        if !preferences.rewriteModel.isEmpty {
            environment["OPENROUTER_RESUME_REWRITE_MODEL"] = preferences.rewriteModel
        }
        if !preferences.visionModel.isEmpty {
            environment["OPENROUTER_VISION_MODEL"] = preferences.visionModel
        }
        if !preferences.httpReferer.isEmpty {
            environment["OPENROUTER_HTTP_REFERER"] = preferences.httpReferer
        }
        if !preferences.appTitle.isEmpty {
            environment["OPENROUTER_APP_TITLE"] = preferences.appTitle
        }
        return environment
    }

    private func resolvedAPIKey() -> String? {
        if let stored = loadAPIKey() {
            return stored
        }
        let envKey = ProcessInfo.processInfo.environment["OPENROUTER_API_KEY"]?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return envKey.isEmpty ? nil : envKey
    }

    private func saveAPIKey(_ apiKey: String) throws {
        let trimmed = apiKey.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            try clearAPIKey()
            return
        }
        guard let data = trimmed.data(using: .utf8) else { return }

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        let attributes: [String: Any] = [
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock,
        ]
        let updateStatus = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if updateStatus == errSecSuccess {
            return
        }
        if updateStatus == errSecItemNotFound {
            var createQuery = query
            createQuery[kSecValueData as String] = data
            createQuery[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
            let addStatus = SecItemAdd(createQuery as CFDictionary, nil)
            guard addStatus == errSecSuccess else {
                throw LLMSettingsStoreError.keychainError(addStatus)
            }
            return
        }
        throw LLMSettingsStoreError.keychainError(updateStatus)
    }

    private static func applicationSupportDirectory() -> URL {
        let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let directory = support.appendingPathComponent("MLJobSwarm", isDirectory: true)
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        return directory
    }

    private func savePreferences(_ preferences: LLMPreferences) throws {
        let directory = preferencesURL.deletingLastPathComponent()
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let data = try JSONEncoder().encode(preferences)
        try data.write(to: preferencesURL, options: .atomic)
    }

    private func hasCompletedLegacyImportAttempt() -> Bool {
        FileManager.default.fileExists(atPath: legacyImportRecordURL.path)
    }

    private func recordLegacyImport(sourcePath: String) throws {
        let record = LegacyLLMImportRecord(
            sourcePath: sourcePath,
            importedAt: ISO8601DateFormatter().string(from: Date())
        )
        let directory = legacyImportRecordURL.deletingLastPathComponent()
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let data = try JSONEncoder().encode(record)
        try data.write(to: legacyImportRecordURL, options: .atomic)
    }

    private func recordImportedKeySource(_ sourcePath: String) throws {
        let directory = importedKeySourceURL.deletingLastPathComponent()
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        try sourcePath.write(to: importedKeySourceURL, atomically: true, encoding: .utf8)
    }

    private static func legacyEnvCandidatePaths() -> [URL] {
        let home = FileManager.default.homeDirectoryForCurrentUser
        let candidates = [
            home.appendingPathComponent("DavidsCodeProjects/ml-job-swarm/Legacy/.env"),
            home.appendingPathComponent("DavidsCodeProjects/ml-job-swarm/.env"),
            home.appendingPathComponent(".env"),
        ]
        return candidates.filter { FileManager.default.fileExists(atPath: $0.path) }
    }

    static func parseOpenRouterAPIKey(from url: URL) -> String? {
        guard let contents = try? String(contentsOf: url, encoding: .utf8) else {
            return nil
        }
        for line in contents.components(separatedBy: .newlines) {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.isEmpty || trimmed.hasPrefix("#") {
                continue
            }
            guard trimmed.hasPrefix("OPENROUTER_API_KEY=") else {
                continue
            }
            var value = String(trimmed.dropFirst("OPENROUTER_API_KEY=".count))
            value = value.trimmingCharacters(in: .whitespaces)
            if (value.hasPrefix("\"") && value.hasSuffix("\""))
                || (value.hasPrefix("'") && value.hasSuffix("'")) {
                value = String(value.dropFirst().dropLast())
            }
            return value.isEmpty ? nil : value
        }
        return nil
    }
}