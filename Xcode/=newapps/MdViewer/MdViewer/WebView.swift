import AppKit
import SwiftUI
import WebKit

/// Riferimento condiviso alla WKWebView, usato da ContentView per stampa, PDF e zoom.
final class WebViewProxy: ObservableObject {
    weak var webView: WKWebView?
}

/// Wrapper SwiftUI della WKWebView che mostra l'anteprima renderizzata.
struct MarkdownWebView: NSViewRepresentable {
    let html: String
    let baseURL: URL?
    let zoom: Double
    let reloadToken: Int
    let proxy: WebViewProxy

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    func makeNSView(context: Context) -> WKWebView {
        let webView = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
        webView.navigationDelegate = context.coordinator
        webView.allowsMagnification = true
        proxy.webView = webView
        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        context.coordinator.parent = self
        if webView.pageZoom != zoom {
            webView.pageZoom = zoom
        }
        if context.coordinator.lastHTML != html || context.coordinator.lastReloadToken != reloadToken {
            context.coordinator.lastHTML = html
            context.coordinator.lastReloadToken = reloadToken
            webView.loadHTMLString(html, baseURL: baseURL)
        }
    }

    final class Coordinator: NSObject, WKNavigationDelegate {
        var parent: MarkdownWebView
        var lastHTML: String?
        var lastReloadToken: Int = .min

        init(_ parent: MarkdownWebView) {
            self.parent = parent
        }

        func webView(_ webView: WKWebView,
                     decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard navigationAction.navigationType == .linkActivated,
                  let url = navigationAction.request.url else {
                decisionHandler(.allow)
                return
            }
            let scheme = url.scheme?.lowercased() ?? ""
            if scheme == "http" || scheme == "https" || scheme == "mailto" {
                // I link esterni si aprono nel browser predefinito, non nell'anteprima.
                decisionHandler(.cancel)
                NSWorkspace.shared.open(url)
                return
            }
            if url.isFileURL {
                if url.fragment != nil, url.path == parent.baseURL?.path {
                    // Ancora interna alla pagina (sommario): lasciala scorrere.
                    decisionHandler(.allow)
                    return
                }
                // Altri file locali (es. un altro .md): aprili con l'app predefinita.
                decisionHandler(.cancel)
                NSWorkspace.shared.open(url)
                return
            }
            decisionHandler(.allow)
        }
    }
}
