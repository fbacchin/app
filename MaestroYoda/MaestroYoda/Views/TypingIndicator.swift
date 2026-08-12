import SwiftUI

/// Tre puntini che danzano mentre il Maestro medita la risposta.
struct TypingIndicator: View {
    @State private var animating = false

    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            YodaAvatarView(size: 30)
            HStack(spacing: 5) {
                ForEach(0..<3) { index in
                    Circle()
                        .fill(Color(hex: 0x9BD77A))
                        .frame(width: 7, height: 7)
                        .offset(y: animating ? -4 : 2)
                        .animation(
                            .easeInOut(duration: 0.5)
                                .repeatForever(autoreverses: true)
                                .delay(Double(index) * 0.16),
                            value: animating
                        )
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .background(
                UnevenRoundedRectangle(
                    topLeadingRadius: 6,
                    bottomLeadingRadius: 18,
                    bottomTrailingRadius: 18,
                    topTrailingRadius: 18
                )
                .fill(Color(hex: 0x1E3524).opacity(0.9))
            )
            Spacer()
        }
        .onAppear { animating = true }
    }
}
