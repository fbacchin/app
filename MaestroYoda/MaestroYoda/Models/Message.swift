import Foundation

struct Message: Identifiable, Equatable {
    enum Role {
        case yoda
        case user
    }

    let id = UUID()
    let role: Role
    let text: String
}
