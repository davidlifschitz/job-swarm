// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "MLJobSwarm",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "MLJobSwarm", targets: ["MLJobSwarmApp"]),
        .library(name: "MLJobSwarmCore", targets: ["MLJobSwarmCore"]),
    ],
    dependencies: [
        .package(url: "https://github.com/getsentry/SnapshotPreviews", branch: "main"),
    ],
    targets: [
        .executableTarget(
            name: "MLJobSwarmApp",
            dependencies: ["MLJobSwarmCore"]
        ),
        .target(
            name: "MLJobSwarmCore",
            dependencies: [
                .product(name: "SnapshotPreferences", package: "SnapshotPreviews"),
            ],
            resources: [.process("Resources")],
            linkerSettings: [
                .linkedLibrary("sqlite3"),
            ]
        ),
        .testTarget(
            name: "MLJobSwarmSnapshotTests",
            dependencies: [
                "MLJobSwarmCore",
                .product(name: "SnapshottingTests", package: "SnapshotPreviews"),
            ]
        ),
    ]
)