import SwiftUI

public struct AdminSourcesView: View {
    @ObservedObject private var model: AppModel

    public init(model: AppModel) {
        self.model = model
    }

    public var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header
                refreshAllCard
                if let admin = model.adminSources {
                    summary(admin.supportSummary)
                    sourceList(admin.sources)
                    reviewQueue(admin.sourceReviews)
                } else if model.isLoading {
                    ProgressView("Loading source health…")
                }
                if !model.statusMessage.isEmpty {
                    Text(model.statusMessage)
                        .font(.footnote)
                        .foregroundStyle(AppTheme.muted)
                }
            }
            .padding(24)
        }
        .navigationTitle("Source health")
        .toolbar {
            ToolbarItemGroup {
                Button {
                    Task { await model.refreshAllAdminSources() }
                } label: {
                    Label("Refresh all sources", systemImage: "arrow.clockwise")
                }
                Button {
                    Task { await model.loadAdminSources() }
                } label: {
                    Label("Reload source health", systemImage: "arrow.counterclockwise")
                }
            }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Catalog operations")
                .font(.caption.weight(.semibold))
                .foregroundStyle(AppTheme.muted)
            Text("Seed catalog companies drive both job sources and LinkedIn referral matching. Expand data/seed_companies.json (or submit sources for review) and restart to grow your network company count; aliases like DeepMind → Google DeepMind improve matching. Refresh sources only ingests open roles — it does not add catalog companies.")
                .foregroundStyle(AppTheme.muted)
                .font(.caption)
        }
    }

    private var refreshAllCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Refresh every source")
                .font(.headline)
                .foregroundStyle(AppTheme.textPrimary)
            Text("Runs CareersJsonLdAdapter and public ATS adapters for all reviewed sources in one pass. Use this before fit review when many careers pages look stale.")
                .font(.caption)
                .foregroundStyle(AppTheme.muted)
            Button("Refresh all sources now") {
                Task { await model.refreshAllAdminSources() }
            }
            .appProminentButton()
            .disabled(model.isWorking)
        }
        .surfaceCardStyle()
    }

    private func summary(_ support: SourceSupportSummary) -> some View {
        HStack(spacing: 12) {
            statCard("Total", value: "\(support.total)")
            statCard("Ready", value: "\(support.ready)")
            statCard("Unsupported", value: "\(support.unsupported)")
            statCard("Disabled", value: "\(support.disabled)")
        }
    }

    private func sourceList(_ sources: [SourceHealthRow]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Active sources (\(sources.count))")
                .font(.headline)
                .foregroundStyle(AppTheme.textPrimary)
            if sources.isEmpty {
                Text("No sources configured yet.")
                    .foregroundStyle(AppTheme.muted)
            } else {
                ForEach(sources) { source in
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text(source.companyName)
                                .font(.subheadline.bold())
                                .foregroundStyle(AppTheme.textPrimary)
                            Spacer()
                            Text(source.healthStatusLabel)
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(healthColor(source.healthStatus))
                        }
                        Text("\(source.sourceType) · \(source.url)")
                            .font(.caption)
                            .foregroundStyle(AppTheme.muted)
                            .lineLimit(2)
                        HStack {
                            Text(source.adapterStatusLabel)
                            Text("·")
                            Text("\(source.activeJobCount) open jobs on this source")
                            Text("·")
                            Text(source.latestRecommendation)
                        }
                        .font(.caption2)
                        .foregroundStyle(AppTheme.muted)
                        Button("Refresh this source") {
                            Task { await model.refreshAdminSource(sourceID: source.id) }
                        }
                        .appBorderedButton()
                    }
                    .surfaceCardStyle()
                }
            }
        }
    }

    private func reviewQueue(_ reviews: [SourceReviewRow]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Pending reviews")
                .font(.headline)
                .foregroundStyle(AppTheme.textPrimary)
            if reviews.filter({ $0.status == "pending" }).isEmpty {
                Text("No pending source reviews.")
                    .foregroundStyle(AppTheme.muted)
            } else {
                ForEach(reviews.filter { $0.status == "pending" }) { review in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(review.companyName)
                            .font(.subheadline.bold())
                            .foregroundStyle(AppTheme.textPrimary)
                        Text(review.requestedURL)
                            .font(.caption)
                            .foregroundStyle(AppTheme.muted)
                        Text(review.reason)
                            .font(.caption)
                            .foregroundStyle(AppTheme.muted)
                        HStack {
                            Button("Approve source") {
                                Task { await model.approveSourceReview(queueID: review.id) }
                            }
                            .appProminentButton()
                            Button("Reject source") {
                                Task { await model.rejectSourceReview(queueID: review.id) }
                            }
                            .appBorderedButton()
                        }
                    }
                    .surfaceCardStyle()
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

    private func healthColor(_ status: String) -> Color {
        switch status {
        case "healthy", "covered": return AppTheme.referral
        case "disabled": return AppTheme.muted
        case "spa-fallback": return AppTheme.accent
        default: return .orange
        }
    }
}