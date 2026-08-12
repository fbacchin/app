import SwiftUI

/// Primo passo: il Maestro pone la domanda rituale.
struct WelcomeView: View {
    let onStart: () -> Void
    @State private var appeared = false

    var body: some View {
        VStack(spacing: 26) {
            Spacer()

            YodaAvatarView(size: 170)
                .scaleEffect(appeared ? 1 : 0.7)
                .opacity(appeared ? 1 : 0)

            VStack(spacing: 8) {
                Text("MAESTRO YODA")
                    .font(.system(size: 30, weight: .heavy, design: .rounded))
                    .tracking(6)
                    .foregroundStyle(Color.swYellow)
                    .shadow(color: Color.swYellow.opacity(0.5), radius: 12)
                Text("Il tuo consigliere galattico")
                    .font(.subheadline)
                    .foregroundStyle(.white.opacity(0.7))
            }
            .opacity(appeared ? 1 : 0)

            Spacer()

            TypewriterText(text: "«Su cosa avere risposta tu vuoi?»")
                .font(.system(.title2, design: .serif).italic())
                .foregroundStyle(.white)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 30)

            Spacer()

            Button(action: onStart) {
                Text("Parla con il Maestro")
                    .font(.headline)
                    .foregroundStyle(Color(hex: 0x06210B))
                    .padding(.horizontal, 34)
                    .padding(.vertical, 15)
                    .background(Capsule().fill(Color.saberGreen))
                    .shadow(color: Color.saberGreen.opacity(0.6), radius: 16)
            }
            .opacity(appeared ? 1 : 0)

            Spacer().frame(height: 30)
        }
        .onAppear {
            withAnimation(.spring(duration: 0.9)) { appeared = true }
        }
    }
}

/// Testo che appare lettera per lettera, come un messaggio dallo spazio profondo.
struct TypewriterText: View {
    let text: String
    var speed: Double = 0.05
    @State private var visibleCount = 0

    var body: some View {
        ZStack(alignment: .topLeading) {
            Text(text).opacity(0)
            Text(String(text.prefix(visibleCount)))
        }
        .task {
            visibleCount = 0
            while visibleCount < text.count {
                try? await Task.sleep(for: .seconds(speed))
                visibleCount += 1
            }
        }
    }
}
