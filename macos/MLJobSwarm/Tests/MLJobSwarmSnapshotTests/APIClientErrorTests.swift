import XCTest
@testable import MLJobSwarmCore

final class APIClientErrorTests: XCTestCase {
    func testBadStatusUsesDetailMessage() {
        let error = APIClientError.badStatus(403, "target profile not accessible")
        XCTAssertEqual(error.errorDescription, "target profile not accessible")
    }

    func testBadStatusFallsBackToStatusCode() {
        let error = APIClientError.badStatus(401, nil)
        XCTAssertEqual(error.errorDescription, "API request failed with status 401")
    }
}
