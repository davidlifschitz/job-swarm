import SwiftUI

public struct LinkedInExportGuideView: View {
    private let onImport: () -> Void
    @Environment(\.openURL) private var openURL

    public init(onImport: @escaping () -> Void) {
        self.onImport = onImport
    }

    public var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 6) {
                Text("How to export your LinkedIn connections")
                    .font(.headline)
                    .foregroundStyle(AppTheme.textPrimary)
                Text(
                    "Start from the LinkedIn home page after logging in. LinkedIn emails a ZIP archive; unzip it and import Connections.csv here."
                )
                .font(.caption)
                .foregroundStyle(AppTheme.muted)
            }

            HStack(spacing: 10) {
                Button("Open LinkedIn") {
                    open(linkedInHomeURL)
                }
                .appBorderedButton()
                Button("Open download data page") {
                    open(linkedInDataExportURL)
                }
                .appProminentButton()
                Button("Import Connections.csv") {
                    onImport()
                }
                .appBorderedButton()
            }

            DisclosureGroup("Option A · Mobile (app or mobile browser)") {
                instructionList([
                    "Tap your profile picture in the top-left of the LinkedIn home page.",
                    "Open Settings (gear icon).",
                    "Tap Data privacy.",
                    "Tap Download your data (under How LinkedIn uses your data).",
                    "Select Download larger data archive, including connections, verifications, contacts…. LinkedIn bundles connections into this archive — a separate Connections-only checkbox may not appear.",
                    "Scroll down and tap Request archive.",
                    "Enter your LinkedIn password if prompted.",
                    "Wait for LinkedIn’s email with the download link (often a few hours, up to 24 hours for large networks).",
                ])
            }
            .surfaceCardStyle()

            DisclosureGroup("Option B · Desktop web browser") {
                instructionList([
                    "Click Me (your profile icon) in the top-right navigation bar.",
                    "Click Settings & Privacy.",
                    "Click Data privacy in the left sidebar.",
                    "Click Get a copy of your data (under How LinkedIn uses your data).",
                    "Select Download larger data archive….",
                    "Click Request archive.",
                    "Enter your LinkedIn password if prompted.",
                    "Wait for LinkedIn’s email with the download link.",
                ])
            }
            .surfaceCardStyle()

            VStack(alignment: .leading, spacing: 8) {
                Text("After the email arrives")
                    .font(.subheadline.bold())
                    .foregroundStyle(AppTheme.textPrimary)
                instructionList([
                    "Download the .zip archive from LinkedIn’s email link.",
                    "Unzip the archive on your Mac.",
                    "Find Connections.csv inside the extracted folder.",
                    "Click Import Connections.csv above (or use the toolbar button) and select that file.",
                ])
            }
            .surfaceCardStyle()
        }
    }

    private var linkedInHomeURL: URL {
        URL(string: "https://www.linkedin.com/")!
    }

    private var linkedInDataExportURL: URL {
        URL(string: "https://www.linkedin.com/mypreferences/d/download-my-data")!
    }

    private func open(_ url: URL) {
        openURL(url)
    }

    @ViewBuilder
    private func instructionList(_ steps: [String]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(Array(steps.enumerated()), id: \.offset) { index, step in
                HStack(alignment: .top, spacing: 10) {
                    Text("\(index + 1).")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(AppTheme.accent)
                        .frame(width: 18, alignment: .trailing)
                    Text(step)
                        .font(.caption)
                        .foregroundStyle(AppTheme.textPrimary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        .padding(.top, 4)
    }
}

#if DEBUG
#Preview("LinkedIn export guide") {
    LinkedInExportGuideView(onImport: {})
        .padding(24)
        .frame(width: 760)
}
#endif