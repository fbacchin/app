import SwiftUI

@main
struct TetrisApp: App {
    var body: some Scene {
        WindowGroup {
            TetrisView()
                .preferredColorScheme(.dark)
                .statusBarHidden()
        }
    }
}
