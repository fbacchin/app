import Foundation

/// Converte il testo Markdown in una pagina HTML completa e autosufficiente,
/// pronta per essere caricata in WKWebView (anteprima e stampa).
enum MarkdownRenderer {

    private static let markedJS: String = loadResource(named: "marked.min", withExtension: "js") ?? ""
    private static let styleSheet: String = loadResource(named: "markdown", withExtension: "css") ?? ""

    private static func loadResource(named name: String, withExtension ext: String) -> String? {
        guard let url = Bundle.main.url(forResource: name, withExtension: ext) else { return nil }
        return try? String(contentsOf: url, encoding: .utf8)
    }

    /// Serializza il testo come literal JavaScript sicuro dentro un tag <script>:
    /// ogni "<" viene emesso come <, così nessuna sequenza HTML può chiudere lo script.
    private static func javaScriptLiteral(_ text: String) -> String {
        let data = (try? JSONSerialization.data(withJSONObject: text, options: .fragmentsAllowed)) ?? Data("\"\"".utf8)
        var literal = String(data: data, encoding: .utf8) ?? "\"\""
        literal = literal.replacingOccurrences(of: "<", with: "\\u003c")
        literal = literal.replacingOccurrences(of: "\u{2028}", with: "\\u2028")
        literal = literal.replacingOccurrences(of: "\u{2029}", with: "\\u2029")
        return literal
    }

    /// Pagina HTML completa per il Markdown dato. Se marked.js non fosse nel bundle,
    /// la pagina mostra comunque il testo semplice (fallback in JavaScript).
    static func page(for markdown: String) -> String {
        let literal = javaScriptLiteral(markdown)
        return """
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <meta name="color-scheme" content="light dark">
        <style>
        \(styleSheet)
        </style>
        <script>
        \(markedJS)
        </script>
        </head>
        <body>
        <article id="content" class="markdown-body"></article>
        <script>
        "use strict";
        (function () {
            var source = \(literal);
            var content = document.getElementById("content");
            function showPlainText() {
                content.textContent = source;
                content.style.whiteSpace = "pre-wrap";
                content.style.fontFamily = "ui-monospace, Menlo, monospace";
            }
            try {
                if (typeof marked === "undefined") {
                    showPlainText();
                    return;
                }
                if (marked.use) {
                    marked.use({ gfm: true, breaks: false });
                }
                content.innerHTML = marked.parse ? marked.parse(source) : marked(source);

                // Caselle degli elenchi attività: non interattive e senza puntino elenco.
                var boxes = content.querySelectorAll("li input[type=checkbox]");
                for (var i = 0; i < boxes.length; i++) {
                    boxes[i].disabled = true;
                    var item = boxes[i].closest("li");
                    if (item) { item.classList.add("task-list-item"); }
                }

                // Ancore per i titoli (stile GitHub), così i sommari interni funzionano.
                var seen = Object.create(null);
                var headings = content.querySelectorAll("h1,h2,h3,h4,h5,h6");
                for (var j = 0; j < headings.length; j++) {
                    var heading = headings[j];
                    if (heading.id) { continue; }
                    var slug = heading.textContent.trim().toLowerCase()
                        .replace(/[^\\p{L}\\p{N}\\s_-]/gu, "")
                        .replace(/\\s+/g, "-")
                        .replace(/-+/g, "-");
                    if (!slug) { slug = "sezione"; }
                    var id = slug;
                    var n = 1;
                    while (seen[id] || document.getElementById(id)) {
                        id = slug + "-" + n;
                        n++;
                    }
                    seen[id] = true;
                    heading.id = id;
                }
            } catch (error) {
                showPlainText();
            }
        })();
        </script>
        </body>
        </html>
        """
    }
}
