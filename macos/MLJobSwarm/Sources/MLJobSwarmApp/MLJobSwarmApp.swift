import MLJobSwarmCore
import SwiftUI

@main
struct MLJobSwarmApp: App {
    @StateObject private var model = AppModel(backend: BackendManager())

    var body: some Scene {
        WindowGroup {
            RootView(model: model)
                .frame(minWidth: 1080, minHeight: 720)
        }
        .defaultSize(width: 1280, height: 840)
    }
}