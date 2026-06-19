import SwiftUI
import UniformTypeIdentifiers

public struct OnboardingView: View {
    @ObservedObject private var model: AppModel
    @State private var isImporterPresented = false
    @State private var role = ""
    @State private var level = ""
    @State private var location = ""
    @State private var workMode = ""
    @State private var companyStage = ""

    public init(model: AppModel) {
        self.model = model
    }

    public var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                header
                resumeStep
                preferencesStep
                if !model.statusMessage.isEmpty {
                    Text(model.statusMessage)
                        .font(.footnote)
                        .foregroundStyle(AppTheme.muted)
                }
            }
            .padding(24)
        }
        .navigationTitle("Onboarding")
        .fileImporter(
            isPresented: $isImporterPresented,
            allowedContentTypes: [.pdf, UTType(filenameExtension: "docx") ?? .data],
            allowsMultipleSelection: false
        ) { result in
            guard case .success(let urls) = result, let url = urls.first else { return }
            Task { await model.uploadResume(from: url) }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("First-run setup")
                .font(.caption.weight(.semibold))
                .foregroundStyle(AppTheme.muted)
            Text("Upload your resume and set target preferences to start matching.")
                .foregroundStyle(AppTheme.muted)
        }
    }

    private var resumeStep: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Step 1 · Upload resume")
                .font(.headline)
            Text("PDF and DOCX files are stored locally. Keywords are extracted before any optional LLM step.")
                .font(.subheadline)
                .foregroundStyle(AppTheme.muted)
            HStack {
                Button("Choose resume file") {
                    isImporterPresented = true
                }
                .appProminentButton()
                if let assetID = model.resumeAssetID {
                    Text("Resume asset #\(assetID)")
                        .font(.caption)
                        .foregroundStyle(AppTheme.referral)
                }
            }
            if model.onboardingState?.pendingVisionFallback == true {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Low-confidence parse detected. Consent to vision fallback or continue with extracted content.")
                        .font(.caption)
                        .foregroundStyle(.orange)
                    HStack {
                        Button("Use vision fallback") {
                            Task { await model.consentVisionFallback(consent: true) }
                        }
                        .appProminentButton()
                        Button("Decline vision fallback") {
                            Task { await model.consentVisionFallback(consent: false) }
                        }
                        .appBorderedButton()
                    }
                }
            }
        }
        .surfaceCardStyle()
    }

    private var preferencesStep: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Step 2 · Preferences")
                .font(.headline)
            preferenceField("Role", text: $role, placeholder: "Machine Learning Engineer")
            preferenceField("Level", text: $level, placeholder: "Senior")
            preferenceField("Location", text: $location, placeholder: "New York or Remote US")
            preferenceField("Work mode", text: $workMode, placeholder: "Remote, hybrid, or onsite")
            preferenceField("Company stage", text: $companyStage, placeholder: "Growth, startup, or public")
            Button("Create profile and open dashboard") {
                Task {
                    await model.completeOnboarding(
                        role: role,
                        level: level,
                        location: location,
                        workMode: workMode,
                        companyStage: companyStage
                    )
                }
            }
            .appProminentButton()
            .disabled(model.resumeAssetID == nil || model.isLoading)
        }
        .surfaceCardStyle()
    }

    private func preferenceField(_ label: String, text: Binding<String>, placeholder: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.caption.weight(.semibold))
            TextField(placeholder, text: text)
                .textFieldStyle(.roundedBorder)
        }
    }
}