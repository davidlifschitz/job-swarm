import Foundation
import SQLite3

public enum BackendManagerError: Error, LocalizedError {
    case projectRootNotFound
    case pythonRuntimeNotFound
    case startupTimeout
    case processFailed(String)

    public var errorDescription: String? {
        switch self {
        case .projectRootNotFound:
            return "Could not locate the ml-job-swarm backend. Rebuild the app with ./scripts/build-macos-app.sh."
        case .pythonRuntimeNotFound:
            return "Could not start the Python backend. Rebuild the app with ./scripts/build-macos-app.sh, or install uv (https://docs.astral.sh/uv/) for development runs."
        case .startupTimeout:
            return "Timed out waiting for the Python backend to start."
        case .processFailed(let message):
            return message
        }
    }
}

@MainActor
public final class BackendManager: ObservableObject {
    public private(set) var baseURL: URL
    public private(set) var apiClient: APIClient

    @Published public private(set) var status: String = "Starting backend…"
    @Published public private(set) var isReady = false

    private var process: Process?
    private let backendRoot: URL
    private let databaseURL: URL
    private let defaultPort = 18_765

    public init(port: Int = 18_765, previewReady: Bool = false) {
        self.baseURL = URL(string: "http://127.0.0.1:\(port)")!
        self.apiClient = APIClient(baseURL: baseURL)
        self.backendRoot = BackendManager.locateBackendRoot()
        self.databaseURL = BackendManager.defaultDatabaseURL()
        if previewReady {
            self.status = "Preview"
            self.isReady = true
        }
    }

    public static func preview() -> BackendManager {
        BackendManager(previewReady: true)
    }

    public func start() async {
        guard !isReady else { return }
        do {
            let port = try Self.findAvailablePort(startingAt: defaultPort)
            updateBaseURL(port: port)
            try await launchBackend(port: port)
            try await waitForHealth()
            status = "Backend ready"
            isReady = true
        } catch {
            status = error.localizedDescription
            isReady = false
        }
    }

    public func stop() {
        process?.terminate()
        process = nil
        isReady = false
        status = "Backend stopped"
    }

    public func restart() async {
        stop()
        await start()
    }

    private func updateBaseURL(port: Int) {
        baseURL = URL(string: "http://127.0.0.1:\(port)")!
        apiClient = APIClient(baseURL: baseURL)
    }

    private func launchBackend(port: Int) async throws {
        guard FileManager.default.fileExists(atPath: backendRoot.path) else {
            throw BackendManagerError.projectRootNotFound
        }

        let launch = try Self.launchConfiguration(backendRoot: backendRoot, port: port)
        let seedPath = backendRoot.appendingPathComponent("data/seed_companies.json")

        let process = Process()
        process.executableURL = URL(fileURLWithPath: launch.executable)
        process.currentDirectoryURL = backendRoot
        process.arguments = launch.arguments
        process.environment = Self.backendEnvironment(
            databaseURL: databaseURL,
            seedURL: seedPath,
            augmentedPath: launch.pathPrefix,
            catalogImportPath: Self.legacyCatalogImportPath(
                databaseURL: databaseURL,
                backendRoot: backendRoot
            )
        )

        let logPipe = Pipe()
        process.standardOutput = logPipe
        process.standardError = logPipe
        try process.run()
        self.process = process
        status = "Launching Python backend on port \(port)…"
    }

    private func waitForHealth(timeoutSeconds: TimeInterval = 45) async throws {
        let expectedDBPath = databaseURL.path
        let deadline = Date().addingTimeInterval(timeoutSeconds)
        while Date() < deadline {
            if let process, !process.isRunning {
                throw BackendManagerError.processFailed(
                    "Python backend exited before becoming ready. Check Console.app for MLJobSwarm logs."
                )
            }
            do {
                let health = try await apiClient.health()
                if health.status == "ok" {
                    if let dbPath = health.dbPath, dbPath != expectedDBPath {
                        throw BackendManagerError.processFailed(
                            "Port \(baseURL.port ?? defaultPort) is serving a different database (\(dbPath)). Quit other ml-job-swarm servers and relaunch."
                        )
                    }
                    try await verifyNativeAPI()
                    return
                }
            } catch let error as BackendManagerError {
                throw error
            } catch {
                try await Task.sleep(nanoseconds: 500_000_000)
                continue
            }
        }
        throw BackendManagerError.startupTimeout
    }

    private func verifyNativeAPI() async throws {
        do {
            _ = try await apiClient.onboardingState()
        } catch APIClientError.badStatus(let code, _) where code == 404 {
            let port = baseURL.port ?? defaultPort
            throw BackendManagerError.processFailed(
                "Port \(port) is serving an older ml-job-swarm build without native onboarding APIs. Quit other servers on that port and relaunch the app."
            )
        } catch {
            throw BackendManagerError.processFailed(
                "Backend health check passed but native API verification failed: \(error.localizedDescription)"
            )
        }
    }

    private struct LaunchConfiguration {
        let executable: String
        let arguments: [String]
        let pathPrefix: String?
    }

    private static func findAvailablePort(startingAt: Int, attempts: Int = 12) throws -> Int {
        for offset in 0..<attempts {
            let port = startingAt + offset
            if isPortAvailable(port) {
                return port
            }
        }
        throw BackendManagerError.processFailed(
            "Could not find a free port near \(startingAt). Quit other ml-job-swarm servers and relaunch."
        )
    }

    private static func isPortAvailable(_ port: Int) -> Bool {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/sbin/lsof")
        process.arguments = ["-i", "TCP:\(port)", "-sTCP:LISTEN"]
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = Pipe()
        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            return true
        }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let output = String(data: data, encoding: .utf8) ?? ""
        return output.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    private static func launchConfiguration(backendRoot: URL, port: Int) throws -> LaunchConfiguration {
        let uvicornArgs = [
            "-m", "uvicorn",
            "ml_job_swarm.app:create_app_from_env",
            "--factory",
            "--host", "127.0.0.1",
            "--port", String(port),
        ]

        if let python = bundledPython(in: backendRoot) {
            return LaunchConfiguration(
                executable: python,
                arguments: uvicornArgs,
                pathPrefix: backendRoot.appendingPathComponent(".venv/bin").path
            )
        }

        let uvPath = try locateUvExecutable()
        return LaunchConfiguration(
            executable: uvPath,
            arguments: ["run"] + uvicornArgs,
            pathPrefix: (uvPath as NSString).deletingLastPathComponent
        )
    }

    private static func bundledPython(in backendRoot: URL) -> String? {
        let candidates = [
            backendRoot.appendingPathComponent(".venv/bin/python3"),
            backendRoot.appendingPathComponent(".venv/bin/python"),
        ]
        for candidate in candidates where FileManager.default.isExecutableFile(atPath: candidate.path) {
            return candidate.path
        }
        return nil
    }

    private static func legacyCatalogImportPath(databaseURL: URL, backendRoot: URL) -> String? {
        let candidates = [
            FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent("DavidsCodeProjects/ml-job-swarm/jobs.db"),
            backendRoot.appendingPathComponent("jobs.db"),
        ]
        guard destinationNeedsCatalogImport(databaseURL: databaseURL) else {
            return nil
        }
        for candidate in candidates where catalogHasJobs(at: candidate) {
            return candidate.path
        }
        return nil
    }

    private static func destinationNeedsCatalogImport(databaseURL: URL) -> Bool {
        guard FileManager.default.fileExists(atPath: databaseURL.path) else {
            return true
        }
        return !catalogHasJobs(at: databaseURL)
    }

    private static func catalogHasJobs(at url: URL) -> Bool {
        guard FileManager.default.fileExists(atPath: url.path) else {
            return false
        }
        var database: OpaquePointer?
        guard sqlite3_open(url.path, &database) == SQLITE_OK, let database else {
            return false
        }
        defer { sqlite3_close(database) }
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(database, "SELECT COUNT(*) FROM jobs", -1, &statement, nil) == SQLITE_OK,
              let statement else {
            return false
        }
        defer { sqlite3_finalize(statement) }
        guard sqlite3_step(statement) == SQLITE_ROW else {
            return false
        }
        return sqlite3_column_int(statement, 0) > 0
    }

    private static func backendEnvironment(
        databaseURL: URL,
        seedURL: URL,
        augmentedPath: String?,
        catalogImportPath: String?
    ) -> [String: String] {
        var environment = ProcessInfo.processInfo.environment
        if let augmentedPath, !augmentedPath.isEmpty {
            let existing = environment["PATH"] ?? "/usr/bin:/bin:/usr/sbin:/sbin"
            environment["PATH"] = "\(augmentedPath):\(existing)"
        }
        let supportDirectory = applicationSupportDirectory()
        environment["ML_JOB_SWARM_DB_PATH"] = databaseURL.path
        environment["ML_JOB_SWARM_RESUME_ASSET_DIR"] = supportDirectory
            .appendingPathComponent("resume-assets", isDirectory: true)
            .path
        if FileManager.default.fileExists(atPath: seedURL.path) {
            environment["ML_JOB_SWARM_SEED_COMPANIES"] = seedURL.path
        }
        if let catalogImportPath {
            environment["ML_JOB_SWARM_IMPORT_CATALOG_FROM"] = catalogImportPath
        }
        for (key, value) in LLMSettingsStore.shared.openRouterEnvironment() where !value.isEmpty {
            environment[key] = value
        }
        return environment
    }

    static func applicationSupportDirectory() -> URL {
        let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let directory = support.appendingPathComponent("MLJobSwarm", isDirectory: true)
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        return directory
    }

    private static func defaultDatabaseURL() -> URL {
        applicationSupportDirectory().appendingPathComponent("jobs.db")
    }

    private static func locateBackendRoot() -> URL {
        if let resources = Bundle.main.resourceURL {
            let bundled = resources.appendingPathComponent("backend", isDirectory: true)
            let marker = bundled.appendingPathComponent("pyproject.toml")
            let packageMarker = bundled.appendingPathComponent("ml_job_swarm")
            if FileManager.default.fileExists(atPath: marker.path),
               FileManager.default.fileExists(atPath: packageMarker.path) {
                return bundled
            }
        }
        return locateProjectRoot()
    }

    private static func locateProjectRoot() -> URL {
        let fileManager = FileManager.default
        let candidates = [
            fileManager.currentDirectoryPath,
            Bundle.main.bundlePath,
        ]
        for candidate in candidates {
            var url = URL(fileURLWithPath: candidate, isDirectory: true)
            for _ in 0..<8 {
                let marker = url.appendingPathComponent("pyproject.toml")
                let packageMarker = url.appendingPathComponent("ml_job_swarm")
                if fileManager.fileExists(atPath: marker.path),
                   fileManager.fileExists(atPath: packageMarker.path) {
                    return url
                }
                url.deleteLastPathComponent()
            }
        }
        return URL(fileURLWithPath: fileManager.currentDirectoryPath, isDirectory: true)
    }

    private static func locateUvExecutable() throws -> String {
        let home = NSHomeDirectory()
        let candidates = [
            "/opt/homebrew/bin/uv",
            "/usr/local/bin/uv",
            "\(home)/.local/bin/uv",
            "\(home)/.cargo/bin/uv",
        ]
        for path in candidates where FileManager.default.isExecutableFile(atPath: path) {
            return path
        }

        let searchPath = [
            "/opt/homebrew/bin",
            "/usr/local/bin",
            "\(home)/.local/bin",
            "\(home)/.cargo/bin",
            ProcessInfo.processInfo.environment["PATH"] ?? "",
        ].joined(separator: ":")

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        process.arguments = ["bash", "-lc", "export PATH='\(searchPath)'; command -v uv"]
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = Pipe()
        try process.run()
        process.waitUntilExit()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let path = String(data: data, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        guard !path.isEmpty, FileManager.default.isExecutableFile(atPath: path) else {
            throw BackendManagerError.pythonRuntimeNotFound
        }
        return path
    }
}