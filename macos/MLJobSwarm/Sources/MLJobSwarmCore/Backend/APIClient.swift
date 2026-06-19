import Foundation

public enum APIClientError: Error, LocalizedError {
    case invalidURL
    case badStatus(Int, String?)
    case decoding(Error)

    public var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid API URL"
        case .badStatus(let code, let detail):
            if let detail, !detail.isEmpty {
                return detail
            }
            return "API request failed with status \(code)"
        case .decoding(let error):
            return "Failed to decode API response: \(error.localizedDescription)"
        }
    }
}

public struct APIClient: Sendable {
    public let baseURL: URL
    private let session: URLSession

    public init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    public func health() async throws -> HealthResponse {
        try await get(path: "/api/v1/health")
    }

    public func llmUsage() async throws -> LLMUsageResponse {
        try await get(path: "/api/v1/llm/usage")
    }

    public func onboardingState(resumeAssetID: Int? = nil) async throws -> OnboardingState {
        var queryItems: [URLQueryItem] = []
        if let resumeAssetID {
            queryItems.append(URLQueryItem(name: "resume_asset_id", value: String(resumeAssetID)))
        }
        return try await get(path: "/api/v1/onboarding", queryItems: queryItems)
    }

    public func uploadResume(fileURL: URL) async throws -> ResumeUploadResponse {
        guard let url = endpointURL(path: "/api/v1/onboarding/resume") else {
            throw APIClientError.invalidURL
        }
        let boundary = "Boundary-\(UUID().uuidString)"
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        let fileData = try Data(contentsOf: fileURL)
        let filename = fileURL.lastPathComponent
        let mimeType = Self.mimeType(for: fileURL)
        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"resume\"; filename=\"\(filename)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: \(mimeType)\r\n\r\n".data(using: .utf8)!)
        body.append(fileData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        request.httpBody = body

        let (data, response) = try await session.data(for: request)
        try Self.ensureSuccess(data: data, response: response)
        return try JSONDecoder().decode(ResumeUploadResponse.self, from: data)
    }

    public func consentVisionFallback(resumeAssetID: Int, consent: Bool) async throws -> ResumeUploadResponse {
        struct Body: Encodable {
            let resumeAssetID: Int
            let consent: Bool

            enum CodingKeys: String, CodingKey {
                case consent
                case resumeAssetID = "resume_asset_id"
            }
        }
        return try await postJSON(
            path: "/api/v1/onboarding/vision-fallback",
            body: Body(resumeAssetID: resumeAssetID, consent: consent)
        )
    }

    public func createProfile(
        resumeAssetID: Int,
        role: String,
        level: String,
        location: String,
        workMode: String,
        companyStage: String
    ) async throws -> CreateProfileResponse {
        let body = PreferencesBody(
            resumeAssetID: resumeAssetID,
            role: role,
            level: level,
            location: location,
            workMode: workMode,
            companyStage: companyStage
        )
        return try await postJSON(path: "/api/v1/onboarding/preferences", body: body)
    }

    public func updateProfilePreferences(
        targetProfileID: Int,
        role: String,
        level: String,
        location: String,
        workMode: String,
        companyStage: String
    ) async throws -> StatusVersionResponse {
        let body = PreferencesBody(
            resumeAssetID: nil,
            role: role,
            level: level,
            location: location,
            workMode: workMode,
            companyStage: companyStage
        )
        return try await putJSON(path: "/api/v1/profiles/\(targetProfileID)/preferences", body: body)
    }

    public func profiles() async throws -> ProfilesResponse {
        try await get(path: "/api/v1/profiles")
    }

    public func dashboard(
        targetProfileID: Int,
        decisionFilter: String = "all",
        connectionFilter: String = "all"
    ) async throws -> DashboardResponse {
        try await get(
            path: "/api/v1/dashboard",
            queryItems: [
                URLQueryItem(name: "target_profile_id", value: String(targetProfileID)),
                URLQueryItem(name: "decision_filter", value: decisionFilter),
                URLQueryItem(name: "connection_filter", value: connectionFilter),
            ]
        )
    }

    public func savedJobs(
        targetProfileID: Int,
        query: String = "",
        sort: String = "recent"
    ) async throws -> SavedJobsResponse {
        try await get(
            path: "/api/v1/saved-jobs",
            queryItems: [
                URLQueryItem(name: "target_profile_id", value: String(targetProfileID)),
                URLQueryItem(name: "q", value: query),
                URLQueryItem(name: "sort", value: sort),
            ]
        )
    }

    public func exportSavedJobsCSV(
        targetProfileID: Int,
        query: String = "",
        sort: String = "recent"
    ) async throws -> Data {
        guard let url = endpointURL(
            path: "/api/v1/saved-jobs/export.csv",
            queryItems: [
                URLQueryItem(name: "target_profile_id", value: String(targetProfileID)),
                URLQueryItem(name: "q", value: query),
                URLQueryItem(name: "sort", value: sort),
            ]
        ) else {
            throw APIClientError.invalidURL
        }
        let (data, response) = try await session.data(from: url)
        try Self.ensureSuccess(data: data, response: response)
        return data
    }

    public func jobDetail(jobID: Int, targetProfileID: Int) async throws -> JobDetailResponse {
        try await get(
            path: "/api/v1/jobs/\(jobID)",
            queryItems: [URLQueryItem(name: "target_profile_id", value: String(targetProfileID))]
        )
    }

    public func connections(search: String = "") async throws -> ConnectionsResponse {
        var queryItems: [URLQueryItem] = []
        if !search.isEmpty {
            queryItems.append(URLQueryItem(name: "search", value: search))
        }
        return try await get(path: "/api/v1/connections", queryItems: queryItems)
    }

    public func adminSources() async throws -> AdminSourcesResponse {
        try await get(path: "/api/v1/admin/sources")
    }

    public func setDecision(
        jobID: Int,
        targetProfileID: Int,
        decision: String,
        notes: String = ""
    ) async throws {
        let body = JobDecisionRequest(
            targetProfileID: targetProfileID,
            decision: decision,
            notes: notes
        )
        _ = try await postJSON(path: "/api/v1/jobs/\(jobID)/decision", body: body) as StatusResponse
    }

    public func addReferralContact(
        jobID: Int,
        targetProfileID: Int,
        name: String,
        email: String = "",
        title: String = "",
        relationship: String = "",
        notes: String = ""
    ) async throws {
        let body = ReferralContactBody(
            targetProfileID: targetProfileID,
            name: name,
            email: email,
            title: title,
            relationship: relationship,
            notes: notes
        )
        _ = try await postJSON(path: "/api/v1/jobs/\(jobID)/referral-contacts", body: body) as StatusResponse
    }

    public func prepareApplicationPacket(jobID: Int, targetProfileID: Int) async throws -> JobDetailResponse {
        guard let url = endpointURL(
            path: "/api/v1/jobs/\(jobID)/application-packet",
            queryItems: [URLQueryItem(name: "target_profile_id", value: String(targetProfileID))]
        ) else {
            throw APIClientError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        let (data, response) = try await session.data(for: request)
        try Self.ensureSuccess(data: data, response: response)
        return try await jobDetail(jobID: jobID, targetProfileID: targetProfileID)
    }

    public func rewriteResumeSection(
        targetProfileID: Int,
        sectionID: Int,
        jobID: Int? = nil,
        llmConsent: Bool
    ) async throws -> ResumeRewriteResponse {
        struct Body: Encodable {
            let sectionID: Int
            let targetProfileID: Int
            let jobID: Int?
            let llmConsent: Bool

            enum CodingKeys: String, CodingKey {
                case jobID = "job_id"
                case sectionID = "section_id"
                case llmConsent = "llm_consent"
                case targetProfileID = "target_profile_id"
            }
        }
        return try await postJSON(
            path: "/api/v1/profiles/\(targetProfileID)/resume/rewrite",
            body: Body(
                sectionID: sectionID,
                targetProfileID: targetProfileID,
                jobID: jobID,
                llmConsent: llmConsent
            )
        )
    }

    public func updateSuggestionStatus(
        suggestionID: Int,
        targetProfileID: Int,
        accepted: Bool
    ) async throws {
        let path = accepted
            ? "/api/v1/resume/suggestions/\(suggestionID)/accept"
            : "/api/v1/resume/suggestions/\(suggestionID)/reject"
        struct Body: Encodable {
            let targetProfileID: Int

            enum CodingKeys: String, CodingKey {
                case targetProfileID = "target_profile_id"
            }
        }
        _ = try await postJSON(path: path, body: Body(targetProfileID: targetProfileID)) as StatusResponse
    }

    public func refreshAllAdminSources() async throws {
        _ = try await postJSON(path: "/api/v1/admin/sources/refresh", body: EmptyRequest()) as StatusResponse
    }

    public func refreshAdminSource(sourceID: Int) async throws {
        _ = try await postJSON(
            path: "/api/v1/admin/sources/\(sourceID)/refresh",
            body: EmptyRequest()
        ) as StatusResponse
    }

    public func approveSourceReview(queueID: Int) async throws {
        _ = try await postJSON(
            path: "/api/v1/admin/source-review/\(queueID)/approve",
            body: EmptyRequest()
        ) as StatusResponse
    }

    public func rejectSourceReview(queueID: Int) async throws {
        _ = try await postJSON(
            path: "/api/v1/admin/source-review/\(queueID)/reject",
            body: EmptyRequest()
        ) as StatusResponse
    }

    public func updatePacketStatus(
        packetID: Int,
        targetProfileID: Int,
        status: String
    ) async throws {
        let body = PacketStatusBody(targetProfileID: targetProfileID, status: status)
        _ = try await postJSON(
            path: "/api/v1/application-packets/\(packetID)/status",
            body: body
        ) as StatusResponse
    }

    public func refreshSources(targetProfileID: Int) async throws -> FindMatchesResponse {
        try await postJSON(
            path: "/api/v1/dashboard/refresh-sources",
            queryItems: [URLQueryItem(name: "target_profile_id", value: String(targetProfileID))],
            body: EmptyRequest()
        )
    }

    public func findMatches(targetProfileID: Int, llmConsent: Bool) async throws -> FindMatchesResponse {
        let body = FindMatchesBody(targetProfileID: targetProfileID, llmConsent: llmConsent)
        return try await postJSON(path: "/api/v1/dashboard/find-matches", body: body)
    }

    public func reviewJobs(targetProfileID: Int, llmConsent: Bool) async throws {
        let body = FindMatchesBody(targetProfileID: targetProfileID, llmConsent: llmConsent)
        _ = try await postJSON(path: "/api/v1/dashboard/review-jobs", body: body) as StatusResponse
    }

    public func importConnections(fileURL: URL) async throws -> ImportConnectionsResponse {
        guard let url = endpointURL(path: "/api/v1/connections/import") else {
            throw APIClientError.invalidURL
        }
        let boundary = "Boundary-\(UUID().uuidString)"
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        let fileData = try Data(contentsOf: fileURL)
        let filename = fileURL.lastPathComponent
        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"connections_file\"; filename=\"\(filename)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: text/csv\r\n\r\n".data(using: .utf8)!)
        body.append(fileData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        request.httpBody = body

        let (data, response) = try await session.data(for: request)
        try Self.ensureSuccess(data: data, response: response)
        return try JSONDecoder().decode(ImportConnectionsResponse.self, from: data)
    }

    private static func mimeType(for fileURL: URL) -> String {
        switch fileURL.pathExtension.lowercased() {
        case "pdf":
            return "application/pdf"
        case "docx":
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        default:
            return "application/octet-stream"
        }
    }

    private static func ensureSuccess(data: Data, response: URLResponse) throws {
        guard let http = response as? HTTPURLResponse else {
            throw APIClientError.badStatus(-1, nil)
        }
        guard (200...299).contains(http.statusCode) else {
            throw APIClientError.badStatus(http.statusCode, parseErrorDetail(from: data))
        }
    }

    private static func parseErrorDetail(from data: Data) -> String? {
        struct ErrorBody: Decodable {
            let detail: ErrorDetail?

            enum ErrorDetail: Decodable {
                case string(String)
                case list([String])

                init(from decoder: Decoder) throws {
                    let container = try decoder.singleValueContainer()
                    if let value = try? container.decode(String.self) {
                        self = .string(value)
                        return
                    }
                    if let values = try? container.decode([String].self) {
                        self = .list(values)
                        return
                    }
                    throw DecodingError.dataCorruptedError(
                        in: container,
                        debugDescription: "Unsupported error detail payload"
                    )
                }

                var message: String {
                    switch self {
                    case .string(let value):
                        return value
                    case .list(let values):
                        return values.joined(separator: ", ")
                    }
                }
            }
        }

        guard let body = try? JSONDecoder().decode(ErrorBody.self, from: data) else {
            return String(data: data, encoding: .utf8)
        }
        return body.detail?.message
    }

    private func endpointURL(path: String, queryItems: [URLQueryItem] = []) -> URL? {
        var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false)
        let normalized = path.hasPrefix("/") ? String(path.dropFirst()) : path
        var basePath = components?.path ?? ""
        if basePath.hasSuffix("/") {
            basePath = String(basePath.dropLast())
        }
        components?.path = "\(basePath)/\(normalized)"
        if !queryItems.isEmpty {
            components?.queryItems = queryItems
        }
        return components?.url
    }

    private func get<T: Decodable>(path: String, queryItems: [URLQueryItem] = []) async throws -> T {
        guard let url = endpointURL(path: path, queryItems: queryItems) else {
            throw APIClientError.invalidURL
        }
        let (data, response) = try await session.data(from: url)
        try Self.ensureSuccess(data: data, response: response)
        return try JSONDecoder().decode(T.self, from: data)
    }

    private struct EmptyRequest: Encodable {}
    private struct StatusResponse: Decodable { let status: String }

    public struct ResumeRewriteResponse: Decodable, Sendable {
        public let status: String
        public let suggestionId: Int
        public let suggestionText: String

        enum CodingKeys: String, CodingKey {
            case status
            case suggestionId = "suggestion_id"
            case suggestionText = "suggestion_text"
        }
    }

    public struct StatusVersionResponse: Decodable, Sendable {
        public let status: String
        public let version: Int
    }

    private struct PreferencesBody: Encodable {
        let resumeAssetID: Int?
        let role: String
        let level: String
        let location: String
        let workMode: String
        let companyStage: String

        enum CodingKeys: String, CodingKey {
            case role, level, location
            case resumeAssetID = "resume_asset_id"
            case workMode = "work_mode"
            case companyStage = "company_stage"
        }
    }

    private struct JobDecisionRequest: Encodable {
        let targetProfileID: Int
        let decision: String
        let notes: String

        enum CodingKeys: String, CodingKey {
            case decision, notes
            case targetProfileID = "target_profile_id"
        }
    }

    private struct ReferralContactBody: Encodable {
        let targetProfileID: Int
        let name: String
        let email: String
        let title: String
        let relationship: String
        let notes: String

        enum CodingKeys: String, CodingKey {
            case name, email, title, relationship, notes
            case targetProfileID = "target_profile_id"
        }
    }

    private struct PacketStatusBody: Encodable {
        let targetProfileID: Int
        let status: String

        enum CodingKeys: String, CodingKey {
            case status
            case targetProfileID = "target_profile_id"
        }
    }

    private struct FindMatchesBody: Encodable {
        let targetProfileID: Int
        let llmConsent: Bool

        enum CodingKeys: String, CodingKey {
            case targetProfileID = "target_profile_id"
            case llmConsent = "llm_consent"
        }
    }

    private func postJSON<T: Decodable, B: Encodable>(
        path: String,
        queryItems: [URLQueryItem] = [],
        body: B
    ) async throws -> T {
        guard let url = endpointURL(path: path, queryItems: queryItems) else {
            throw APIClientError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        let (data, response) = try await session.data(for: request)
        try Self.ensureSuccess(data: data, response: response)
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func putJSON<T: Decodable, B: Encodable>(path: String, body: B) async throws -> T {
        guard let url = endpointURL(path: path) else {
            throw APIClientError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        let (data, response) = try await session.data(for: request)
        try Self.ensureSuccess(data: data, response: response)
        return try JSONDecoder().decode(T.self, from: data)
    }
}