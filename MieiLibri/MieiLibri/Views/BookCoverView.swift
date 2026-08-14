import SwiftUI

/// Mostra la copertina di un libro: prima quella salvata in locale,
/// altrimenti la scarica dall'URL remoto, con un segnaposto di riserva.
struct BookCoverView: View {
    var image: PlatformImage?
    var url: URL?
    var width: CGFloat

    private var height: CGFloat { width * 1.5 }
    private var cornerRadius: CGFloat { width * 0.09 }

    var body: some View {
        Group {
            if let image = image {
                Image(platformImage: image)
                    .resizable()
                    .scaledToFill()
            } else if let url = url {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let remoteImage):
                        remoteImage
                            .resizable()
                            .scaledToFill()
                    case .empty:
                        ZStack {
                            placeholderBackground
                            ProgressView()
                        }
                    default:
                        placeholder
                    }
                }
            } else {
                placeholder
            }
        }
        .frame(width: width, height: height)
        .clipShape(RoundedRectangle(cornerRadius: cornerRadius))
        .overlay {
            RoundedRectangle(cornerRadius: cornerRadius)
                .strokeBorder(Color.black.opacity(0.1), lineWidth: 0.5)
        }
    }

    private var placeholder: some View {
        ZStack {
            placeholderBackground
            Image(systemName: "book.closed.fill")
                .font(.system(size: width * 0.4))
                .foregroundStyle(.secondary)
        }
    }

    private var placeholderBackground: some View {
        Rectangle().fill(.quaternary)
    }
}
