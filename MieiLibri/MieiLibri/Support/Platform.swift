import SwiftUI

#if canImport(UIKit)
import UIKit
typealias PlatformImage = UIImage

extension Image {
    init(platformImage: PlatformImage) {
        self.init(uiImage: platformImage)
    }
}
#elseif canImport(AppKit)
import AppKit
typealias PlatformImage = NSImage

extension Image {
    init(platformImage: PlatformImage) {
        self.init(nsImage: platformImage)
    }
}
#endif

/// Feedback aptico di conferma (solo iPhone).
func playSuccessHaptic() {
    #if os(iOS)
    UINotificationFeedbackGenerator().notificationOccurred(.success)
    #endif
}

extension View {
    /// Titolo di navigazione compatto su iOS; senza effetto su macOS.
    func inlineNavigationTitle() -> some View {
        #if os(iOS)
        return navigationBarTitleDisplayMode(.inline)
        #else
        return self
        #endif
    }

    /// Chiude la tastiera durante lo scorrimento (solo iOS).
    func dismissKeyboardOnScroll() -> some View {
        #if os(iOS)
        return scrollDismissesKeyboard(.immediately)
        #else
        return self
        #endif
    }

    /// Impostazioni consigliate per un campo email.
    func emailFieldStyle() -> some View {
        #if os(iOS)
        return keyboardType(.emailAddress)
            .textInputAutocapitalization(.never)
            .textContentType(.emailAddress)
            .autocorrectionDisabled()
        #else
        return autocorrectionDisabled()
        #endif
    }

    /// Tastiera numerica dove esiste (iPhone e iPad).
    func numericFieldStyle() -> some View {
        #if os(iOS)
        return keyboardType(.numberPad)
        #else
        return self
        #endif
    }

    /// Impostazioni consigliate per un campo password.
    func passwordFieldStyle() -> some View {
        #if os(iOS)
        return textContentType(.password)
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
        #else
        return autocorrectionDisabled()
        #endif
    }
}
