import SwiftUI

@main
struct ValichiLiveApp: App {
    @StateObject private var data = DataStore()
    @StateObject private var store = StoreManager()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(data)
                .environmentObject(store)
        }
    }
}
