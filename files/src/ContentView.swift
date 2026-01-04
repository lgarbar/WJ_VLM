import SwiftUI
import PhotosUI

// MARK: - Main Content View
struct ContentView: View {
    @State private var userID: String = ""
    @State private var path = NavigationPath()

    // Ensure this matches your Flask server's local IP
    let serverURL = "http://10.0.0.144:5001"

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
            }
            .navigationDestination(for: String.self) { user in
                SessionsView(user: user, serverURL: serverURL, path: $path)
            }
            .navigationDestination(for: SessionPath.self) { sessionPath in
                SessionDetailView(sessionPath: sessionPath, serverURL: serverURL, path: $path)
            }
        }
    }
}

// MARK: - Models
struct SessionPath: Hashable {
    let user: String
    let subject: String
}

struct Session: Codable, Identifiable {
    var id: String { name }
    let name: String
    let status: String
    let score: Int?
}

// MARK: - Sessions List View
struct SessionsView: View {
    let user: String
    let serverURL: String
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
        .toolbar {
            Button("Refresh") { fetchSessions() }
        }
        .onAppear { fetchSessions() }
    }

    func fetchSessions() {
        guard let url = URL(string: "\(serverURL)/sessions/\(user)") else { return }
        URLSession.shared.dataTask(with: url) { data, _, _ in
            if let data = data {
                if let fetched = try? JSONDecoder().decode([Session].self, from: data) {
                    DispatchQueue.main.async {
                        self.sessions = fetched
                        self.isLoading = false
                    }
                }
            }
        }
        .resume()
    }
}

struct SessionRow: View {
    let session: Session
    let user: String
    @Binding var path: NavigationPath

    var body: some View {
        HStack {
            VStack(alignment: .leading) {
                Text(session.name).font(.headline)
                if let score = session.score {
                    Text("Last Score: \(score)").font(.subheadline).foregroundColor(.secondary)
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
    let serverURL: String
    @Binding var path: NavigationPath
    
    @State private var page1Item: PhotosPickerItem?
    @State private var page2Item: PhotosPickerItem?
    @State private var page1Image: UIImage?
    @State private var page2Image: UIImage?
    
    @State private var score: Int?
    @State private var scoredImageURLs: [String] = []
    @State private var isUploading = false
    @State private var errorMessage: String?

    var body: some View {
        Form {
            Section("Session Info") {
                Text("Subject: \(sessionPath.subject)")
                Text("User: \(sessionPath.user)")
            }
            
            Section("Step 1: Select Assessment Pages") {
                PhotosPicker(selection: $page1Item, matching: .images) {
                    Label(page1Image == nil ? "Select Page 1" : "Page 1 Selected", systemImage: "doc.text.viewfinder")
                }
                if let image = page1Image {
                    Image(uiImage: image).resizable().scaledToFit().frame(height: 150).cornerRadius(8)
                }
                
                PhotosPicker(selection: $page2Item, matching: .images) {
                    Label(page2Image == nil ? "Select Page 2" : "Page 2 Selected", systemImage: "doc.text.viewfinder")
                }
                if let image = page2Image {
                    Image(uiImage: image).resizable().scaledToFit().frame(height: 150).cornerRadius(8)
                }
            }
            
            Section {
                Button(action: uploadImages) {
                    if isUploading {
                        HStack {
                            ProgressView().padding(.trailing, 5)
                            Text("Processing...")
                        }
                    } else {
                        Text("Analyze & Score").bold()
                    }
                }
                .frame(maxWidth: .infinity)
                .disabled(page1Image == nil || page2Image == nil || isUploading)
            }
            
            if let error = errorMessage {
                Section("Error") {
                    Text(error).foregroundColor(.red).font(.caption)
                }
            }
            
            if let finalScore = score {
                Section("Results") {
                    HStack {
                        Text("Final Score:")
                        Spacer()
                        Text("\(finalScore)").font(.title).bold().foregroundColor(.blue)
                    }
                    NavigationLink("View Scored Pages") {
                        ResultsView(score: finalScore, imageURLs: scoredImageURLs, serverURL: serverURL)
                    }
                }
            }
        }
        .navigationTitle("Session Detail")
        // This ensures that when you switch sessions, the old data is wiped
        .task(id: sessionPath) {
            resetState()
        }
        .onChange(of: page1Item) { _ in loadImg(from: page1Item, target: 1) }
        .onChange(of: page2Item) { _ in loadImg(from: page2Item, target: 2) }
    }

    private func resetState() {
        score = nil
        scoredImageURLs = []
        page1Image = nil
        page2Image = nil
        page1Item = nil
        page2Item = nil
        errorMessage = nil
    }

    func loadImg(from item: PhotosPickerItem?, target: Int) {
        Task {
            if let data = try? await item?.loadTransferable(type: Data.self),
               let uiImage = UIImage(data: data) {
                await MainActor.run {
                    if target == 1 { page1Image = uiImage } else { page2Image = uiImage }
                }
            }
        }
    }

    func uploadImages() {
        guard let img1 = page1Image, let img2 = page2Image else { return }
        isUploading = true
        errorMessage = nil
        
        let boundary = "Boundary-\(UUID().uuidString)"
        guard let url = URL(string: "\(serverURL)/score") else { return }
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
                if let error = error {
                    self.isUploading = false
                    self.errorMessage = error.localizedDescription
                    return
                }
                if let data = data, let result = try? JSONDecoder().decode(ScoreResponse.self, from: data) {
                    self.pollStatus(for: result.job_id)
                } else {
                    self.isUploading = false
                    self.errorMessage = "Server error or invalid response"
                }
            }
        }.resume()
    }

    func pollStatus(for jobId: String) {
        let statusURL = URL(string: "\(serverURL)/status/\(jobId)")!
        Timer.scheduledTimer(withTimeInterval: 3.0, repeats: true) { timer in
            URLSession.shared.dataTask(with: statusURL) { data, _, _ in
                if let data = data, let statusRes = try? JSONDecoder().decode(StatusResponse.self, from: data) {
                    DispatchQueue.main.async {
                        if statusRes.status == "completed" {
                            timer.invalidate()
                            self.fetchResults(for: jobId)
                        } else if statusRes.status == "failed" {
                            timer.invalidate()
                            self.isUploading = false
                            self.errorMessage = "AI Scoring failed."
                        }
                    }
                }
            }.resume()
        }
    }

    func fetchResults(for jobId: String) {
        let resultsURL = URL(string: "\(serverURL)/results/\(jobId)")!
        URLSession.shared.dataTask(with: resultsURL) { data, _, _ in
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
                Text("Final Score: \(score)")
                    .font(.largeTitle).bold()
                
                ForEach(imageURLs, id: \.self) { urlString in
                    VStack(alignment: .leading) {
                        Text("Analysis").font(.caption).foregroundColor(.secondary)
                        AsyncImage(url: URL(string: serverURL + urlString)) { image in
                            image.resizable().scaledToFit()
                        } placeholder: {
                            ProgressView()
                        }
                        .cornerRadius(12)
                        .shadow(radius: 4)
                    }
                    .padding(.horizontal)
                }
            }
        }
        .navigationTitle("Detailed Results")
    }
}

// MARK: - Response Structs
struct ScoreResponse: Codable { let job_id: String }
struct StatusResponse: Codable { let status: String }
struct ResultsResponse: Codable {
    let score: Int
    let image_urls: [String]
}
