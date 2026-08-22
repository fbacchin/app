import SwiftUI

/// Testo allineato su entrambi i margini.
///
/// SwiftUI non offre la giustificazione: `multilineTextAlignment` prevede solo
/// sinistra, centro e destra. Serve quindi la vista di testo di sistema, a cui
/// si può applicare uno stile di paragrafo giustificato.
struct TestoGiustificato: View {
    enum Stile {
        case corpo
        case piccolo

        var carattere: PlatformFont {
            switch self {
            case .corpo: return PlatformFont.preferredFont(forTextStyle: .callout)
            case .piccolo: return PlatformFont.preferredFont(forTextStyle: .caption1)
            }
        }
    }

    var testo: String
    var stile: Stile = .corpo
    /// Zero significa nessun limite.
    var righeMassime: Int = 0
    var attenuato = true

    var body: some View {
        RappresentazioneTesto(
            testo: testo,
            carattere: stile.carattere,
            colore: attenuato ? .secondaryPlatformLabel : .primaryPlatformLabel,
            righeMassime: righeMassime
        )
        .accessibilityLabel(testo)
    }
}

extension PlatformColor {
    static var secondaryPlatformLabel: PlatformColor {
        #if canImport(UIKit)
        return .secondaryLabel
        #else
        return .secondaryLabelColor
        #endif
    }

    static var primaryPlatformLabel: PlatformColor {
        #if canImport(UIKit)
        return .label
        #else
        return .labelColor
        #endif
    }
}

private func stileParagrafo(righeMassime: Int) -> NSParagraphStyle {
    let stile = NSMutableParagraphStyle()
    stile.alignment = .justified
    // Senza questo, con parole lunghe la giustificazione apre spazi enormi
    // fra le parole invece di spezzarle.
    stile.hyphenationFactor = 1
    stile.lineBreakMode = righeMassime > 0 ? .byTruncatingTail : .byWordWrapping
    return stile
}

#if canImport(UIKit)

private struct RappresentazioneTesto: UIViewRepresentable {
    let testo: String
    let carattere: PlatformFont
    let colore: PlatformColor
    let righeMassime: Int

    func makeUIView(context: Context) -> UILabel {
        let etichetta = UILabel()
        etichetta.numberOfLines = 0
        etichetta.setContentCompressionResistancePriority(.required, for: .vertical)
        etichetta.setContentHuggingPriority(.required, for: .vertical)
        return etichetta
    }

    func updateUIView(_ etichetta: UILabel, context: Context) {
        etichetta.numberOfLines = righeMassime
        etichetta.attributedText = NSAttributedString(
            string: testo,
            attributes: [
                .font: carattere,
                .foregroundColor: colore,
                .paragraphStyle: stileParagrafo(righeMassime: righeMassime),
            ]
        )
    }

    func sizeThatFits(_ proposta: ProposedViewSize, uiView: UILabel, context: Context) -> CGSize? {
        let larghezza = proposta.width ?? uiView.bounds.width
        guard larghezza > 0 else { return nil }
        let misura = uiView.sizeThatFits(CGSize(width: larghezza, height: .greatestFiniteMagnitude))
        return CGSize(width: larghezza, height: misura.height)
    }
}

#else

private struct RappresentazioneTesto: NSViewRepresentable {
    let testo: String
    let carattere: PlatformFont
    let colore: PlatformColor
    let righeMassime: Int

    func makeNSView(context: Context) -> NSTextField {
        let campo = NSTextField(labelWithString: "")
        campo.isBezeled = false
        campo.drawsBackground = false
        campo.isEditable = false
        campo.isSelectable = false
        campo.cell?.wraps = true
        campo.cell?.isScrollable = false
        return campo
    }

    func updateNSView(_ campo: NSTextField, context: Context) {
        campo.maximumNumberOfLines = righeMassime
        campo.attributedStringValue = NSAttributedString(
            string: testo,
            attributes: [
                .font: carattere,
                .foregroundColor: colore,
                .paragraphStyle: stileParagrafo(righeMassime: righeMassime),
            ]
        )
    }

    func sizeThatFits(_ proposta: ProposedViewSize, nsView: NSTextField, context: Context) -> CGSize? {
        let larghezza = proposta.width ?? nsView.bounds.width
        guard larghezza > 0 else { return nil }
        let misura = nsView.sizeThatFits(CGSize(width: larghezza, height: .greatestFiniteMagnitude))
        return CGSize(width: larghezza, height: misura.height)
    }
}

#endif
