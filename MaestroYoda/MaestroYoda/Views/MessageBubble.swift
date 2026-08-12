import SwiftUI

struct MessageBubble: View {
    let message: Message

    private var isYoda: Bool { message.role == .yoda }

    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            if !isYoda { Spacer(minLength: 48) }
            if isYoda { YodaAvatarView(size: 30) }

            Text(message.text)
                .font(isYoda ? .system(.body, design: .serif) : .system(.body, design: .rounded))
                .foregroundStyle(isYoda ? Color(hex: 0xE8F5D8) : .white)
                .padding(.horizontal, 15)
                .padding(.vertical, 11)
                .background(bubbleShape)

            if isYoda { Spacer(minLength: 48) }
        }
        .frame(maxWidth: .infinity, alignment: isYoda ? .leading : .trailing)
    }

    @ViewBuilder
    private var bubbleShape: some View {
        if isYoda {
            UnevenRoundedRectangle(
                topLeadingRadius: 6,
                bottomLeadingRadius: 18,
                bottomTrailingRadius: 18,
                topTrailingRadius: 18
            )
            .fill(
                LinearGradient(
                    colors: [Color(hex: 0x1E3524), Color(hex: 0x142A1E)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .overlay(
                UnevenRoundedRectangle(
                    topLeadingRadius: 6,
                    bottomLeadingRadius: 18,
                    bottomTrailingRadius: 18,
                    topTrailingRadius: 18
                )
                .strokeBorder(Color.saberGreen.opacity(0.35), lineWidth: 1)
            )
        } else {
            UnevenRoundedRectangle(
                topLeadingRadius: 18,
                bottomLeadingRadius: 18,
                bottomTrailingRadius: 18,
                topTrailingRadius: 6
            )
            .fill(
                LinearGradient(
                    colors: [Color(hex: 0x4A3FBF), Color(hex: 0x2E6BD6)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
        }
    }
}
