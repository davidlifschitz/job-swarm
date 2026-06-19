import Foundation

public struct HealthResponse: Codable, Sendable {
    public let status: String
    public let connectionCount: Int
    public let fitReviewAvailable: Bool
    public let profileCount: Int?
    public let jobCount: Int?
    public let dbPath: String?

    enum CodingKeys: String, CodingKey {
        case status
        case connectionCount = "connection_count"
        case fitReviewAvailable = "fit_review_available"
        case profileCount = "profile_count"
        case jobCount = "job_count"
        case dbPath = "db_path"
    }
}

public struct OnboardingState: Codable, Sendable {
    public let hasProfiles: Bool
    public let preferenceFields: [String]
    public let resumeAssetId: Int?
    public let pendingVisionFallback: Bool
    public let fitReviewAvailable: Bool

    enum CodingKeys: String, CodingKey {
        case hasProfiles = "has_profiles"
        case preferenceFields = "preference_fields"
        case resumeAssetId = "resume_asset_id"
        case pendingVisionFallback = "pending_vision_fallback"
        case fitReviewAvailable = "fit_review_available"
    }
}

public struct ResumeUploadResponse: Codable, Sendable {
    public let status: String
    public let resumeAssetId: Int
    public let needsVisionFallback: Bool

    enum CodingKeys: String, CodingKey {
        case status
        case resumeAssetId = "resume_asset_id"
        case needsVisionFallback = "needs_vision_fallback"
    }
}

public struct CreateProfileResponse: Codable, Sendable {
    public let status: String
    public let targetProfileId: Int

    enum CodingKeys: String, CodingKey {
        case status
        case targetProfileId = "target_profile_id"
    }
}

public struct ProfileSummary: Codable, Sendable, Identifiable {
    public let id: Int
    public let name: String
    public let version: Int
    public let resumeFilename: String
    public let desiredTitles: [String]
    public let levels: [String]
    public let locations: [String]
    public let remoteModes: [String]
    public let companyStages: [String]
    public let keywords: [String]

    enum CodingKeys: String, CodingKey {
        case id, name, version, keywords
        case resumeFilename = "resume_filename"
        case desiredTitles = "desired_titles"
        case levels
        case locations
        case remoteModes = "remote_modes"
        case companyStages = "company_stages"
    }
}

public struct ProfilesResponse: Codable, Sendable {
    public let profiles: [ProfileListItem]
}

public struct ProfileListItem: Codable, Sendable, Identifiable {
    public let id: Int
    public let name: String
    public let version: Int
    public let active: Int
}

public struct ResumeSection: Codable, Sendable, Identifiable {
    public let id: Int
    public let sectionType: String
    public let heading: String
    public let text: String

    enum CodingKeys: String, CodingKey {
        case id, heading, text
        case sectionType = "section_type"
    }
}

public struct ResumeSuggestion: Codable, Sendable, Identifiable {
    public let id: Int
    public let sectionId: Int?
    public let suggestionText: String
    public let status: String
    public let createdAt: String?
    public let heading: String?
    public let sectionType: String?

    enum CodingKeys: String, CodingKey {
        case id, status, heading
        case sectionId = "section_id"
        case suggestionText = "suggestion_text"
        case createdAt = "created_at"
        case sectionType = "section_type"
    }
}

public struct JobFit: Codable, Sendable, Identifiable {
    public var id: Int { jobId }
    public let jobId: Int
    public let title: String
    public let fitScore: Int
    public let label: String
    public let reasons: [String]
    public let risks: [String]
    public let recommendation: String
    public let decision: String?
    public let notes: String

    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"
        case title
        case fitScore = "fit_score"
        case label, reasons, risks, recommendation, decision, notes
    }
}

public struct UnreviewedJob: Codable, Sendable, Identifiable {
    public var id: Int { jobId }
    public let jobId: Int
    public let title: String
    public let locationText: String?
    public let remoteMode: String?
    public let companyName: String

    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"
        case title
        case locationText = "location_text"
        case remoteMode = "remote_mode"
        case companyName = "company_name"
    }
}

public struct RulesPreviewJob: Codable, Sendable, Identifiable {
    public var id: Int { jobId }
    public let jobId: Int
    public let title: String
    public let companyName: String
    public let score: Int
    public let locationText: String?
    public let remoteMode: String?
    public let reasons: [String]
    public let risks: [String]

    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"
        case title, score, reasons, risks
        case companyName = "company_name"
        case locationText = "location_text"
        case remoteMode = "remote_mode"
    }
}

public struct LinkedInConnection: Codable, Sendable, Identifiable {
    public let id: Int
    public let profileURL: String
    public let firstName: String
    public let lastName: String
    public let company: String
    public let position: String
    public let connectedOn: String

    public var fullName: String { "\(firstName) \(lastName)".trimmingCharacters(in: .whitespaces) }

    enum CodingKeys: String, CodingKey {
        case id, company, position
        case profileURL = "profile_url"
        case firstName = "first_name"
        case lastName = "last_name"
        case connectedOn = "connected_on"
    }
}

public struct CompanyGroup: Codable, Sendable, Identifiable {
    public var id: Int { companyId }
    public let companyId: Int
    public let name: String
    public let visibleJobs: [JobFit]
    public let mismatchRiskJobs: [JobFit]
    public let hiddenJobs: [JobFit]
    public let filteredOutCount: Int
    public let linkedinConnections: [LinkedInConnection]
    public let connectionCount: Int

    enum CodingKeys: String, CodingKey {
        case name
        case companyId = "company_id"
        case visibleJobs = "visible_jobs"
        case mismatchRiskJobs = "mismatch_risk_jobs"
        case hiddenJobs = "hidden_jobs"
        case filteredOutCount = "filtered_out_count"
        case linkedinConnections = "linkedin_connections"
        case connectionCount = "connection_count"
    }
}

public struct RulesPreviewCompany: Codable, Sendable, Identifiable {
    public var id: String { companyName }
    public let companyName: String
    public let companyId: Int?
    public let jobs: [RulesPreviewJob]
    public let connectionCount: Int
    public let linkedinConnections: [LinkedInConnection]

    enum CodingKeys: String, CodingKey {
        case jobs
        case companyName = "company_name"
        case companyId = "company_id"
        case connectionCount = "connection_count"
        case linkedinConnections = "linkedin_connections"
    }
}

public struct DashboardResponse: Codable, Sendable {
    public let targetProfileId: Int
    public let decisionFilter: String
    public let connectionFilter: String
    public let connectionCount: Int
    public let catalogRefreshedAt: String?
    public let fitReviewAvailable: Bool
    public let profileSummary: ProfileSummary
    public let companies: [CompanyGroup]
    public let rulesPreviewJobs: [RulesPreviewJob]
    public let rulesPreviewCompanies: [RulesPreviewCompany]
    public let referralNetwork: [CatalogMatch]
    public let unreviewedJobs: [UnreviewedJob]
    public let resumeSections: [ResumeSection]
    public let resumeSuggestions: [ResumeSuggestion]

    enum CodingKeys: String, CodingKey {
        case companies
        case targetProfileId = "target_profile_id"
        case decisionFilter = "decision_filter"
        case connectionFilter = "connection_filter"
        case connectionCount = "connection_count"
        case catalogRefreshedAt = "catalog_refreshed_at"
        case fitReviewAvailable = "fit_review_available"
        case profileSummary = "profile_summary"
        case rulesPreviewJobs = "rules_preview_jobs"
        case rulesPreviewCompanies = "rules_preview_companies"
        case referralNetwork = "referral_network"
        case unreviewedJobs = "unreviewed_jobs"
        case resumeSections = "resume_sections"
        case resumeSuggestions = "resume_suggestions"
    }

    public init(
        targetProfileId: Int,
        decisionFilter: String,
        connectionFilter: String,
        connectionCount: Int,
        catalogRefreshedAt: String?,
        fitReviewAvailable: Bool,
        profileSummary: ProfileSummary,
        companies: [CompanyGroup],
        rulesPreviewJobs: [RulesPreviewJob],
        rulesPreviewCompanies: [RulesPreviewCompany] = [],
        referralNetwork: [CatalogMatch] = [],
        unreviewedJobs: [UnreviewedJob],
        resumeSections: [ResumeSection],
        resumeSuggestions: [ResumeSuggestion]
    ) {
        self.targetProfileId = targetProfileId
        self.decisionFilter = decisionFilter
        self.connectionFilter = connectionFilter
        self.connectionCount = connectionCount
        self.catalogRefreshedAt = catalogRefreshedAt
        self.fitReviewAvailable = fitReviewAvailable
        self.profileSummary = profileSummary
        self.companies = companies
        self.rulesPreviewJobs = rulesPreviewJobs
        self.rulesPreviewCompanies = rulesPreviewCompanies
        self.referralNetwork = referralNetwork
        self.unreviewedJobs = unreviewedJobs
        self.resumeSections = resumeSections
        self.resumeSuggestions = resumeSuggestions
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        targetProfileId = try container.decode(Int.self, forKey: .targetProfileId)
        decisionFilter = try container.decode(String.self, forKey: .decisionFilter)
        connectionFilter = try container.decode(String.self, forKey: .connectionFilter)
        connectionCount = try container.decode(Int.self, forKey: .connectionCount)
        catalogRefreshedAt = try container.decodeIfPresent(String.self, forKey: .catalogRefreshedAt)
        fitReviewAvailable = try container.decode(Bool.self, forKey: .fitReviewAvailable)
        profileSummary = try container.decode(ProfileSummary.self, forKey: .profileSummary)
        companies = try container.decode([CompanyGroup].self, forKey: .companies)
        rulesPreviewJobs = try container.decode([RulesPreviewJob].self, forKey: .rulesPreviewJobs)
        rulesPreviewCompanies = try container.decodeIfPresent(
            [RulesPreviewCompany].self,
            forKey: .rulesPreviewCompanies
        ) ?? []
        referralNetwork = try container.decodeIfPresent([CatalogMatch].self, forKey: .referralNetwork) ?? []
        unreviewedJobs = try container.decode([UnreviewedJob].self, forKey: .unreviewedJobs)
        resumeSections = try container.decode([ResumeSection].self, forKey: .resumeSections)
        resumeSuggestions = try container.decode([ResumeSuggestion].self, forKey: .resumeSuggestions)
    }
}

public struct LLMUsageRequest: Codable, Sendable, Identifiable {
    public let id: Int
    public let provider: String
    public let model: String
    public let feature: String
    public let status: String
    public let error: String?
    public let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id, provider, model, feature, status, error
        case createdAt = "created_at"
    }
}

public struct LLMUsageResponse: Codable, Sendable {
    public let totalRequests: Int
    public let requestsToday: Int
    public let byFeature: [String: [String: Int]]
    public let recentRequests: [LLMUsageRequest]

    enum CodingKeys: String, CodingKey {
        case byFeature = "by_feature"
        case totalRequests = "total_requests"
        case requestsToday = "requests_today"
        case recentRequests = "recent_requests"
    }
}

public struct JobDetail: Codable, Sendable, Identifiable {
    public let id: Int
    public let title: String
    public let companyName: String
    public let department: String?
    public let locationText: String?
    public let remoteMode: String?
    public let employmentType: String?
    public let seniority: String?
    public let descriptionText: String?
    public let requirementsText: String?
    public let applyURL: String?
    public let sourceURL: String
    public let status: String
    public let fitScore: Int?
    public let label: String?
    public let reasons: [String]
    public let risks: [String]
    public let recommendation: String?
    public let decision: String?
    public let notes: String

    enum CodingKeys: String, CodingKey {
        case id, title, status, label, reasons, risks, recommendation, decision, notes, seniority
        case companyName = "company_name"
        case department
        case locationText = "location_text"
        case remoteMode = "remote_mode"
        case employmentType = "employment_type"
        case descriptionText = "description_text"
        case requirementsText = "requirements_text"
        case applyURL = "apply_url"
        case sourceURL = "source_url"
        case fitScore = "fit_score"
    }
}

public struct ReferralContact: Codable, Sendable, Identifiable {
    public let id: Int
    public let name: String
    public let email: String
    public let title: String
    public let notes: String
    public let relationship: String
}

public struct ApplicationPacketDetail: Codable, Sendable {
    public let company: String
    public let title: String
    public let applyURL: String?
    public let sourceURL: String?
    public let fitScore: Int?
    public let label: String?
    public let recommendation: String?
    public let reasons: [String]
    public let risks: [String]
    public let notes: String?

    enum CodingKeys: String, CodingKey {
        case company, title, label, recommendation, reasons, risks, notes
        case applyURL = "apply_url"
        case sourceURL = "source_url"
        case fitScore = "fit_score"
    }
}

public struct ChecklistItem: Codable, Sendable, Identifiable {
    public let id: String
    public let label: String
    public let done: Bool
    public let url: String?
}

public struct ApplicationPacket: Decodable, Sendable, Identifiable {
    public let id: Int
    public let status: String
    public let manualSubmitURL: String?
    public let updatedAt: String?
    public let packet: ApplicationPacketDetail?
    public let checklist: [ChecklistItem]

    enum CodingKeys: String, CodingKey {
        case id, status, packet, checklist
        case manualSubmitURL = "manual_submit_url"
        case updatedAt = "updated_at"
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(Int.self, forKey: .id)
        status = try container.decode(String.self, forKey: .status)
        manualSubmitURL = try container.decodeIfPresent(String.self, forKey: .manualSubmitURL)
        updatedAt = try container.decodeIfPresent(String.self, forKey: .updatedAt)
        packet = try container.decodeIfPresent(ApplicationPacketDetail.self, forKey: .packet)
        checklist = try container.decodeIfPresent([ChecklistItem].self, forKey: .checklist) ?? []
    }
}

public struct MatchRunSummary: Sendable {
    public let title: String
    public let lines: [String]
}

extension FindMatchesResponse {
    public var runSummary: MatchRunSummary? {
        guard let fields = refreshSummary else { return nil }
        func intValue(_ key: String, in source: [String: JSONValue]) -> Int {
            guard let value = source[key] else { return 0 }
            if case .int(let number) = value { return number }
            if case .double(let number) = value { return Int(number) }
            return 0
        }
        let reviewsCreated: Int = {
            guard let review else { return 0 }
            if case .array(let ids) = review["review_ids"] { return ids.count }
            return intValue("reviews_created", in: review)
        }()
        let lines = [
            "Sources attempted: \(intValue("sources_attempted", in: fields))",
            "Sources succeeded: \(intValue("sources_succeeded", in: fields))",
            "Jobs seen: \(intValue("jobs_seen", in: fields))",
            "Jobs closed: \(intValue("jobs_closed", in: fields))",
            "Reviews created: \(reviewsCreated)",
            "Failures: \(intValue("failures", in: fields))",
        ]
        return MatchRunSummary(title: status == "refresh_only" ? "Catalog refresh" : "Match run", lines: lines)
    }
}

public struct JobDetailResponse: Decodable, Sendable {
    public let job: JobDetail
    public let linkedinConnections: [LinkedInConnection]
    public let referralContacts: [ReferralContact]
    public let applicationPacket: ApplicationPacket?

    enum CodingKeys: String, CodingKey {
        case job
        case linkedinConnections = "linkedin_connections"
        case referralContacts = "referral_contacts"
        case applicationPacket = "application_packet"
    }
}

public struct SavedJob: Codable, Sendable, Identifiable {
    public var id: Int { jobId }
    public let jobId: Int
    public let company: String
    public let title: String
    public let fitScore: Int?
    public let label: String
    public let recommendation: String
    public let applyURL: String
    public let sourceURL: String
    public let packetStatus: String
    public let manualSubmitURL: String
    public let decision: String
    public let notes: String
    public let decidedAt: String?
    public var referralContacts: [ReferralContact]?

    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"
        case company, title, label, recommendation, decision, notes
        case fitScore = "fit_score"
        case applyURL = "apply_url"
        case sourceURL = "source_url"
        case packetStatus = "packet_status"
        case manualSubmitURL = "manual_submit_url"
        case decidedAt = "decided_at"
        case referralContacts = "referral_contacts"
    }
}

public struct SavedJobsResponse: Codable, Sendable {
    public let targetProfileId: Int
    public let query: String
    public let sort: String
    public let savedJobs: [SavedJob]
    public let hasSavedJobs: Bool

    enum CodingKeys: String, CodingKey {
        case query, sort
        case targetProfileId = "target_profile_id"
        case savedJobs = "saved_jobs"
        case hasSavedJobs = "has_saved_jobs"
    }
}

public struct ConnectionsGroup: Codable, Sendable, Identifiable {
    public var id: String { company }
    public let company: String
    public let connections: [LinkedInConnection]
}

public struct CatalogMatch: Codable, Sendable, Identifiable {
    public var id: Int { companyId }
    public let companyId: Int
    public let companyName: String
    public let connections: [LinkedInConnection]

    enum CodingKeys: String, CodingKey {
        case connections
        case companyId = "company_id"
        case companyName = "company_name"
    }
}

public struct ConnectionsResponse: Codable, Sendable {
    public let connectionCount: Int
    public let groupedCompanies: [ConnectionsGroup]
    public let matchedCatalog: [CatalogMatch]

    enum CodingKeys: String, CodingKey {
        case connectionCount = "connection_count"
        case groupedCompanies = "grouped_companies"
        case matchedCatalog = "matched_catalog"
    }
}

public struct ImportConnectionsResponse: Codable, Sendable {
    public let status: String
    public let imported: Int
    public let updated: Int
    public let skipped: Int
}

public struct SourceHealthRow: Codable, Sendable, Identifiable {
    public let id: Int
    public let companyName: String
    public let url: String
    public let sourceType: String
    public let healthStatus: String
    public let healthStatusLabel: String
    public let adapterStatusLabel: String
    public let activeJobCount: Int
    public let latestRecommendation: String

    enum CodingKeys: String, CodingKey {
        case id, url
        case companyName = "company_name"
        case sourceType = "source_type"
        case healthStatus = "health_status"
        case healthStatusLabel = "health_status_label"
        case adapterStatusLabel = "adapter_status_label"
        case activeJobCount = "active_job_count"
        case latestRecommendation = "latest_recommendation"
    }
}

public struct SourceReviewRow: Codable, Sendable, Identifiable {
    public let id: Int
    public let companyName: String
    public let requestedURL: String
    public let reason: String
    public let status: String

    enum CodingKeys: String, CodingKey {
        case id, reason, status
        case companyName = "company_name"
        case requestedURL = "requested_url"
    }
}

public struct SourceSupportSummary: Codable, Sendable {
    public let total: Int
    public let ready: Int
    public let unsupported: Int
    public let disabled: Int
}

public struct AdminSourcesResponse: Codable, Sendable {
    public let sources: [SourceHealthRow]
    public let sourceReviews: [SourceReviewRow]
    public let supportSummary: SourceSupportSummary

    enum CodingKeys: String, CodingKey {
        case sources
        case sourceReviews = "source_reviews"
        case supportSummary = "support_summary"
    }
}

public struct FindMatchesResponse: Codable, Sendable {
    public let status: String
    public let refreshSummary: [String: JSONValue]?
    public let review: [String: JSONValue]?

    enum CodingKeys: String, CodingKey {
        case status, review
        case refreshSummary = "refresh_summary"
    }
}

public enum JSONValue: Codable, Sendable {
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)
    case array([JSONValue])
    case object([String: JSONValue])
    case null

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Int.self) {
            self = .int(value)
        } else if let value = try? container.decode(Double.self) {
            self = .double(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else if let value = try? container.decode([String: JSONValue].self) {
            self = .object(value)
        } else {
            self = .null
        }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value): try container.encode(value)
        case .int(let value): try container.encode(value)
        case .double(let value): try container.encode(value)
        case .bool(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        case .object(let value): try container.encode(value)
        case .null: try container.encodeNil()
        }
    }
}