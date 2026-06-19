import SwiftUI

public struct SavedJobsView: View {
    @ObservedObject private var model: AppModel
    @State private var searchText = ""
    @State private var sortKey = "recent"

    public init(model: AppModel) {
        self.model = model
    }

    public var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header
                filters
                if let saved = model.savedJobs {
                    if saved.savedJobs.isEmpty {
                        ContentUnavailableView(
                            "No saved jobs yet",
                            systemImage: "bookmark",
                            description: Text("Save jobs from the dashboard to track applications here.")
                        )
                    } else {
                        ForEach(saved.savedJobs) { job in
                            savedJobCard(job)
                        }
                    }
                } else if model.isLoading {
                    ProgressView("Loading saved jobs…")
                }
                if !model.statusMessage.isEmpty {
                    Text(model.statusMessage)
                        .font(.footnote)
                        .foregroundStyle(AppTheme.muted)
                }
            }
            .padding(24)
        }
        .navigationTitle("Saved jobs")
        .toolbar {
            ToolbarItemGroup {
                Button {
                    Task { await model.exportSavedJobsCSV(query: searchText, sort: sortKey) }
                } label: {
                    Label("Export CSV", systemImage: "square.and.arrow.up")
                }
                Button {
                    Task { await reload() }
                } label: {
                    Label("Reload saved jobs", systemImage: "arrow.counterclockwise")
                }
            }
        }
        .sheet(item: Binding(
            get: { model.selectedJobID.map(JobSheetItem.init) },
            set: { model.selectedJobID = $0?.id }
        )) { item in
            JobDetailView(model: model, jobID: item.id)
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Application queue")
                .font(.caption.weight(.semibold))
                .foregroundStyle(AppTheme.muted)
            Text("Saved roles with packet status, referral contacts, and manual submit links.")
                .foregroundStyle(AppTheme.muted)
        }
    }

    private var filters: some View {
        HStack(spacing: 12) {
            TextField("Search saved jobs", text: $searchText)
                .textFieldStyle(.roundedBorder)
                .onSubmit { Task { await reload() } }
            Picker("Sort", selection: $sortKey) {
                Text("Recent").tag("recent")
                Text("Score").tag("score")
                Text("Company").tag("company")
                Text("Title").tag("title")
            }
            .onChange(of: sortKey) { _, _ in Task { await reload() } }
            Button("Search saved jobs") { Task { await reload() } }
                .appBorderedButton()
        }
    }

    private func savedJobCard(_ job: SavedJob) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Button(job.title) {
                        Task { await model.openJob(job.jobId) }
                    }
                    .appLinkButton()
                    Text(job.company)
                        .foregroundStyle(AppTheme.muted)
                }
                Spacer()
                Text(job.label)
                    .font(.caption.bold())
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(AppTheme.accent.opacity(0.1))
                    .clipShape(Capsule())
            }
            HStack(spacing: 16) {
                if let score = job.fitScore {
                    Text("\(score)/100")
                }
                Text("Packet: \(job.packetStatus)")
                if !job.notes.isEmpty {
                    Text(job.notes)
                        .lineLimit(1)
                        .foregroundStyle(AppTheme.muted)
                }
            }
            .font(.caption)
            HStack(spacing: 12) {
                if !job.applyURL.isEmpty, let url = URL(string: job.applyURL) {
                    Link("Apply", destination: url)
                }
                if !job.sourceURL.isEmpty, let url = URL(string: job.sourceURL) {
                    Link("Source", destination: url)
                }
                if job.packetStatus == "not_prepared" {
                    Button("Prepare application packet") {
                        Task {
                            await model.openJob(job.jobId)
                            await model.prepareApplicationPacket(jobID: job.jobId)
                        }
                    }
                    .appBorderedButton()
                }
                Button("Clear saved status") {
                    Task { await model.setDecision(jobID: job.jobId, decision: "clear") }
                }
                .appBorderedButton()
            }
            .font(.caption)
            if let contacts = job.referralContacts, !contacts.isEmpty {
                Text("\(contacts.count) referral contact(s)")
                    .font(.caption)
                    .foregroundStyle(AppTheme.referral)
            }
        }
        .surfaceCardStyle()
    }

    private func reload() async {
        await model.loadSavedJobs(query: searchText, sort: sortKey)
    }
}

private struct JobSheetItem: Identifiable {
    let id: Int
}