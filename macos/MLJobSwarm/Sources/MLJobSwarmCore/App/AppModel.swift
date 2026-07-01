import AppKit
import Foundation
import UniformTypeIdentifiers

public enum AppSection: String, CaseIterable, Identifiable, Sendable {
    case dashboard
    case savedJobs
    case connections
    case onboarding
    case adminSources
    case llmSettings

    public var id: String { rawValue }

    public var title: String {
        switch self {
        case .dashboard: return "Dashboard"
        case .savedJobs: return "Saved jobs"
        case .connections: return "Connections"
        case .onboarding: return "Onboarding"
        case .adminSources: return "Source health"
        case .llmSettings: return "LLM settings"
        }
    }

    public var symbol: String {
        switch self {
        case .dashboard: return "briefcase"
        case .savedJobs: return "bookmark"
        case .connections: return "person.2"
        case .onboarding: return "doc.text"
        case .adminSources: return "antenna.radiowaves.left.and.right"
        case .llmSettings: return "key"
        }
    }
}

@MainActor
public final class AppModel: ObservableObject {
    @Published public var selectedSection: AppSection = .dashboard
    @Published public var profiles: [ProfileListItem] = []
    @Published public var selectedProfileID: Int?
    @Published public var decisionFilter = "all"
    @Published public var connectionFilter = "all"
    @Published public var dashboard: DashboardResponse?
    @Published public var savedJobs: SavedJobsResponse?
    @Published public var connections: ConnectionsResponse?
    @Published public var adminSources: AdminSourcesResponse?
    @Published public var onboardingState: OnboardingState?
    @Published public var resumeAssetID: Int?
    @Published public var selectedJobID: Int?
    @Published public var jobDetail: JobDetailResponse?
    @Published public var statusMessage = ""
    @Published public var isLoading = false
    @Published public var isWorking = false
    @Published public var llmConsent = false
    @Published public var needsOnboarding = false
    @Published public var lastRunSummary: MatchRunSummary?
    @Published public var llmAvailable = false
    @Published public var llmSettings = LLMPreferences()
    @Published public var hasStoredLLMKey = false
    @Published public var llmKeyImportSource: String?
    @Published public var llmUsage: LLMUsageResponse?

    public let backend: BackendManager
    private let llmSettingsStore = LLMSettingsStore.shared

    public init(backend: BackendManager) {
        self.backend = backend
    }

    public func bootstrap() async {
        llmSettings = llmSettingsStore.loadPreferences()
        let importResult = llmSettingsStore.importLegacyAPIKeyIfNeeded()
        hasStoredLLMKey = llmSettingsStore.hasStoredAPIKey()
        llmKeyImportSource = llmSettingsStore.importedKeySourcePath()
        if importResult.imported, let source = importResult.sourcePath {
            statusMessage = "Imported OpenRouter API key from legacy .env (\(source))."
        }
        await backend.start()
        guard backend.isReady else { return }
        await refreshLLMStatus()
        await loadLLMUsage()
        await loadProfiles()
        if needsOnboarding {
            selectedSection = .onboarding
        }
        await refreshCurrentSection()
    }

    public func loadProfiles() async {
        do {
            let health = try await backend.apiClient.health()
            let response = try await backend.apiClient.profiles()
            profiles = response.profiles
            needsOnboarding = (health.profileCount ?? response.profiles.count) == 0
            if selectedProfileID == nil {
                selectedProfileID = response.profiles.first?.id
            }
            if selectedProfileID == nil {
                selectedSection = .onboarding
            }
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func restartBackend() async {
        isLoading = true
        defer { isLoading = false }
        await backend.restart()
        guard backend.isReady else { return }
        await refreshLLMStatus()
        await loadLLMUsage()
        await loadProfiles()
        await refreshCurrentSection()
    }

    public func refreshCurrentSection() async {
        switch selectedSection {
        case .dashboard:
            await loadDashboard()
        case .savedJobs:
            await loadSavedJobs()
        case .connections:
            await loadConnections()
        case .onboarding:
            await loadOnboarding()
        case .adminSources:
            await loadAdminSources()
        case .llmSettings:
            await refreshLLMStatus()
            await loadLLMUsage()
        }
    }

    public func loadLLMUsage() async {
        guard backend.isReady else {
            llmUsage = nil
            return
        }
        do {
            llmUsage = try await backend.apiClient.llmUsage()
        } catch {
            llmUsage = nil
        }
    }

    public func refreshLLMStatus() async {
        guard backend.isReady else {
            llmAvailable = false
            return
        }
        do {
            let health = try await backend.apiClient.health()
            llmAvailable = health.fitReviewAvailable
        } catch {
            llmAvailable = false
        }
    }

    public func saveLLMSettings(apiKey: String?, preferences: LLMPreferences) async {
        isWorking = true
        defer { isWorking = false }
        do {
            try llmSettingsStore.save(apiKey: apiKey, preferences: preferences)
            llmSettings = preferences
            hasStoredLLMKey = llmSettingsStore.hasStoredAPIKey()
            statusMessage = "LLM settings saved. Restarting backend…"
            await backend.restart()
            guard backend.isReady else {
                statusMessage = backend.status
                llmAvailable = false
                return
            }
            await refreshLLMStatus()
            await loadLLMUsage()
            await loadProfiles()
            await refreshCurrentSection()
            statusMessage = llmAvailable
                ? "LLM fit review is ready."
                : "Backend restarted. Add an OpenRouter API key to enable fit review."
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func clearLLMSettings() async {
        isWorking = true
        defer { isWorking = false }
        do {
            try llmSettingsStore.clearAPIKey()
            hasStoredLLMKey = false
            statusMessage = "API key removed. Restarting backend…"
            await backend.restart()
            await refreshLLMStatus()
            statusMessage = "LLM API key cleared."
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func loadOnboarding() async {
        isLoading = true
        defer { isLoading = false }
        do {
            onboardingState = try await backend.apiClient.onboardingState(
                resumeAssetID: resumeAssetID
            )
            statusMessage = ""
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func consentVisionFallback(consent: Bool) async {
        guard let resumeAssetID else {
            statusMessage = "Upload a resume first."
            return
        }
        isWorking = true
        defer { isWorking = false }
        do {
            let result = try await backend.apiClient.consentVisionFallback(
                resumeAssetID: resumeAssetID,
                consent: consent
            )
            if consent {
                statusMessage = result.needsVisionFallback
                    ? "Vision fallback completed but parsing still needs review."
                    : "Vision fallback completed."
            } else {
                statusMessage = "Vision fallback declined. Continue with extracted content."
            }
            await loadOnboarding()
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func uploadResume(from url: URL) async {
        isWorking = true
        defer { isWorking = false }
        let accessed = url.startAccessingSecurityScopedResource()
        defer {
            if accessed {
                url.stopAccessingSecurityScopedResource()
            }
        }
        do {
            let result = try await backend.apiClient.uploadResume(fileURL: url)
            resumeAssetID = result.resumeAssetId
            if result.needsVisionFallback {
                statusMessage = "Resume uploaded. Vision fallback may be needed for low-confidence parsing."
            } else {
                statusMessage = "Resume uploaded successfully."
            }
            await loadOnboarding()
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func completeOnboarding(
        role: String,
        level: String,
        location: String,
        workMode: String,
        companyStage: String
    ) async {
        guard let resumeAssetID else {
            statusMessage = "Upload a resume first."
            return
        }
        isWorking = true
        defer { isWorking = false }
        do {
            let result = try await backend.apiClient.createProfile(
                resumeAssetID: resumeAssetID,
                role: role,
                level: level,
                location: location,
                workMode: workMode,
                companyStage: companyStage
            )
            selectedProfileID = result.targetProfileId
            needsOnboarding = false
            selectedSection = .dashboard
            statusMessage = "Profile created. Refresh sources to find matches."
            await loadProfiles()
            await loadDashboard()
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func updatePreferences(
        role: String,
        level: String,
        location: String,
        workMode: String,
        companyStage: String
    ) async {
        guard let profileID = selectedProfileID else { return }
        isWorking = true
        defer { isWorking = false }
        do {
            let result = try await backend.apiClient.updateProfilePreferences(
                targetProfileID: profileID,
                role: role,
                level: level,
                location: location,
                workMode: workMode,
                companyStage: companyStage
            )
            statusMessage = "Preferences updated to version \(result.version)."
            await loadProfiles()
            await loadDashboard()
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func loadDashboard() async {
        guard let profileID = selectedProfileID else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            dashboard = try await backend.apiClient.dashboard(
                targetProfileID: profileID,
                decisionFilter: decisionFilter,
                connectionFilter: connectionFilter
            )
            statusMessage = ""
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func loadSavedJobs(query: String = "", sort: String = "recent") async {
        guard let profileID = selectedProfileID else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            savedJobs = try await backend.apiClient.savedJobs(
                targetProfileID: profileID,
                query: query,
                sort: sort
            )
            statusMessage = ""
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func exportSavedJobsCSV(query: String = "", sort: String = "recent") async {
        guard let profileID = selectedProfileID else { return }
        isWorking = true
        defer { isWorking = false }
        do {
            let data = try await backend.apiClient.exportSavedJobsCSV(
                targetProfileID: profileID,
                query: query,
                sort: sort
            )
            let panel = NSSavePanel()
            panel.allowedContentTypes = [.commaSeparatedText]
            panel.nameFieldStringValue = "saved-jobs.csv"
            panel.canCreateDirectories = true
            if panel.runModal() == .OK, let url = panel.url {
                try data.write(to: url)
                statusMessage = "Exported saved jobs CSV."
            }
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func loadConnections(search: String = "") async {
        isLoading = true
        defer { isLoading = false }
        do {
            connections = try await backend.apiClient.connections(search: search)
            statusMessage = ""
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func loadAdminSources() async {
        isLoading = true
        defer { isLoading = false }
        do {
            adminSources = try await backend.apiClient.adminSources()
            statusMessage = ""
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func openJob(_ jobID: Int) async {
        guard let profileID = selectedProfileID else { return }
        selectedJobID = jobID
        isWorking = true
        defer { isWorking = false }
        do {
            jobDetail = try await backend.apiClient.jobDetail(jobID: jobID, targetProfileID: profileID)
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func setDecision(jobID: Int, decision: String, notes: String = "") async {
        guard let profileID = selectedProfileID else { return }
        isWorking = true
        defer { isWorking = false }
        do {
            try await backend.apiClient.setDecision(
                jobID: jobID,
                targetProfileID: profileID,
                decision: decision,
                notes: notes
            )
            await loadDashboard()
            if selectedSection == .savedJobs {
                await loadSavedJobs()
            }
            if selectedJobID == jobID {
                await openJob(jobID)
            }
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func addReferralContact(
        jobID: Int,
        name: String,
        email: String = "",
        title: String = "",
        relationship: String = "",
        notes: String = ""
    ) async {
        guard let profileID = selectedProfileID else { return }
        isWorking = true
        defer { isWorking = false }
        do {
            try await backend.apiClient.addReferralContact(
                jobID: jobID,
                targetProfileID: profileID,
                name: name,
                email: email,
                title: title,
                relationship: relationship,
                notes: notes
            )
            await openJob(jobID)
            statusMessage = "Referral contact added."
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func prepareApplicationPacket(jobID: Int) async {
        guard let profileID = selectedProfileID else { return }
        isWorking = true
        defer { isWorking = false }
        do {
            jobDetail = try await backend.apiClient.prepareApplicationPacket(
                jobID: jobID,
                targetProfileID: profileID
            )
            statusMessage = "Application packet prepared."
            if selectedSection == .savedJobs {
                await loadSavedJobs()
            }
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func markPacketSubmitted(packetID: Int) async {
        guard let profileID = selectedProfileID else { return }
        isWorking = true
        defer { isWorking = false }
        do {
            try await backend.apiClient.updatePacketStatus(
                packetID: packetID,
                targetProfileID: profileID,
                status: "submitted"
            )
            if let jobID = selectedJobID {
                await openJob(jobID)
            }
            if selectedSection == .savedJobs {
                await loadSavedJobs()
            }
            statusMessage = "Marked as submitted."
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func importConnections(from url: URL) async {
        isWorking = true
        defer { isWorking = false }
        let accessed = url.startAccessingSecurityScopedResource()
        defer {
            if accessed {
                url.stopAccessingSecurityScopedResource()
            }
        }
        do {
            let result = try await backend.apiClient.importConnections(fileURL: url)
            statusMessage = "Imported \(result.imported), updated \(result.updated)"
            await loadConnections()
            if selectedSection == .dashboard {
                await loadDashboard()
            }
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func refreshSources() async {
        guard let profileID = selectedProfileID else { return }
        isWorking = true
        defer { isWorking = false }
        do {
            let result = try await backend.apiClient.refreshSources(targetProfileID: profileID)
            lastRunSummary = result.runSummary
            statusMessage = "Catalog refreshed"
            await loadDashboard()
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func findMatches() async {
        guard let profileID = selectedProfileID else { return }
        guard llmConsent else {
            statusMessage = "Check LLM consent before running fit review."
            return
        }
        isWorking = true
        defer { isWorking = false }
        do {
            let result = try await backend.apiClient.findMatches(
                targetProfileID: profileID,
                llmConsent: true
            )
            lastRunSummary = result.runSummary
            if result.status == "refresh_only" {
                statusMessage = "Sources refreshed. Fit review provider is not configured."
            } else {
                statusMessage = "Matches refreshed and fit review completed."
            }
            await loadLLMUsage()
            await loadDashboard()
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func reviewJobsOnly() async {
        guard let profileID = selectedProfileID else { return }
        guard llmConsent else {
            statusMessage = "Check LLM consent before running fit review."
            return
        }
        isWorking = true
        defer { isWorking = false }
        do {
            let result = try await backend.apiClient.reviewJobs(
                targetProfileID: profileID,
                llmConsent: true
            )
            lastRunSummary = result.runSummary
            if let failures = result.review.flatMap({ review in
                if case .int(let count) = review["failures"] { return count }
                return nil
            }), failures > 0 {
                statusMessage = "Fit review completed with \(failures) failure(s)."
            } else {
                statusMessage = "Fit review completed."
            }
            await loadLLMUsage()
            await loadDashboard()
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func selectProfile(_ profileID: Int) async {
        selectedProfileID = profileID
        await refreshCurrentSection()
    }

    public func rewriteResumeSection(sectionID: Int, jobID: Int? = nil) async {
        guard let profileID = selectedProfileID else { return }
        guard llmConsent else {
            statusMessage = "Check LLM consent before requesting resume rewrites."
            return
        }
        isWorking = true
        defer { isWorking = false }
        do {
            _ = try await backend.apiClient.rewriteResumeSection(
                targetProfileID: profileID,
                sectionID: sectionID,
                jobID: jobID,
                llmConsent: true
            )
            statusMessage = "Resume rewrite suggestion created."
            await loadDashboard()
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func updateSuggestionStatus(suggestionID: Int, accepted: Bool) async {
        guard let profileID = selectedProfileID else { return }
        isWorking = true
        defer { isWorking = false }
        do {
            try await backend.apiClient.updateSuggestionStatus(
                suggestionID: suggestionID,
                targetProfileID: profileID,
                accepted: accepted
            )
            statusMessage = accepted ? "Suggestion accepted." : "Suggestion rejected."
            await loadDashboard()
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func refreshAllAdminSources() async {
        isWorking = true
        defer { isWorking = false }
        do {
            try await backend.apiClient.refreshAllAdminSources()
            statusMessage = "Admin source refresh completed."
            await loadAdminSources()
            if selectedSection == .dashboard {
                await loadDashboard()
            }
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func refreshAdminSource(sourceID: Int) async {
        isWorking = true
        defer { isWorking = false }
        do {
            try await backend.apiClient.refreshAdminSource(sourceID: sourceID)
            statusMessage = "Source refreshed."
            await loadAdminSources()
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func approveSourceReview(queueID: Int) async {
        isWorking = true
        defer { isWorking = false }
        do {
            try await backend.apiClient.approveSourceReview(queueID: queueID)
            statusMessage = "Source review approved."
            await loadAdminSources()
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    public func rejectSourceReview(queueID: Int) async {
        isWorking = true
        defer { isWorking = false }
        do {
            try await backend.apiClient.rejectSourceReview(queueID: queueID)
            statusMessage = "Source review rejected."
            await loadAdminSources()
        } catch {
            statusMessage = error.localizedDescription
        }
    }
}