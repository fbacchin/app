import SwiftUI

struct ContentView: View {
    @StateObject private var viewModel = ChatViewModel()
    @State private var showWelcome = true

    var body: some View {
        ZStack {
            SpaceBackground()
            if showWelcome {
                WelcomeView {
                    withAnimation(.easeInOut(duration: 0.7)) { showWelcome = false }
                    viewModel.startConversation()
                }
                .transition(.opacity)
            } else {
                ChatView(viewModel: viewModel)
                    .transition(.opacity)
            }
        }
    }
}

#Preview {
    ContentView()
}
