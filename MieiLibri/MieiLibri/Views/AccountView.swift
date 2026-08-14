import SwiftUI

/// Gestione dell'account di sincronizzazione.
/// Come "gate" al primo avvio propone accesso, registrazione o uso locale;
/// come scheda richiamata dalla toolbar mostra lo stato e le azioni.
struct AccountView: View {
    @EnvironmentObject private var library: Library
    @Environment(\.dismiss) private var dismiss
    var isGate = false

    @State private var email = ""
    @State private var password = ""
    @State private var isWorking = false
    @State private var message: String?

    var body: some View {
        Form {
            if library.isSignedIn {
                signedInContent
            } else {
                signInContent
            }
        }
        .formStyle(.grouped)
        .navigationTitle(isGate ? "Benvenuto" : "Account")
        .toolbar {
            if !isGate {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Chiudi") { dismiss() }
                }
            }
        }
        #if os(macOS)
        .frame(minWidth: 440, minHeight: 420)
        #endif
    }

    // MARK: - Account collegato

    @ViewBuilder
    private var signedInContent: some View {
        Section("Account") {
            LabeledContent("Email", value: library.sessionEmail ?? "—")
        }
        Section("Sincronizzazione") {
            if let status = library.syncStatusText {
                Text(status)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            Button {
                Task { await library.syncNow() }
            } label: {
                if library.isSyncing {
                    HStack(spacing: 8) {
                        ProgressView()
                        Text("Sincronizzazione in corso…")
                    }
                } else {
                    Text("Sincronizza ora")
                }
            }
            .disabled(library.isSyncing)
        }
        Section {
            Button("Esci", role: .destructive) {
                library.signOut()
                if !isGate { dismiss() }
            }
        } footer: {
            Text("Uscendo, i libri restano salvati su questo dispositivo e sul server.")
        }
    }

    // MARK: - Accesso o registrazione

    @ViewBuilder
    private var signInContent: some View {
        if !library.syncAvailable {
            notConfiguredContent
        } else {
            credentialsContent
        }
    }

    /// Il file SupabaseConfig.swift non è ancora stato compilato.
    @ViewBuilder
    private var notConfiguredContent: some View {
        Section {
            Label("Sincronizzazione non configurata", systemImage: "externaldrive.badge.xmark")
                .font(.headline)
            Text("Per condividere i libri tra iPhone e Mac inserisci l'indirizzo e la chiave del progetto Supabase nel file SupabaseConfig.swift. Le istruzioni sono nel README del progetto.")
                .font(.callout)
                .foregroundStyle(.secondary)
        } footer: {
            Text("Fino ad allora l'app funziona normalmente e salva i libri su questo dispositivo.")
        }
    }

    @ViewBuilder
    private var credentialsContent: some View {
        Section {
            Text("Con un account gratuito i tuoi libri si sincronizzano tra iPhone e Mac.")
                .font(.callout)
        }
        Section("Credenziali") {
            TextField("Email", text: $email)
                .emailFieldStyle()
            SecureField("Password (almeno 6 caratteri)", text: $password)
                .passwordFieldStyle()
        }
        if let message {
            Section {
                Text(message)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
        Section {
            Button {
                authenticate(asNewUser: false)
            } label: {
                centeredLabel("Accedi")
            }
            .disabled(!canSubmit)
            Button {
                authenticate(asNewUser: true)
            } label: {
                centeredLabel("Registrati")
            }
            .disabled(!canSubmit)
        } footer: {
            Text("Alla prima registrazione riceverai un'email di conferma: apri il collegamento che contiene e poi premi Accedi.")
        }
        if isGate {
            Section {
                Button("Usa solo su questo dispositivo") {
                    library.localOnly = true
                }
            } footer: {
                Text("Potrai attivare la sincronizzazione in seguito dal simbolo della persona in alto.")
            }
        }
    }

    private var canSubmit: Bool {
        !isWorking && trimmedEmail.contains("@") && password.count >= 6
    }

    private var trimmedEmail: String {
        email.trimmingCharacters(in: .whitespaces)
    }

    private func centeredLabel(_ title: String) -> some View {
        HStack {
            Spacer()
            if isWorking {
                ProgressView()
            } else {
                Text(title)
            }
            Spacer()
        }
    }

    private func authenticate(asNewUser: Bool) {
        isWorking = true
        message = nil
        Task {
            do {
                if asNewUser {
                    let needsConfirmation = try await library.signUp(email: trimmedEmail, password: password)
                    if needsConfirmation {
                        message = "Registrazione avviata: apri l'email di conferma, tocca il collegamento e poi premi Accedi."
                    } else if !isGate {
                        dismiss()
                    }
                } else {
                    try await library.signIn(email: trimmedEmail, password: password)
                    if !isGate { dismiss() }
                }
            } catch {
                message = error.localizedDescription
            }
            isWorking = false
        }
    }
}
