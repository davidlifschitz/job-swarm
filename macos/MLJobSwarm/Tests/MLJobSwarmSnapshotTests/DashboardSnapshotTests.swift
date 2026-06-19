import SnapshottingTests

final class MLJobSwarmSnapshotTests: SnapshotTest {
    override class func snapshotPreviewModules() -> [String]? {
        ["MLJobSwarmCore"]
    }
}