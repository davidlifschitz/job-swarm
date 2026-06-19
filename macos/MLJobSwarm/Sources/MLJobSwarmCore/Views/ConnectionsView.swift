import SnapshotPreferences
import SwiftUI
import UniformTypeIdentifiers

public struct ConnectionsView: View {
    @ObservedObject private var model: AppModel
    @State private var isImporterPresented = false
    @State private var searchText = ""

    public init(model: AppModel) {
        self.model = model
    }

    public var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header
                LinkedInExportGuideView {
                    isImporterPresented = true
                }
                HStack {
                    TextField("Search connections", text: $searchText)
                        .textFieldStyle(.roundedBorder)
                        .onSubmit { Task { await model.loadConnections(search: searchText) } }
                    Button("Search connections") {
                        Task { await model.loadConnections(search: searchText) }
                    }
                    .appBorderedButton()
                }
                if let connections = model.connections {
                    stats(connections)
                    matchedCatalog(connections.matchedCatalog)
                    groupedCompanies(connections.groupedCompanies)
                } else if model.isLoading {
                    ProgressView("Loading connections…")
                }
            }
            .padding(24)
        }
        .navigationTitle("LinkedIn connections")
        .toolbar {
            Button {
                isImporterPresented = true
            } label: {
                Label("Import LinkedIn CSV", systemImage: "square.and.arrow.down")
            }
        }
        .fileImporter(
            isPresented: $isImporterPresented,
            allowedContentTypes: [.commaSeparatedText, .text],
            allowsMultipleSelection: false
        ) { result in
            guard case .success(let urls) = result, let url = urls.first else { return }
            Task { await model.importConnections(from: url) }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Referral network")
                .font(.caption.weight(.semibold))
                .foregroundStyle(AppTheme.muted)
            Text("Import Connections.csv once; contacts are matched to companies in the seed catalog by name and aliases (e.g. DeepMind → Google DeepMind). Add catalog companies in Source health to grow matches — refreshing careers only adds jobs, not network companies.")
                .foregroundStyle(AppTheme.muted)
        }
    }

    private func stats(_ response: ConnectionsResponse) -> some View {
        HStack(spacing: 12) {
            statCard("Stored connections", value: "\(response.connectionCount)")
            statCard("Catalog matches", value: "\(response.matchedCatalog.count)")
        }
    }

    private func matchedCatalog(_ matches: [CatalogMatch]) -> some View {
        Group {
            if !matches.isEmpty {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Companies in your network")
                        .font(.headline)
                        .foregroundStyle(AppTheme.textPrimary)
                    ForEach(matches) { match in
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text(match.companyName)
                                    .font(.title3.bold())
                                    .foregroundStyle(AppTheme.textPrimary)
                                Spacer()
                                Text("\(match.connections.count) connections")
                                    .font(.caption)
                                    .foregroundStyle(AppTheme.muted)
                            }
                            ForEach(match.connections) { contact in
                                HStack {
                                    Text(contact.fullName)
                                        .foregroundStyle(AppTheme.textPrimary)
                                    if !contact.position.isEmpty {
                                        Text(contact.position)
                                            .foregroundStyle(AppTheme.muted)
                                    }
                                    Spacer()
                                    if let url = URL(string: contact.profileURL), !contact.profileURL.isEmpty {
                                        Link("Profile", destination: url)
                                    }
                                }
                                .font(.subheadline)
                            }
                        }
                        .surfaceCardStyle()
                    }
                }
            }
        }
    }

    private func groupedCompanies(_ groups: [ConnectionsGroup]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Browse by company")
                .font(.headline)
                .foregroundStyle(AppTheme.textPrimary)
            if groups.isEmpty {
                ContentUnavailableView(
                    "No connections imported yet",
                    systemImage: "person.crop.circle.badge.plus",
                    description: Text("Follow the export steps above, then import Connections.csv from LinkedIn’s data archive.")
                )
            } else {
                ForEach(groups) { group in
                    DisclosureGroup {
                        ForEach(group.connections) { contact in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(contact.fullName)
                                    .font(.subheadline.bold())
                                    .foregroundStyle(AppTheme.textPrimary)
                                if !contact.position.isEmpty {
                                    Text(contact.position)
                                        .font(.caption)
                                        .foregroundStyle(AppTheme.muted)
                                }
                            }
                            .padding(.vertical, 4)
                        }
                    } label: {
                        HStack {
                            Text(group.company)
                                .foregroundStyle(AppTheme.textPrimary)
                            Spacer()
                            Text("\(group.connections.count)")
                                .foregroundStyle(AppTheme.muted)
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
}

#if DEBUG
#Preview("Connections workspace") {
    ConnectionsPreview()
        .snapshotGroup("Connections")
        .frame(width: 900, height: 700)
}

private struct ConnectionsPreview: View {
    var body: some View {
        let model = PreviewFixtures.appModel()
        model.connections = PreviewFixtures.connections
        return ConnectionsView(model: model)
    }
}
#endif