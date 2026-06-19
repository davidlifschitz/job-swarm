import SwiftUI

public struct FirstRunChecklistView: View {
    @ObservedObject private var model: AppModel

    public init(model: AppModel) {
        self.model = model
    }

    public var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("First-run checklist")
                .font(.headline)
                .foregroundStyle(AppTheme.textPrimary)
            Text("Complete these once to get matches flowing.")
                .font(.caption)
                .foregroundStyle(AppTheme.muted)
            checklistRow(
                done: model.resumeAssetID != nil,
                title: "Upload resume",
                detail: "Onboarding extracts keywords locally before any LLM step."
            ) {
                model.selectedSection = .onboarding
            }
            checklistRow(
                done: (model.connections?.connectionCount ?? 0) > 0,
                title: "Import LinkedIn Connections.csv",
                detail: "Use the export guide on the Connections page."
            ) {
                model.selectedSection = .connections
            }
            checklistRow(
                done: model.dashboard?.catalogRefreshedAt != nil,
                title: "Refresh careers catalog",
                detail: "Pulls open roles from reviewed company sources."
            ) {
                Task { await model.refreshSources() }
            }
            checklistRow(
                done: model.hasStoredLLMKey,
                title: "Configure LLM (optional)",
                detail: "Enables fit review; rules matching works without a key."
            ) {
                model.selectedSection = .llmSettings
            }
        }
        .surfaceCardStyle()
    }

    @ViewBuilder
    private func checklistRow(
        done: Bool,
        title: String,
        detail: String,
        action: @escaping () -> Void
    ) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: done ? "checkmark.circle.fill" : "circle")
                .foregroundStyle(done ? AppTheme.referral : AppTheme.muted)
                .font(.title3)
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.subheadline.bold())
                    .foregroundStyle(AppTheme.textPrimary)
                Text(detail)
                    .font(.caption)
                    .foregroundStyle(AppTheme.muted)
                if !done {
                    Button("Go") { action() }
                        .appBorderedButton()
                }
            }
            Spacer()
        }
    }
}

#if DEBUG
#Preview("First-run checklist") {
    FirstRunChecklistView(model: PreviewFixtures.appModel())
        .padding(24)
        .frame(width: 520)
}
#endif