import SwiftUI

public struct LLMSettingsView: View {
    @ObservedObject private var model: AppModel
    @State private var apiKey = ""
    @State private var fitModel = ""
    @State private var rewriteModel = ""
    @State private var visionModel = ""
    @State private var httpReferer = ""
    @State private var appTitle = "ML Job Swarm"

    public init(model: AppModel) {
        self.model = model
    }

    public var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header
                statusCard
                usageCard
                credentialsCard
                modelsCard
                actionsCard
                if !model.statusMessage.isEmpty {
                    Text(model.statusMessage)
                        .font(.footnote)
                        .foregroundStyle(AppTheme.muted)
                }
            }
            .padding(24)
        }
        .navigationTitle("LLM settings")
        .task {
            await model.loadLLMUsage()
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(5))
                await model.loadLLMUsage()
            }
        }
        .onAppear {
            fitModel = model.llmSettings.fitModel
            rewriteModel = model.llmSettings.rewriteModel
            visionModel = model.llmSettings.visionModel
            httpReferer = model.llmSettings.httpReferer
            appTitle = model.llmSettings.appTitle
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("OpenRouter")
                .font(.caption.weight(.semibold))
                .foregroundStyle(AppTheme.muted)
            Text("Fit review, resume rewrite, and vision fallback use OpenRouter. Keys are stored in the macOS Keychain and injected into the bundled Python backend on restart.")
                .foregroundStyle(AppTheme.muted)
        }
    }

    private var statusCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Runtime status")
                .font(.headline)
                .foregroundStyle(AppTheme.textPrimary)
            HStack {
                Text(model.llmAvailable ? "Fit review ready" : "Fit review unavailable")
                    .font(.subheadline.bold())
                    .foregroundStyle(model.llmAvailable ? AppTheme.referral : .orange)
                Spacer()
                Text(model.hasStoredLLMKey ? "Keychain key saved" : "No saved API key")
                    .font(.caption)
                    .foregroundStyle(AppTheme.muted)
            }
            if let source = model.llmKeyImportSource {
                Text("API key imported from \(source)")
                    .font(.caption)
                    .foregroundStyle(AppTheme.referral)
            }
            Text(model.llmAvailable
                ? "Find matches and fit review can call OpenRouter when consent is checked."
                : "Save an OpenRouter API key below, then restart the backend.")
                .font(.caption)
                .foregroundStyle(AppTheme.muted)
        }
        .surfaceCardStyle()
    }

    private var usageCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Live usage")
                    .font(.headline)
                    .foregroundStyle(AppTheme.textPrimary)
                Spacer()
                Text("Updates every 5s")
                    .font(.caption2)
                    .foregroundStyle(AppTheme.muted)
            }
            if let usage = model.llmUsage {
                HStack(spacing: 12) {
                    usageStat("Total calls", value: "\(usage.totalRequests)")
                    usageStat("Today", value: "\(usage.requestsToday)")
                    usageStat("Succeeded", value: "\(succeededCount(in: usage))")
                    usageStat("Failed", value: "\(failedCount(in: usage))")
                }
                if !usage.byFeature.isEmpty {
                    Text("By feature")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(AppTheme.muted)
                    ForEach(featureRows(from: usage), id: \.label) { row in
                        HStack {
                            Text(row.label)
                                .font(.caption)
                                .foregroundStyle(AppTheme.textPrimary)
                            Spacer()
                            Text("\(row.succeeded) ok · \(row.failed) failed")
                                .font(.caption)
                                .foregroundStyle(AppTheme.muted)
                        }
                    }
                }
                if usage.recentRequests.isEmpty {
                    Text("No LLM calls yet. Run fit review or resume rewrite to populate this feed.")
                        .font(.caption)
                        .foregroundStyle(AppTheme.muted)
                } else {
                    Text("Recent activity")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(AppTheme.muted)
                    ForEach(usage.recentRequests.prefix(12)) { request in
                        HStack(alignment: .top, spacing: 8) {
                            Circle()
                                .fill(request.status == "succeeded" ? AppTheme.referral : .orange)
                                .frame(width: 8, height: 8)
                                .padding(.top, 4)
                            VStack(alignment: .leading, spacing: 2) {
                                Text("\(featureLabel(request.feature)) · \(request.model)")
                                    .font(.caption)
                                    .foregroundStyle(AppTheme.textPrimary)
                                Text(request.createdAt)
                                    .font(.caption2)
                                    .foregroundStyle(AppTheme.muted)
                                if let error = request.error, request.status != "succeeded", !error.isEmpty {
                                    Text(error)
                                        .font(.caption2)
                                        .foregroundStyle(.orange)
                                        .lineLimit(2)
                                }
                            }
                            Spacer()
                            Text(request.status)
                                .font(.caption2.weight(.semibold))
                                .foregroundStyle(request.status == "succeeded" ? AppTheme.referral : .orange)
                        }
                    }
                }
            } else {
                ProgressView("Loading usage…")
            }
        }
        .surfaceCardStyle()
    }

    private var credentialsCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("API key")
                .font(.headline)
                .foregroundStyle(AppTheme.textPrimary)
            SecureField(
                model.hasStoredLLMKey ? "Enter a new key to replace the saved key" : "OpenRouter API key",
                text: $apiKey
            )
            .textFieldStyle(.roundedBorder)
            Text("Leave blank and save to keep the existing Keychain key.")
                .font(.caption)
                .foregroundStyle(AppTheme.muted)
        }
        .surfaceCardStyle()
    }

    private var modelsCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Optional model overrides")
                .font(.headline)
                .foregroundStyle(AppTheme.textPrimary)
            settingsField("Fit review model", text: $fitModel, placeholder: "openrouter/auto")
            settingsField("Resume rewrite model", text: $rewriteModel, placeholder: "openrouter/auto")
            settingsField("Vision fallback model", text: $visionModel, placeholder: "openrouter/auto")
            settingsField("HTTP referer", text: $httpReferer, placeholder: "https://example.com")
            settingsField("App title", text: $appTitle, placeholder: "ML Job Swarm")
        }
        .surfaceCardStyle()
    }

    private var actionsCard: some View {
        HStack(spacing: 12) {
            Button("Save and restart backend") {
                Task {
                    let keyToSave: String? = apiKey.isEmpty ? nil : apiKey
                    await model.saveLLMSettings(
                        apiKey: keyToSave,
                        preferences: LLMPreferences(
                            fitModel: fitModel,
                            rewriteModel: rewriteModel,
                            visionModel: visionModel,
                            httpReferer: httpReferer,
                            appTitle: appTitle
                        )
                    )
                    apiKey = ""
                }
            }
            .appProminentButton()
            Button("Remove saved key") {
                Task { await model.clearLLMSettings() }
            }
            .appBorderedButton()
            .disabled(!model.hasStoredLLMKey)
        }
    }

    private func settingsField(_ label: String, text: Binding<String>, placeholder: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.caption.weight(.semibold))
                .foregroundStyle(AppTheme.textPrimary)
            TextField(placeholder, text: text)
                .textFieldStyle(.roundedBorder)
        }
    }

    private func usageStat(_ title: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption2)
                .foregroundStyle(AppTheme.muted)
            Text(value)
                .font(.title3.bold())
                .foregroundStyle(AppTheme.textPrimary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func succeededCount(in usage: LLMUsageResponse) -> Int {
        usage.byFeature.values.reduce(0) { $0 + ($1["succeeded"] ?? 0) }
    }

    private func failedCount(in usage: LLMUsageResponse) -> Int {
        usage.byFeature.values.reduce(0) { $0 + ($1["failed"] ?? 0) }
    }

    private func featureLabel(_ feature: String) -> String {
        switch feature {
        case "fit_gate": return "Fit review"
        case "resume_rewrite": return "Resume rewrite"
        case "resume_vision_fallback": return "Vision fallback"
        default: return feature
        }
    }

    private struct FeatureRow {
        let label: String
        let succeeded: Int
        let failed: Int
    }

    private func featureRows(from usage: LLMUsageResponse) -> [FeatureRow] {
        usage.byFeature.keys.sorted().map { feature in
            let counts = usage.byFeature[feature] ?? [:]
            return FeatureRow(
                label: featureLabel(feature),
                succeeded: counts["succeeded"] ?? 0,
                failed: counts["failed"] ?? 0
            )
        }
    }
}