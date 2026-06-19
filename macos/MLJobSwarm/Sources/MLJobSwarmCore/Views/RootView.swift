import SwiftUI

public struct RootView: View {
    @ObservedObject private var model: AppModel

    public init(model: AppModel) {
        self.model = model
    }

    public var body: some View {
        NavigationSplitView {
            SidebarView(model: model)
                .navigationSplitViewColumnWidth(min: 220, ideal: 260, max: 300)
        } detail: {
            detailContent
                .mainContentStyle()
                .overlay {
                    if model.isWorking {
                        ZStack {
                            Color.black.opacity(0.08)
                            ProgressView("Working…")
                                .padding(20)
                                .background(AppTheme.surface)
                                .clipShape(RoundedRectangle(cornerRadius: 12))
                        }
                    }
                }
        }
        .textSelection(.enabled)
        .task {
            await model.bootstrap()
        }
    }

    @ViewBuilder
    private var detailContent: some View {
        if !model.backend.isReady {
            BackendStatusView(model: model)
        } else {
            switch model.selectedSection {
            case .dashboard:
                DashboardView(model: model)
            case .savedJobs:
                SavedJobsView(model: model)
            case .connections:
                ConnectionsView(model: model)
            case .onboarding:
                OnboardingView(model: model)
            case .adminSources:
                AdminSourcesView(model: model)
            case .llmSettings:
                LLMSettingsView(model: model)
            }
        }
    }
}

private struct BackendStatusView: View {
    @ObservedObject var model: AppModel

    private var startupFailed: Bool {
        let status = model.backend.status.lowercased()
        return status.contains("timed out")
            || status.contains("exited")
            || status.contains("could not")
            || status.contains("failed")
    }

    var body: some View {
        VStack(spacing: 16) {
            if startupFailed {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.largeTitle)
                    .foregroundStyle(.orange)
            } else {
                ProgressView()
                    .tint(AppTheme.accent)
            }
            Text(model.backend.status)
                .font(.headline)
                .foregroundStyle(AppTheme.textPrimary)
                .multilineTextAlignment(.center)
            Text(
                startupFailed
                    ? "The bundled Python engine did not start. Restart the backend or reinstall from the latest GitHub release."
                    : "Starting the local Python engine and SQLite store."
            )
            .foregroundStyle(AppTheme.muted)
            .multilineTextAlignment(.center)
            if startupFailed {
                Button("Restart backend") {
                    Task { await model.restartBackend() }
                }
                .appProminentButton()
            }
        }
        .padding(24)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .mainContentStyle()
    }
}