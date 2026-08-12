import SwiftUI

struct ChatView: View {
    @ObservedObject var viewModel: ChatViewModel
    @State private var draft = ""
    @FocusState private var inputFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            header
            messagesList
            inputBar
        }
    }

    // MARK: - Intestazione

    private var header: some View {
        HStack(spacing: 12) {
            YodaAvatarView(size: 44)
            VStack(alignment: .leading, spacing: 2) {
                Text("Maestro Yoda")
                    .font(.headline)
                    .tracking(1)
                    .foregroundStyle(Color.swYellow)
                Text(viewModel.isTyping ? "sta meditando…" : "in ascolto nella Forza")
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.6))
            }
            Spacer()
            Image(systemName: "sparkles")
                .foregroundStyle(Color.swYellow.opacity(0.8))
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(.ultraThinMaterial)
        .overlay(alignment: .bottom) {
            Rectangle()
                .fill(Color.saberGreen.opacity(0.25))
                .frame(height: 0.5)
        }
    }

    // MARK: - Messaggi

    private var messagesList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 14) {
                    ForEach(viewModel.messages) { message in
                        MessageBubble(message: message)
                            .id(message.id)
                    }
                    if viewModel.isTyping {
                        TypingIndicator()
                            .id("typing")
                    }
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 16)
            }
            .scrollDismissesKeyboard(.interactively)
            .onChange(of: viewModel.messages.count) {
                withAnimation(.easeOut(duration: 0.25)) { scrollToBottom(proxy) }
            }
            .onChange(of: viewModel.isTyping) {
                withAnimation(.easeOut(duration: 0.25)) { scrollToBottom(proxy) }
            }
        }
    }

    private func scrollToBottom(_ proxy: ScrollViewProxy) {
        if viewModel.isTyping {
            proxy.scrollTo("typing", anchor: .bottom)
        } else if let last = viewModel.messages.last {
            proxy.scrollTo(last.id, anchor: .bottom)
        }
    }

    // MARK: - Barra di scrittura

    private var inputBar: some View {
        HStack(spacing: 10) {
            TextField("Chiedi al Maestro…", text: $draft)
                .textFieldStyle(.plain)
                .focused($inputFocused)
                .foregroundStyle(.white)
                .tint(Color.saberGreen)
                .submitLabel(.send)
                .onSubmit(send)
                .padding(.horizontal, 16)
                .padding(.vertical, 11)
                .background(
                    Capsule()
                        .fill(Color.white.opacity(0.08))
                        .overlay(Capsule().strokeBorder(Color.white.opacity(0.15)))
                )

            Button(action: send) {
                Image(systemName: "arrow.up")
                    .font(.system(size: 17, weight: .bold))
                    .foregroundStyle(Color(hex: 0x06210B))
                    .frame(width: 40, height: 40)
                    .background(Circle().fill(Color.saberGreen))
                    .shadow(color: Color.saberGreen.opacity(0.55), radius: 9)
            }
            .disabled(draftIsEmpty)
            .opacity(draftIsEmpty ? 0.45 : 1)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(.ultraThinMaterial)
        .sensoryFeedback(.impact(weight: .light), trigger: viewModel.messages.count)
    }

    private var draftIsEmpty: Bool {
        draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    private func send() {
        guard !draftIsEmpty else { return }
        viewModel.send(draft)
        draft = ""
    }
}
