import Foundation

#if DEBUG
enum PreviewFixtures {
    @MainActor
    static func appModel() -> AppModel {
        AppModel(backend: BackendManager.preview())
    }

    static let dashboard = DashboardResponse(
        targetProfileId: 1,
        decisionFilter: "all",
        connectionFilter: "with_connections",
        connectionCount: 3,
        catalogRefreshedAt: "2026-06-17T12:00:00Z",
        fitReviewAvailable: true,
        profileSummary: ProfileSummary(
            id: 1,
            name: "Senior ML profile",
            version: 1,
            resumeFilename: "resume.pdf",
            desiredTitles: ["Machine Learning Engineer"],
            levels: ["senior"],
            locations: ["New York"],
            remoteModes: ["remote"],
            companyStages: ["growth"],
            keywords: ["pytorch", "ranking"]
        ),
        companies: [
            CompanyGroup(
                companyId: 10,
                name: "Dataiku",
                visibleJobs: [
                    JobFit(
                        jobId: 101,
                        title: "Senior ML Engineer",
                        fitScore: 92,
                        label: "Strong fit",
                        reasons: ["Role and skills fit"],
                        risks: [],
                        recommendation: "Prioritize",
                        decision: nil,
                        notes: ""
                    )
                ],
                mismatchRiskJobs: [],
                hiddenJobs: [],
                filteredOutCount: 0,
                linkedinConnections: [
                    LinkedInConnection(
                        id: 1,
                        profileURL: "https://www.linkedin.com/in/jamie-example-fixture",
                        firstName: "Jamie",
                        lastName: "Example",
                        company: "Dataiku",
                        position: "Technical Talent Acquisition Partner",
                        connectedOn: "12 Jun 2026"
                    )
                ],
                connectionCount: 1
            )
        ],
        rulesPreviewJobs: [],
        unreviewedJobs: [],
        resumeSections: [],
        resumeSuggestions: []
    )

    static let connections = ConnectionsResponse(
        connectionCount: 3,
        groupedCompanies: [
            ConnectionsGroup(
                company: "Dataiku",
                connections: [
                    LinkedInConnection(
                        id: 1,
                        profileURL: "https://www.linkedin.com/in/jamie-example-fixture",
                        firstName: "Jamie",
                        lastName: "Example",
                        company: "Dataiku",
                        position: "Technical Talent Acquisition Partner",
                        connectedOn: "12 Jun 2026"
                    )
                ]
            )
        ],
        matchedCatalog: [
            CatalogMatch(
                companyId: 10,
                companyName: "Dataiku",
                connections: [
                    LinkedInConnection(
                        id: 1,
                        profileURL: "https://www.linkedin.com/in/jamie-example-fixture",
                        firstName: "Jamie",
                        lastName: "Example",
                        company: "Dataiku",
                        position: "Technical Talent Acquisition Partner",
                        connectedOn: "12 Jun 2026"
                    )
                ]
            )
        ]
    )
}
#endif