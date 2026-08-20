import SwiftUI

/// La copertina ingrandita a schermo intero.
/// Si allarga col pizzico, si sposta trascinando quando è ingrandita,
/// e un doppio tocco alterna fra dimensione piena e adattata.
struct CoverZoomView: View {
    var image: PlatformImage?
    var url: URL?
    var titolo: String

    @Environment(\.dismiss) private var dismiss

    @State private var scala: CGFloat = 1
    @State private var scalaDiPartenza: CGFloat = 1
    @State private var spostamento: CGSize = .zero
    @State private var spostamentoDiPartenza: CGSize = .zero

    private let scalaMassima: CGFloat = 5

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            copertina
                .scaleEffect(scala)
                .offset(spostamento)
                .gesture(pizzico)
                .simultaneousGesture(trascinamento)
                .onTapGesture(count: 2) { alterna() }
                .accessibilityLabel("Copertina di \(titolo)")

            VStack {
                HStack {
                    Spacer()
                    Button {
                        dismiss()
                    } label: {
                        Image(systemName: "xmark")
                            .font(.title3.weight(.semibold))
                            .foregroundStyle(.white)
                            .padding(12)
                            .background(.black.opacity(0.45), in: Circle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Chiudi")
                    .padding(.trailing, 16)
                    .padding(.top, 12)
                }
                Spacer()
            }
        }
        #if os(macOS)
        .frame(minWidth: 520, minHeight: 680)
        #endif
    }

    @ViewBuilder
    private var copertina: some View {
        if let image {
            Image(platformImage: image)
                .resizable()
                .scaledToFit()
        } else if let url {
            AsyncImage(url: url) { fase in
                switch fase {
                case .success(let immagine):
                    immagine.resizable().scaledToFit()
                case .empty:
                    ProgressView().tint(.white)
                default:
                    segnaposto
                }
            }
        } else {
            segnaposto
        }
    }

    private var segnaposto: some View {
        VStack(spacing: 14) {
            Image(systemName: "book.closed.fill")
                .font(.system(size: 64))
            Text("Copertina non disponibile")
                .font(.callout)
        }
        .foregroundStyle(.white.opacity(0.6))
    }

    // MARK: - Gesti

    private var pizzico: some Gesture {
        MagnifyGesture()
            .onChanged { valore in
                scala = min(max(scalaDiPartenza * valore.magnification, 1), scalaMassima)
            }
            .onEnded { _ in
                scalaDiPartenza = scala
                if scala <= 1 { azzera() }
            }
    }

    private var trascinamento: some Gesture {
        DragGesture()
            .onChanged { valore in
                // Trascinare serve solo quando l'immagine e' piu' grande
                // dello schermo, altrimenti la si sposterebbe nel vuoto.
                guard scala > 1 else { return }
                spostamento = CGSize(
                    width: spostamentoDiPartenza.width + valore.translation.width,
                    height: spostamentoDiPartenza.height + valore.translation.height
                )
            }
            .onEnded { _ in
                spostamentoDiPartenza = spostamento
            }
    }

    private func alterna() {
        withAnimation(.spring(duration: 0.3)) {
            if scala > 1 {
                azzera()
            } else {
                scala = 2.5
                scalaDiPartenza = 2.5
            }
        }
    }

    private func azzera() {
        scala = 1
        scalaDiPartenza = 1
        spostamento = .zero
        spostamentoDiPartenza = .zero
    }
}
