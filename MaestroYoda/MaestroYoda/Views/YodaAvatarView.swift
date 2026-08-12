import SwiftUI

/// Distintivo circolare con il ritratto del Maestro e un alone verde.
struct YodaAvatarView: View {
    var size: CGFloat = 40

    var body: some View {
        Image("YodaPortrait")
            .resizable()
            .scaledToFill()
            .frame(width: size, height: size)
            .clipShape(Circle())
            .overlay(
                Circle().strokeBorder(Color.saberGreen.opacity(0.7), lineWidth: max(1, size * 0.022))
            )
            .shadow(color: Color.saberGreen.opacity(0.45), radius: size * 0.12)
    }
}
