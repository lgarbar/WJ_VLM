import SwiftUI
import PhotosUI
import Combine

// MARK: - Server Configuration
// Using ObservableObject so all views refresh when settings changs

class ServerConfig: ObservableObject {
    // We use @AppStorage to persist to the device
    @AppStorage("server_ip") var ip: String = "10.0.0.144" {
        willSet { objectWillChange.send() }
    }
    
    @AppStorage("server_port") var port: String = "5001" {
        willSet { objectWillChange.send() }
    }
    
    var baseURL: String {
        "http://\(ip):\(port)"
    }
}

struct ContentView: View {
    @StateObject private var config = ServerConfig()
    @State private var userID: String = ""
    @State private var path = NavigationPath()
    @State private var showSettings = false

    var body: some View {
        NavigationStack(path: $path) {
            VStack(spacing: 20) {
                Text("WJ Math Scorer")
                    .font(.largeTitle)
                    .fontWeight(.bold)
                
                TextField("Enter User ID (e.g. DGB)", text: $userID)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.characters)
                    .padding(.horizontal)
                
                Button(action: { path.append(userID) }) {
                    Text("Enter")
                        .frame(maxWidth: .infinity)
                }
                .disabled(userID.isEmpty)
                .buttonStyle(.borderedProminent)
                .padding(.horizontal)
                
                Text("Connected to: \(config.baseURL)")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            .navigationTitle("Home")
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button {
                        showSettings = true
                    } label: {
                        Image(systemName: "gearshape.fill")
                    }
                }
            }
            .sheet(isPresented: $showSettings) {
                SettingsView(config: config)
            }
            .navigationDestination(for: String.self) { user in
                SessionsView(user: user, config: config, path: $path)
            }
            .navigationDestination(for: SessionPath.self) { sessionPath in
                SessionDetailView(sessionPath: sessionPath, config: config, path: $path)
            }
        }
    }
}

// MARK: - Settings View
struct SettingsView: View {
    @ObservedObject var config: ServerConfig
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section(header: Text("Server Connection")) {
                    HStack {
                        Text("IP Address")
                        TextField("e.g. 192.168.1.5", text: $config.ip)
                            .multilineTextAlignment(.trailing)
                            .keyboardType(.numbersAndPunctuation)
                    }
                    HStack {
                        Text("Port")
                        TextField("e.g. 5001", text: $config.port)
                            .multilineTextAlignment(.trailing)
                            .keyboardType(.numberPad)
                    }
                }
                
                Section(footer: Text("The app will attempt to connect to \(config.baseURL)")) {
                    Button("Done") {
                        dismiss()
                    }
                    .frame(maxWidth: .infinity)
                    .alignmentGuide(.leading) { _ in 0 }
                }
            }
            .navigationTitle("Advanced Settings")
        }
    }
}

// MARK: - Sessions List View
struct SessionsView: View {
    let user: String
    @ObservedObject var config: ServerConfig
    @Binding var path: NavigationPath
    
    @State private var sessions: [Session] = []
    @State private var isLoading = true
    @State private var newSubjectName = ""

    var body: some View {
        VStack {
            HStack {
                TextField("New Subject Name", text: $newSubjectName)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                Button("Add") {
                    if !newSubjectName.isEmpty {
                        path.append(SessionPath(user: user, subject: newSubjectName))
                        newSubjectName = ""
                    }
                }
                .disabled(newSubjectName.isEmpty)
            }
            .padding()

            if isLoading {
                Spacer()
                ProgressView("Loading Sessions...")
                Spacer()
            } else {
                List {
                    Section("Current Sessions") {
                        ForEach(sessions.filter { $0.status != "completed" }) { session in
                            SessionRow(session: session, user: user, path: $path)
                        }
                    }
                    Section("Past Sessions") {
                        ForEach(sessions.filter { $0.status == "completed" }) { session in
                            SessionRow(session: session, user: user, path: $path)
                        }
                    }
                }
                .refreshable { fetchSessions() }
            }
        }
        .navigationTitle("Sessions: \(user)")
        .onAppear { fetchSessions() }
    }

    func fetchSessions() {
        guard let url = URL(string: "\(config.baseURL)/sessions/\(user)") else { return }
        URLSession.shared.dataTask(with: url) { data, _, _ in
            if let data = data {
                if let fetched = try? JSONDecoder().decode([Session].self, from: data) {
                    DispatchQueue.main.async {
                        self.sessions = fetched
                        self.isLoading = false
                    }
                }
            }
        }.resume()
    }
}

// MARK: - Session Row
struct SessionRow: View {
    let session: Session
    let user: String
    @Binding var path: NavigationPath

    var body: some View {
        HStack {
            VStack(alignment: .leading) {
                Text(session.name).font(.headline)
                if let score = session.score {
                    Text("Score: \(score)").font(.subheadline).foregroundColor(.secondary)
                }
            }
            Spacer()
            Circle()
                .fill(statusColor)
                .frame(width: 12, height: 12)
        }
        .contentShape(Rectangle())
        .onTapGesture {
            path.append(SessionPath(user: user, subject: session.name))
        }
    }

    var statusColor: Color {
        switch session.status {
        case "completed": return .green
        case "in_progress": return .yellow
        default: return .gray
        }
    }
}

// MARK: - Detail & Upload View
struct SessionDetailView: View {
    let sessionPath: SessionPath
    @ObservedObject var config: ServerConfig
    @Binding var path: NavigationPath
    
    @State private var page1Item: PhotosPickerItem?
    @State private var page2Item: PhotosPickerItem?
    @State private var page1Image: UIImage?
    @State private var page2Image: UIImage?
    
    @State private var score: Int?
    @State private var scoredImageURLs: [String] = []
    @State private var isUploading = false
    @State private var isCheckingServer = true
    @State private var errorMessage: String?

    var body: some View {
        Form {
            Section("Session Info") {
                Text("Subject: \(sessionPath.subject)")
                Text("User: \(sessionPath.user)")
            }
            
            if isCheckingServer {
                ProgressView("Checking for previous results...")
            } else {
                Section("Upload New Photos") {
                    PhotosPicker(selection: $page1Item, matching: .images) {
                        Label(page1Image == nil ? "Select Page 1" : "Page 1 Ready", systemImage: "photo.on.rectangle")
                    }
                    PhotosPicker(selection: $page2Item, matching: .images) {
                        Label(page2Image == nil ? "Select Page 2" : "Page 2 Ready", systemImage: "photo.on.rectangle")
                    }
                    
                    Button(action: uploadImages) {
                        if isUploading {
                            ProgressView()
                        } else {
                            Text("Rerun Analysis").bold()
                        }
                    }
                    .disabled(page1Image == nil || page2Image == nil || isUploading)
                }
            }
            
            if let finalScore = score {
                Section("Stored Results") {
                    HStack {
                        Text("Final Score:")
                        Spacer()
                        Text("\(finalScore)").font(.title2).bold().foregroundColor(.green)
                    }
                    NavigationLink("View Detailed Scored Pages") {
                        ResultsView(score: finalScore, imageURLs: scoredImageURLs, serverURL: config.baseURL)
                    }
                }
            }
            
            if let error = errorMessage {
                Text(error).foregroundColor(.red).font(.caption)
            }
        }
        .navigationTitle("Session Detail")
        .task(id: sessionPath) {
            resetState()
            fetchExistingMetadata()
        }
        .onChange(of: page1Item) { _ in loadImg(from: page1Item, target: 1) }
        .onChange(of: page2Item) { _ in loadImg(from: page2Item, target: 2) }
    }

    private func resetState() {
        score = nil
        scoredImageURLs = []
        page1Image = nil
        page2Image = nil
        isCheckingServer = true
    }

    func fetchExistingMetadata() {
        guard let url = URL(string: "\(config.baseURL)/sessions/\(sessionPath.user)") else { return }
        URLSession.shared.dataTask(with: url) { data, _, _ in
            DispatchQueue.main.async {
                self.isCheckingServer = false
                if let data = data, let sessions = try? JSONDecoder().decode([Session].self, from: data) {
                    if let current = sessions.first(where: { $0.name == sessionPath.subject && $0.status == "completed" }) {
                        self.score = current.score
                        self.scoredImageURLs = [
                            "/static/data/user-\(sessionPath.user)/\(sessionPath.subject)/debug_cells/colored_page_1.png",
                            "/static/data/user-\(sessionPath.user)/\(sessionPath.subject)/debug_cells/colored_page_2.png"
                        ]
                    }
                }
            }
        }.resume()
    }

    func loadImg(from item: PhotosPickerItem?, target: Int) {
        Task {
            if let data = try? await item?.loadTransferable(type: Data.self), let uiImage = UIImage(data: data) {
                await MainActor.run { if target == 1 { page1Image = uiImage } else { page2Image = uiImage } }
            }
        }
    }

    func uploadImages() {
        guard let img1 = page1Image, let img2 = page2Image else { return }
        isUploading = true
        errorMessage = nil
        
        let boundary = "Boundary-\(UUID().uuidString)"
        guard let url = URL(string: "\(config.baseURL)/score") else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()
        let fields = ["username": sessionPath.user, "subject": sessionPath.subject]
        for (key, value) in fields {
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"\(key)\"\r\n\r\n".data(using: .utf8)!)
            body.append("\(value)\r\n".data(using: .utf8)!)
        }
        body.append(createImageData(image: img1, fieldName: "page1", fileName: "p1.png", boundary: boundary))
        body.append(createImageData(image: img2, fieldName: "page2", fileName: "p2.png", boundary: boundary))
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)

        URLSession.shared.uploadTask(with: request, from: body) { data, _, error in
            DispatchQueue.main.async {
                if let data = data, let result = try? JSONDecoder().decode(ScoreResponse.self, from: data) {
                    self.pollStatus(for: result.job_id)
                } else {
                    self.isUploading = false
                    self.errorMessage = "Upload failed."
                }
            }
        }.resume()
    }

    func pollStatus(for jobId: String) {
        Timer.scheduledTimer(withTimeInterval: 3.0, repeats: true) { timer in
            guard let url = URL(string: "\(config.baseURL)/status/\(jobId)") else { return }
            URLSession.shared.dataTask(with: url) { data, _, _ in
                if let data = data, let statusRes = try? JSONDecoder().decode(StatusResponse.self, from: data) {
                    DispatchQueue.main.async {
                        if statusRes.status == "completed" {
                            timer.invalidate()
                            self.fetchResults(for: jobId)
                        } else if statusRes.status == "failed" {
                            timer.invalidate()
                            self.isUploading = false
                        }
                    }
                }
            }.resume()
        }
    }

    func fetchResults(for jobId: String) {
        guard let url = URL(string: "\(config.baseURL)/results/\(jobId)") else { return }
        URLSession.shared.dataTask(with: url) { data, _, _ in
            DispatchQueue.main.async {
                self.isUploading = false
                if let data = data, let res = try? JSONDecoder().decode(ResultsResponse.self, from: data) {
                    self.score = res.score
                    self.scoredImageURLs = res.image_urls
                }
            }
        }.resume()
    }

    func createImageData(image: UIImage, fieldName: String, fileName: String, boundary: String) -> Data {
        var data = Data()
        data.append("--\(boundary)\r\n".data(using: .utf8)!)
        data.append("Content-Disposition: form-data; name=\"\(fieldName)\"; filename=\"\(fileName)\"\r\n".data(using: .utf8)!)
        data.append("Content-Type: image/png\r\n\r\n".data(using: .utf8)!)
        if let pngData = image.pngData() { data.append(pngData) }
        data.append("\r\n".data(using: .utf8)!)
        return data
    }
}

// MARK: - Results View
struct ResultsView: View {
    let score: Int
    let imageURLs: [String]
    let serverURL: String

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                Text("Final Score: \(score)").font(.largeTitle).bold().padding(.top)
                ForEach(imageURLs, id: \.self) { urlString in
                    AsyncImage(url: URL(string: serverURL + urlString)) { image in
                        image.resizable().scaledToFit()
                    } placeholder: {
                        ProgressView()
                    }
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(10)
                    .padding(.horizontal)
                }
            }
        }
        .navigationTitle("Analysis Result")
    }
}

// MARK: - Models & Helpers
struct SessionPath: Hashable {
    let user: String
    let subject: String
}

struct Session: Codable, Identifiable {
    var id: String { name }
    let name: String
    let status: String
    let score: Int?
    let image_urls: [String]?
}

struct ScoreResponse: Codable { let job_id: String }
struct StatusResponse: Codable { let status: String }
struct ResultsResponse: Codable {
    let score: Int
    let image_urls: [String]
}
