import SwiftUI

public struct JobDetailView: View {
    @ObservedObject private var model: AppModel
    private let jobID: Int
    @Environment(\.dismiss) private var dismiss
    @State private var decisionNotes = ""
    @State private var referralName = ""
    @State private var referralEmail = ""
    @State private var referralTitle = ""
    @State private var referralRelationship = ""

    public init(model: AppModel, jobID: Int) {
        self.model = model
        self.jobID = jobID
    }

    public var body: some View {
        ScrollView {
            if let detail = model.jobDetail?.job {
                VStack(alignment: .leading, spacing: 20) {
                    header(detail)
                    roleDetails(detail)
                    fitReview(detail)
                    descriptionSection(detail)
                    referralSection
                    localReferralForm
                    applicationWorkspace
                    decisionSection(detail)
                }
                .padding(24)
                .onAppear { decisionNotes = detail.notes }
            } else {
                ProgressView("Loading job…")
                    .task { await model.openJob(jobID) }
            }
        }
        .frame(minWidth: 720, minHeight: 600)
        .mainContentStyle()
    }

    private func header(_ job: JobDetail) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(job.title)
                .font(.largeTitle.bold())
            Text(job.companyName)
                .font(.title3)
                .foregroundStyle(AppTheme.muted)
            if let location = job.locationText {
                Text(location)
                    .foregroundStyle(AppTheme.muted)
            }
        }
    }

    private func roleDetails(_ job: JobDetail) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Role details")
                .font(.headline)
            detailRow("Department", job.department)
            detailRow("Work mode", job.remoteMode)
            detailRow("Employment", job.employmentType)
            detailRow("Seniority", job.seniority)
            detailRow("Status", job.status)
            if let apply = job.applyURL, let url = URL(string: apply) {
                Link("Apply URL", destination: url)
            }
            if let url = URL(string: job.sourceURL) {
                Link("Source listing", destination: url)
            }
        }
        .surfaceCardStyle()
    }

    private func detailRow(_ label: String, _ value: String?) -> some View {
        HStack {
            Text(label)
                .font(.caption.weight(.semibold))
                .frame(width: 100, alignment: .leading)
            Text(value ?? "Not specified")
                .font(.caption)
                .foregroundStyle(AppTheme.muted)
        }
    }

    private func fitReview(_ job: JobDetail) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Fit review")
                .font(.headline)
            if let label = job.label, let score = job.fitScore {
                Text("\(label) · \(score)/100")
                if let recommendation = job.recommendation {
                    Text(recommendation)
                }
                if !job.reasons.isEmpty {
                    Text("Reasons: \(job.reasons.joined(separator: ", "))")
                        .font(.caption)
                }
                if !job.risks.isEmpty {
                    Text("Risks: \(job.risks.joined(separator: ", "))")
                        .font(.caption)
                        .foregroundStyle(.orange)
                }
            } else {
                Text("No fit review for this profile version.")
                    .foregroundStyle(AppTheme.muted)
            }
        }
        .surfaceCardStyle()
    }

    private func descriptionSection(_ job: JobDetail) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Description")
                .font(.headline)
            Text(job.descriptionText ?? "No description captured.")
                .font(.body)
            Text("Requirements")
                .font(.headline)
            Text(job.requirementsText ?? "No requirements captured.")
                .font(.body)
        }
        .surfaceCardStyle()
    }

    private var referralSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("LinkedIn connections")
                .font(.headline)
            if let contacts = model.jobDetail?.linkedinConnections, !contacts.isEmpty {
                ForEach(contacts) { contact in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(contact.fullName)
                            .font(.subheadline.bold())
                        if !contact.position.isEmpty {
                            Text(contact.position)
                                .foregroundStyle(AppTheme.muted)
                        }
                        if let url = URL(string: contact.profileURL), !contact.profileURL.isEmpty {
                            Link("Open LinkedIn profile", destination: url)
                        }
                    }
                }
            } else {
                Text("No imported LinkedIn connections matched this company yet.")
                    .foregroundStyle(AppTheme.muted)
            }

            if let contacts = model.jobDetail?.referralContacts, !contacts.isEmpty {
                Divider()
                Text("Local referral contacts")
                    .font(.subheadline.bold())
                ForEach(contacts) { contact in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(contact.name)
                        if !contact.title.isEmpty {
                            Text(contact.title).font(.caption).foregroundStyle(AppTheme.muted)
                        }
                        if !contact.email.isEmpty {
                            Text(contact.email).font(.caption)
                        }
                    }
                }
            }
        }
        .surfaceCardStyle()
    }

    private var localReferralForm: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Add referral contact")
                .font(.headline)
            TextField("Name", text: $referralName)
                .textFieldStyle(.roundedBorder)
            TextField("Email", text: $referralEmail)
                .textFieldStyle(.roundedBorder)
            TextField("Title", text: $referralTitle)
                .textFieldStyle(.roundedBorder)
            TextField("Relationship", text: $referralRelationship)
                .textFieldStyle(.roundedBorder)
            Button("Add referral contact") {
                Task {
                    await model.addReferralContact(
                        jobID: jobID,
                        name: referralName,
                        email: referralEmail,
                        title: referralTitle,
                        relationship: referralRelationship
                    )
                    referralName = ""
                    referralEmail = ""
                    referralTitle = ""
                    referralRelationship = ""
                }
            }
            .appProminentButton()
            .disabled(referralName.trimmingCharacters(in: .whitespaces).isEmpty)
        }
        .surfaceCardStyle()
    }

    private var applicationWorkspace: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Application workspace")
                .font(.headline)
            Text("Prep-only packet for manual final submit.")
                .font(.caption)
                .foregroundStyle(AppTheme.muted)
            if let packet = model.jobDetail?.applicationPacket {
                Text("Status: \(packet.status)")
                if let detail = packet.packet {
                    Text("\(detail.company) · \(detail.title)")
                        .font(.subheadline.bold())
                    if let score = detail.fitScore, let label = detail.label {
                        Text("\(label) · \(score)/100")
                            .font(.caption)
                    }
                    if let recommendation = detail.recommendation, !recommendation.isEmpty {
                        Text(recommendation)
                            .font(.caption)
                    }
                    if !detail.reasons.isEmpty {
                        Text("Reasons: \(detail.reasons.joined(separator: ", "))")
                            .font(.caption2)
                            .foregroundStyle(AppTheme.muted)
                    }
                }
                if let url = packet.manualSubmitURL, !url.isEmpty, let link = URL(string: url) {
                    Link("Manual submit URL", destination: link)
                }
                if !packet.checklist.isEmpty {
                    Text("Checklist")
                        .font(.subheadline.bold())
                    ForEach(packet.checklist) { item in
                        HStack(alignment: .top) {
                            Image(systemName: item.done ? "checkmark.circle.fill" : "circle")
                                .foregroundStyle(item.done ? AppTheme.referral : AppTheme.muted)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(item.label)
                                    .font(.caption)
                                if let url = item.url, !url.isEmpty, let link = URL(string: url) {
                                    Link("Open apply page", destination: link)
                                        .font(.caption2)
                                }
                            }
                        }
                    }
                }
                if packet.status != "submitted" {
                    Button("Mark application submitted") {
                        Task { await model.markPacketSubmitted(packetID: packet.id) }
                    }
                    .appBorderedButton()
                }
            } else {
                Button("Prepare application packet") {
                    Task { await model.prepareApplicationPacket(jobID: jobID) }
                }
                .appProminentButton()
            }
        }
        .surfaceCardStyle()
    }

    private func decisionSection(_ job: JobDetail) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Decision")
                .font(.headline)
            Text(job.decision ?? "Unmarked")
            TextField("Notes", text: $decisionNotes)
                .textFieldStyle(.roundedBorder)
            HStack {
                Button("Save job") {
                    Task {
                        await model.setDecision(jobID: jobID, decision: "saved", notes: decisionNotes)
                        dismiss()
                    }
                }
                .appProminentButton()
                Button("Hide job") {
                    Task {
                        await model.setDecision(jobID: jobID, decision: "hidden", notes: decisionNotes)
                        dismiss()
                    }
                }
                .appBorderedButton()
                if job.decision != nil {
                    Button("Clear decision") {
                        Task {
                            await model.setDecision(jobID: jobID, decision: "clear")
                            dismiss()
                        }
                    }
                    .appBorderedButton()
                }
                Button("Close job detail") { dismiss() }
                    .appBorderedButton()
            }
        }
        .surfaceCardStyle()
    }
}