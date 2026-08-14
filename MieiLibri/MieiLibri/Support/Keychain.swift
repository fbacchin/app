import Foundation
import Security

/// Accesso minimale al portachiavi per conservare la sessione dell'account.
enum Keychain {
    private static let service = "com.bacchin.MieiLibri"

    /// Attributi comuni a tutte le operazioni. Su macOS si richiede
    /// esplicitamente il portachiavi moderno, l'unico compatibile con
    /// l'app sandbox e con lo stesso comportamento di iOS.
    private static func baseQuery(key: String) -> [String: Any] {
        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
        ]
        #if os(macOS)
        query[kSecUseDataProtectionKeychain as String] = true
        #endif
        return query
    }

    static func save(_ data: Data, key: String) {
        delete(key: key)
        var query = baseQuery(key: key)
        query[kSecValueData as String] = data
        query[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        _ = SecItemAdd(query as CFDictionary, nil)
    }

    static func load(key: String) -> Data? {
        var query = baseQuery(key: key)
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess else { return nil }
        return item as? Data
    }

    static func delete(key: String) {
        _ = SecItemDelete(baseQuery(key: key) as CFDictionary)
    }
}
