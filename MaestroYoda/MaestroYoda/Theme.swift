import SwiftUI

extension Color {
    /// Giallo "Guerre Stellari" per titoli e dettagli.
    static let swYellow = Color(hex: 0xFFE81F)
    /// Verde spada laser di Yoda, colore d'accento dell'app.
    static let saberGreen = Color(hex: 0x7ED957)

    init(hex: UInt32) {
        let red = Double((hex >> 16) & 0xFF) / 255
        let green = Double((hex >> 8) & 0xFF) / 255
        let blue = Double(hex & 0xFF) / 255
        self.init(red: red, green: green, blue: blue)
    }
}
