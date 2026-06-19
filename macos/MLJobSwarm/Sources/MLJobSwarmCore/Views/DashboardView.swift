import SnapshotPreferences
import SwiftUI

public struct DashboardView: View {
    @ObservedObject private var model: AppModel

    public init(model: AppModel) {
        self.model = model
    }

    public var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header
                if shouldShowFirstRunChecklist {
                    FirstRunChecklistView(model: model)
                }
                if let dashboard = model.dashboard {
                    commandCenter(dashboard)
                    if let summary = model.lastRunSummary {
                        runSummaryPanel(summary)
                    }
                    filters
                    stats(for: dashboard)
                    if !dashboard.fitReviewAvailable {
                        llmUnavailableNotice
                    }
                    if !dashboard.referralNetwork.isEmpty {
                        referralNetworkSection(dashboard.referralNetwork)
                    }
                    if !dashboard.unreviewedJobs.isEmpty {
                        unreviewedSection(dashboard.unreviewedJobs)
                    }
                    if dashboard.companies.isEmpty && !dashboard.rulesPreviewCompanies.isEmpty {
                        rulesPreviewCompaniesSection(dashboard.rulesPreviewCompanies)
                    } else if !dashboard.rulesPreviewJobs.isEmpty {
                        rulesPreviewSection(dashboard.rulesPreviewJobs)
                    }
                    profileSidebar(dashboard.profileSummary, dashboard: dashboard)
                    companyList(dashboard.companies)
                } else if model.isLoading {
                    ProgressView("Loading matches…")
                } else if model.needsOnboarding {
                    ContentUnavailableView(
                        "Complete onboarding first",
                        systemImage: "doc.text",
                        description: Text("Upload a resume and set preferences to start matching.")
                    )
                } else {
                    ContentUnavailableView("No profile selected", systemImage: "person.crop.circle.badge.questionmark")
                }
                if !model.statusMessage.isEmpty {
                    Text(model.statusMessage)
                        .font(.footnote)
                        .foregroundStyle(AppTheme.muted)
                }
            }
            .padding(24)
        }
        .navigationTitle("Job matches")
        .toolbar {
            ToolbarItemGroup {
                Button {
                    Task { await model.refreshSources() }
                } label: {
                    Label("Refresh careers catalog", systemImage: "arrow.clockwise")
                }
                Button {
                    Task { await model.loadDashboard() }
                } label: {
                    Label("Reload dashboard", systemImage: "arrow.counterclockwise")
                }
            }
        }
        .sheet(item: Binding(
            get: { model.selectedJobID.map(DashboardJobSheetItem.init) },
            set: { model.selectedJobID = $0?.id }
        )) { item in
            JobDetailView(model: model, jobID: item.id)
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Matching workspace")
                .font(.caption.weight(.semibold))
                .foregroundStyle(AppTheme.muted)
            if let refreshed = model.dashboard?.catalogRefreshedAt {
                Text("Catalog refreshed: \(refreshed)")
                    .font(.caption)
                    .foregroundStyle(AppTheme.muted)
            } else {
                Text("Focus on companies where you have a referral path.")
                    .foregroundStyle(AppTheme.muted)
            }
        }
    }

    private func commandCenter(_ dashboard: DashboardResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Operator queue")
                .font(.headline)
            HStack(spacing: 12) {
                commandCard(
                    title: "Refresh careers catalog",
                    detail: "Pulls open roles from reviewed careers pages and ATS boards. This grows your job list, not your referral-network company count — that only increases when more catalog companies match your LinkedIn connections (expand seed data or aliases in Source health).",
                    actionTitle: "Refresh all careers",
                    action: { Task { await model.refreshSources() } }
                )
                VStack(alignment: .leading, spacing: 8) {
                    Text("Rules + fit review")
                        .font(.subheadline.bold())
                        .foregroundStyle(AppTheme.textPrimary)
                    Toggle("LLM consent for fit review", isOn: $model.llmConsent)
                        .font(.caption)
                    HStack {
                        Button("Find matches") {
                            Task { await model.findMatches() }
                        }
                        .appProminentButton()
                        .disabled(!dashboard.fitReviewAvailable)
                        Button("Fit review only") {
                            Task { await model.reviewJobsOnly() }
                        }
                        .appBorderedButton()
                        .disabled(!dashboard.fitReviewAvailable)
                    }
                }
                .surfaceCardStyle()
            }
        }
    }

    private func commandCard(
        title: String,
        detail: String,
        actionTitle: String,
        action: @escaping () -> Void
    ) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.subheadline.bold())
            Text(detail)
                .font(.caption)
                .foregroundStyle(AppTheme.muted)
            Button(actionTitle, action: action)
                .appProminentButton()
        }
        .surfaceCardStyle()
    }

    private func referralNetworkSection(_ matches: [CatalogMatch]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Referral network (\(matches.count) companies)")
                    .font(.headline)
                    .foregroundStyle(AppTheme.textPrimary)
                Spacer()
                Button("Refresh all careers") {
                    Task { await model.refreshSources() }
                }
                .appBorderedButton()
            }
            Text("Each company here is a catalog entry with at least one LinkedIn connection match. To grow this count, add companies or aliases to the seed catalog (Source health), then restart the app — re-importing Connections.csv is not required. Refresh careers only updates open jobs for companies already in the catalog.")
                .font(.caption)
                .foregroundStyle(AppTheme.muted)
            ForEach(matches) { match in
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text(match.companyName)
                            .font(.subheadline.bold())
                            .foregroundStyle(AppTheme.textPrimary)
                        Spacer()
                        Text("\(match.connections.count) connection(s)")
                            .font(.caption)
                            .foregroundStyle(AppTheme.referral)
                    }
                    Text(match.connections.prefix(3).map(\.fullName).joined(separator: ", "))
                        .font(.caption2)
                        .foregroundStyle(AppTheme.muted)
                    if match.connections.count > 3 {
                        Text("+\(match.connections.count - 3) more contacts")
                            .font(.caption2)
                            .foregroundStyle(AppTheme.muted)
                    }
                }
                .surfaceCardStyle()
            }
        }
    }

    private var llmUnavailableNotice: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("LLM fit review unavailable")
                .font(.subheadline.bold())
            Text("Public source refresh works without an API key. Configure the fit-review provider to enable scoring.")
                .font(.caption)
                .foregroundStyle(AppTheme.muted)
        }
        .surfaceCardStyle()
    }

    private var filters: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Filter matches")
                .font(.headline)
                .foregroundStyle(AppTheme.textPrimary)
            Text("Decision controls which jobs you have marked. Connection narrows the company list to places where your imported LinkedIn contacts work.")
                .font(.caption)
                .foregroundStyle(AppTheme.muted)
            VStack(alignment: .leading, spacing: 8) {
                Text("Decision status")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(AppTheme.textPrimary)
                HStack(spacing: 8) {
                    filterChip("All jobs", tag: "all", selection: $model.decisionFilter)
                    filterChip("Saved", tag: "saved", selection: $model.decisionFilter)
                    filterChip("Unmarked", tag: "unmarked", selection: $model.decisionFilter)
                    filterChip("Hidden", tag: "hidden", selection: $model.decisionFilter)
                }
            }
            VStack(alignment: .leading, spacing: 8) {
                Text("Referral network")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(AppTheme.textPrimary)
                HStack(spacing: 8) {
                    filterChip("All companies", tag: "all", selection: $model.connectionFilter)
                    filterChip("With LinkedIn connections", tag: "with_connections", selection: $model.connectionFilter)
                }
            }
            Text(activeFilterSummary)
                .font(.caption2)
                .foregroundStyle(AppTheme.muted)
        }
        .surfaceCardStyle()
    }

    private var activeFilterSummary: String {
        let decisionLabel: String
        switch model.decisionFilter {
        case "saved": decisionLabel = "saved jobs only"
        case "unmarked": decisionLabel = "unmarked jobs only"
        case "hidden": decisionLabel = "hidden jobs only"
        default: decisionLabel = "all decision states"
        }
        let connectionLabel = model.connectionFilter == "with_connections"
            ? "companies with LinkedIn matches"
            : "all catalog companies"
        return "Showing \(decisionLabel) across \(connectionLabel)."
    }

    private func filterChip(
        _ title: String,
        tag: String,
        selection: Binding<String>
    ) -> some View {
        Button(title) {
            selection.wrappedValue = tag
            Task { await model.loadDashboard() }
        }
        .appFilterChip(selected: selection.wrappedValue == tag)
    }

    private func stats(for dashboard: DashboardResponse) -> some View {
        HStack(spacing: 12) {
            statCard("Visible companies", value: "\(dashboard.companies.count)")
            statCard("Network matches", value: "\(networkMatches(in: dashboard.companies))")
            statCard("Waiting review", value: "\(dashboard.unreviewedJobs.count)")
            statCard("Connections", value: "\(dashboard.connectionCount)")
            statCard("Fit review", value: dashboard.fitReviewAvailable ? "Ready" : "Paused")
        }
    }

    private func unreviewedSection(_ jobs: [UnreviewedJob]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Jobs waiting for fit review")
                .font(.headline)
            ForEach(jobs) { job in
                HStack {
                    VStack(alignment: .leading) {
                        Button(job.title) { Task { await model.openJob(job.jobId) } }
                            .appLinkButton()
                        Text("\(job.companyName) · \(job.locationText ?? "—")")
                            .font(.caption)
                            .foregroundStyle(AppTheme.muted)
                    }
                    Spacer()
                    Button("Save job") { Task { await model.setDecision(jobID: job.jobId, decision: "saved") } }
                        .appBorderedButton()
                    Button("Hide job") { Task { await model.setDecision(jobID: job.jobId, decision: "hidden") } }
                        .appBorderedButton()
                }
                .font(.subheadline)
            }
        }
        .surfaceCardStyle()
    }

    private func rulesPreviewCompaniesSection(_ companies: [RulesPreviewCompany]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Rules matches with referral paths (\(companies.count) companies)")
                .font(.headline)
                .foregroundStyle(AppTheme.textPrimary)
            Text("No LLM fit review yet. These are rules-filtered jobs from the current catalog — not your full referral network above.")
                .font(.caption)
                .foregroundStyle(AppTheme.muted)
            ForEach(companies) { company in
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text(company.companyName)
                            .font(.subheadline.bold())
                        Spacer()
                        if company.connectionCount > 0 {
                            Text("\(company.connectionCount) connection(s)")
                                .font(.caption)
                                .foregroundStyle(AppTheme.referral)
                        }
                    }
                    if !company.linkedinConnections.isEmpty {
                        Text(company.linkedinConnections.prefix(2).map(\.fullName).joined(separator: ", "))
                            .font(.caption2)
                            .foregroundStyle(AppTheme.muted)
                    }
                    ForEach(company.jobs) { job in
                        HStack {
                            VStack(alignment: .leading) {
                                Button(job.title) { Task { await model.openJob(job.jobId) } }
                                    .appLinkButton()
                                Text("Rules score \(job.score)")
                                    .font(.caption)
                                    .foregroundStyle(AppTheme.muted)
                            }
                            Spacer()
                            Button("Save job") { Task { await model.setDecision(jobID: job.jobId, decision: "saved") } }
                                .appBorderedButton()
                            Button("Hide job") { Task { await model.setDecision(jobID: job.jobId, decision: "hidden") } }
                                .appBorderedButton()
                        }
                    }
                }
                .surfaceCardStyle()
            }
        }
    }

    private func resumeSuggestionsSection(_ suggestions: [ResumeSuggestion]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Resume rewrite suggestions")
                .font(.subheadline.bold())
            ForEach(suggestions) { suggestion in
                VStack(alignment: .leading, spacing: 4) {
                    if let heading = suggestion.heading {
                        Text(heading)
                            .font(.caption.bold())
                    }
                    Text(suggestion.suggestionText)
                        .font(.caption)
                        .foregroundStyle(AppTheme.muted)
                    HStack {
                        Button("Accept suggestion") {
                            Task { await model.updateSuggestionStatus(suggestionID: suggestion.id, accepted: true) }
                        }
                        .appBorderedButton()
                        Button("Reject suggestion") {
                            Task { await model.updateSuggestionStatus(suggestionID: suggestion.id, accepted: false) }
                        }
                        .appBorderedButton()
                    }
                    .controlSize(.small)
                }
            }
        }
    }

    private func rulesPreviewSection(_ jobs: [RulesPreviewJob]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Rules preview")
                .font(.headline)
            ForEach(jobs) { job in
                HStack {
                    VStack(alignment: .leading) {
                        Button(job.title) { Task { await model.openJob(job.jobId) } }
                            .appLinkButton()
                        Text("\(job.companyName) · score \(job.score)")
                            .font(.caption)
                            .foregroundStyle(AppTheme.muted)
                    }
                    Spacer()
                    Button("Save job") { Task { await model.setDecision(jobID: job.jobId, decision: "saved") } }
                        .appBorderedButton()
                }
                .font(.subheadline)
            }
        }
        .surfaceCardStyle()
    }

    private func runSummaryPanel(_ summary: MatchRunSummary) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(summary.title)
                .font(.headline)
            ForEach(summary.lines, id: \.self) { line in
                Text(line)
                    .font(.caption)
                    .foregroundStyle(AppTheme.muted)
            }
        }
        .surfaceCardStyle()
    }

    private func profileSidebar(_ profile: ProfileSummary, dashboard: DashboardResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Active profile")
                .font(.headline)
            Text("\(profile.name) v\(profile.version)")
                .font(.subheadline.bold())
            Text("Resume: \(profile.resumeFilename)")
                .font(.caption)
                .foregroundStyle(AppTheme.muted)
            if !profile.keywords.isEmpty {
                Text("Keywords: \(profile.keywords.prefix(6).joined(separator: ", "))")
                    .font(.caption)
                    .foregroundStyle(AppTheme.muted)
            }
            PreferencesEditor(profile: profile, model: model)
            if !dashboard.resumeSections.isEmpty {
                DisclosureGroup("Resume sections (\(dashboard.resumeSections.count))") {
                    ForEach(dashboard.resumeSections.prefix(6)) { section in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(section.heading)
                                .font(.caption.bold())
                            Text(section.text)
                                .font(.caption2)
                                .foregroundStyle(AppTheme.muted)
                                .lineLimit(3)
                            Button("Rewrite section") {
                                Task { await model.rewriteResumeSection(sectionID: section.id) }
                            }
                            .appBorderedButton()
                            .disabled(!model.llmConsent)
                        }
                        .padding(.vertical, 4)
                    }
                }
            }
            if !dashboard.resumeSuggestions.isEmpty {
                resumeSuggestionsSection(dashboard.resumeSuggestions)
            }
        }
        .surfaceCardStyle()
    }

    private func companyList(_ companies: [CompanyGroup]) -> some View {
        VStack(spacing: 16) {
            ForEach(companies) { company in
                CompanyCard(company: company) { jobID in
                    Task { await model.openJob(jobID) }
                } onDecision: { jobID, decision in
                    Task { await model.setDecision(jobID: jobID, decision: decision) }
                }
            }
        }
    }

    private func statCard(_ title: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption)
                .foregroundStyle(AppTheme.muted)
            Text(value)
                .font(.title3.bold())
                .foregroundStyle(AppTheme.textPrimary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .surfaceCardStyle()
    }

    private var shouldShowFirstRunChecklist: Bool {
        let connectionsImported = (model.connections?.connectionCount ?? model.dashboard?.connectionCount ?? 0) > 0
        let resumeReady = model.resumeAssetID != nil
        let catalogRefreshed = model.dashboard?.catalogRefreshedAt != nil
        return !resumeReady || !connectionsImported || !catalogRefreshed
    }

    private func networkMatches(in companies: [CompanyGroup]) -> Int {
        companies.filter { $0.connectionCount > 0 }.count
    }
}

private struct DashboardJobSheetItem: Identifiable {
    let id: Int
}

private struct CompanyCard: View {
    let company: CompanyGroup
    let onOpen: (Int) -> Void
    let onDecision: (Int, String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(company.name)
                        .font(.title3.bold())
                        .foregroundStyle(AppTheme.textPrimary)
                    if company.connectionCount > 0 {
                        Text(connectionHint)
                            .font(.caption)
                            .foregroundStyle(AppTheme.referral)
                    }
                }
                Spacer()
                if company.connectionCount > 0 {
                    Text("Referral path")
                        .font(.caption.bold())
                        .padding(.horizontal, 10)
                        .padding(.vertical, 4)
                        .background(AppTheme.referral.opacity(0.12))
                        .foregroundStyle(AppTheme.referral)
                        .clipShape(Capsule())
                }
                Text("\(company.visibleJobs.count) visible")
                    .font(.caption)
                    .foregroundStyle(AppTheme.muted)
            }

            ForEach(company.visibleJobs) { job in
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Button(job.title) { onOpen(job.jobId) }
                            .appLinkButton()
                        Text("\(job.label) · \(job.fitScore)/100 · \(job.recommendation)")
                            .font(.caption)
                            .foregroundStyle(AppTheme.muted)
                    }
                    Spacer()
                    HStack(spacing: 8) {
                        Button("Save job") { onDecision(job.jobId, "saved") }
                            .appBorderedButton()
                        Button("Hide job") { onDecision(job.jobId, "hidden") }
                            .appBorderedButton()
                        if job.decision != nil {
                            Button("Clear decision") { onDecision(job.jobId, "clear") }
                                .appBorderedButton()
                        }
                    }
                }
                .padding(.vertical, 4)
            }

            if !company.mismatchRiskJobs.isEmpty {
                DisclosureGroup("\(company.mismatchRiskJobs.count) mismatch risk") {
                    ForEach(company.mismatchRiskJobs) { job in
                        Button("\(job.title) · \(job.fitScore)") { onOpen(job.jobId) }
                            .appLinkButton()
                    }
                }
                .font(.caption)
            }

            if !company.hiddenJobs.isEmpty {
                DisclosureGroup("\(company.hiddenJobs.count) hidden") {
                    ForEach(company.hiddenJobs) { job in
                        HStack {
                            Button(job.title) { onOpen(job.jobId) }
                                .appLinkButton()
                            Button("Clear decision") { onDecision(job.jobId, "clear") }
                                .appBorderedButton()
                        }
                    }
                }
                .font(.caption)
            }
        }
        .padding(16)
        .background(AppTheme.surface)
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .stroke(
                    company.connectionCount > 0 ? AppTheme.referral.opacity(0.45) : AppTheme.border,
                    lineWidth: 1
                )
        )
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private var connectionHint: String {
        let names = company.linkedinConnections.prefix(3).map(\.fullName).joined(separator: ", ")
        if company.connectionCount > 3 {
            return "\(company.connectionCount) connections: \(names) +\(company.connectionCount - 3) more"
        }
        return "\(company.connectionCount) connections: \(names)"
    }
}

private struct PreferencesEditor: View {
    let profile: ProfileSummary
    @ObservedObject var model: AppModel
    @State private var role = ""
    @State private var level = ""
    @State private var location = ""
    @State private var workMode = ""
    @State private var companyStage = ""

    var body: some View {
        DisclosureGroup("Edit preferences") {
            VStack(alignment: .leading, spacing: 8) {
                preferenceField("Role", text: $role)
                preferenceField("Level", text: $level)
                preferenceField("Location", text: $location)
                preferenceField("Work mode", text: $workMode)
                preferenceField("Company stage", text: $companyStage)
                Button("Save preferences") {
                    Task {
                        await model.updatePreferences(
                            role: role,
                            level: level,
                            location: location,
                            workMode: workMode,
                            companyStage: companyStage
                        )
                    }
                }
                .appProminentButton()
            }
            .padding(.top, 8)
        }
        .onAppear {
            role = profile.desiredTitles.first ?? ""
            level = profile.levels.first ?? ""
            location = profile.locations.first ?? ""
            workMode = profile.remoteModes.first ?? ""
            companyStage = profile.companyStages.first ?? ""
        }
        .onChange(of: profile.version) { _, _ in
            role = profile.desiredTitles.first ?? ""
            level = profile.levels.first ?? ""
            location = profile.locations.first ?? ""
            workMode = profile.remoteModes.first ?? ""
            companyStage = profile.companyStages.first ?? ""
        }
    }

    private func preferenceField(_ label: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.caption2.weight(.semibold))
            TextField(label, text: text)
                .textFieldStyle(.roundedBorder)
        }
    }
}

#if DEBUG
#Preview("Dashboard with referral path") {
    DashboardPreview()
        .snapshotGroup("Dashboard")
        .frame(width: 1100, height: 760)
}

private struct DashboardPreview: View {
    var body: some View {
        let model = PreviewFixtures.appModel()
        model.dashboard = PreviewFixtures.dashboard
        return DashboardView(model: model)
    }
}
#endif