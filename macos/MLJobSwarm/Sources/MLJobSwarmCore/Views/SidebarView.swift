import SwiftUI

public struct SidebarView: View {
    @ObservedObject private var model: AppModel

    public init(model: AppModel) {
        self.model = model
    }

    public var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            VStack(alignment: .leading, spacing: 4) {
                Text("ml-job-swarm")
                    .font(.title3.bold())
                Text("Local-first job ops")
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.7))
            }

            if !model.profiles.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Profile")
                        .font(.caption.bold())
                        .foregroundStyle(.white.opacity(0.7))
                    Picker("Profile", selection: Binding(
                        get: { model.selectedProfileID ?? model.profiles.first!.id },
                        set: { newValue in
                            Task { await model.selectProfile(newValue) }
                        }
                    )) {
                        ForEach(model.profiles) { profile in
                            Text("\(profile.name) v\(profile.version)")
                                .tag(profile.id)
                        }
                    }
                    .labelsHidden()
                }
            }

            List(selection: $model.selectedSection) {
                Section("Workspace") {
                    ForEach(AppSection.allCases) { section in
                        Label(section.title, systemImage: section.symbol)
                            .foregroundStyle(AppTheme.textOnSidebar)
                            .tag(section)
                    }
                }
            }
            .listStyle(.sidebar)
            .scrollContentBackground(.hidden)

            VStack(alignment: .leading, spacing: 6) {
                Text("Safety")
                    .font(.caption.bold())
                    .foregroundStyle(.white.opacity(0.7))
                Text("Public ATS only")
                Text("Manual submit")
                Text("SQLite local")
                Text(model.llmAvailable ? "LLM ready" : "LLM paused")
                    .foregroundStyle(model.llmAvailable ? AppTheme.referral : .white.opacity(0.7))
                if let usage = model.llmUsage {
                    Text("\(usage.totalRequests) LLM calls · \(usage.requestsToday) today")
                        .foregroundStyle(.white.opacity(0.7))
                }
            }
            .font(.caption2)
            .foregroundStyle(.white.opacity(0.85))

            Spacer()
        }
        .padding(16)
        .background(AppTheme.sidebar)
        .foregroundStyle(AppTheme.textOnSidebar)
        .preferredColorScheme(.dark)
        .textSelection(.enabled)
        .onChange(of: model.selectedSection) { _, _ in
            Task { await model.refreshCurrentSection() }
        }
    }
}