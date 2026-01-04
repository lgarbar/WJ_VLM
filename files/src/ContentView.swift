import SwiftUI
import PhotosUI

struct ContentView: View {
    @State private var userID: String = ""
    @State private var path = NavigationPath()

    let serverURL = "http://10.0.0.144:5001"

    var body: some View {
        NavigationStack(path: $path) {
            VStack {
                Text("WJ Math Scorer")
                    .font(.largeTitle)
                    .padding()
                TextField("Enter User ID (e.g. DGB)", text: $userID)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .padding()
                Button("Enter") {
                    path.append(userID)
                }
                .disabled(userID.isEmpty)
                .buttonStyle(.borderedProminent)
            }
            .navigationDestination(for: String.self) { user in
                SessionsView(user: user, serverURL: serverURL, path: $path)
            }
            .navigationDestination(for: SessionPath.self) { sessionPath in
                SessionDetailView(user: sessionPath.user, subject: sessionPath.subject, serverURL: serverURL, path: $path)
            }
        }
    }
}

struct SessionPath: Hashable {
    let user: String
    let subject: String
}

struct SessionsView: View {
    let user: String
    let serverURL: String
    @Binding var path: NavigationPath
    @State private var sessions: [Session] = []
    @State private var isLoading = true
    @State private var newSubjectName = ""

    var body: some View {
        VStack {
            Text("Sessions for \(user)")
                .font(.title)
                .padding()
            
            HStack {
                TextField("New Subject Name", text: $newSubjectName)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                Button("Add") {
                    if !newSubjectName.isEmpty {
                        path.append(SessionPath(user: user, subject: newSubjectName))
                    }
                }
                .disabled(newSubjectName.isEmpty)
                Button("Refresh") {
                    fetchSessions()
                }
            }
            .padding()
            
            if isLoading {
                ProgressView()
            } else {
                List {
                    Section(header: Text("Current Sessions")) {
                        ForEach(sessions.filter { $0.status != "completed" }) { session in
                            SessionRow(session: session, user: user, path: $path)
                        }
                    }
                    Section(header: Text("Past Sessions")) {
                        ForEach(sessions.filter { $0.status == "completed" }) { session in
                            SessionRow(session: session, user: user, path: $path)
                        }
                    }
                }
            }
        }
        .onAppear {
            fetchSessions()
        }
        .navigationBarBackButtonHidden(false)
    }

    func fetchSessions() {
        guard let url = URL(string: "\(serverURL)/sessions/\(user)") else { return }
        URLSession.shared.dataTask(with: url) { data, _, _ in
            if let data = data {
                do {
                    let fetched = try JSONDecoder().decode([Session].self, from: data)
                    DispatchQueue.main.async {
                        self.sessions = fetched
                        self.isLoading = false
                    }
                } catch {
                    print("Error decoding: \(error)")
                }
            }
        }.resume()
    }
}

struct SessionRow: View {
    let session: Session
    let user: String
    @Binding var path: NavigationPath

    var body: some View {
        HStack {
            Text(session.name)
            Spacer()
            Circle()
                .fill(statusColor)
                .frame(width: 20, height: 20)
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
        default: return .red
        }
    }
}

struct SessionDetailView: View {
    let user: String
    let subject: String
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
            Section(header: Text("Subject: \(subject)")) {
                Text("User: \(user)")
            }
            
            Section(header: Text("Assessment Pages")) {
                PhotosPicker("Select Page 1", selection: $page1Item, matching: .images)
                if let image = page1Image {
                    Image(uiImage: image).resizable().scaledToFit().frame(height: 100)
                }
                
                PhotosPicker("Select Page 2", selection: $page2Item, matching: .images)
                if let image = page2Image {
                    Image(uiImage: image).resizable().scaledToFit().frame(height: 100)
                }
            }
            
            Button(action: uploadImages) {
                if isUploading {
                    ProgressView()
                } else {
                    Text("Analyze & Score")
                        .fontWeight(.bold)
                        .frame(maxWidth: .infinity)
                }
            }
            .disabled(page1Image == nil || page2Image == nil)
            
            if let error = errorMessage {
                Section(header: Text("Error")) {
                    Text(error).foregroundColor(.red)
                }
            }
            
            if let finalScore = score {
                Section(header: Text("Results")) {
                    Text("Final Score: \(finalScore)").font(.largeTitle).foregroundColor(.blue)
                    NavigationLink("View Detailed Results") {
                        ResultsView(score: finalScore, imageURLs: scoredImageURLs, serverURL: serverURL)
                    }
                }
            }
        }
        .navigationTitle("Session Detail")
        .onChange(of: page1Item) { _ in loadImg(from: page1Item, target: 1) }
        .onChange(of: page2Item) { _ in loadImg(from: page2Item, target: 2) }
    }

    func loadImg(from item: PhotosPickerItem?, target: Int) {
        Task {
            if let data = try? await item?.loadTransferable(type: Data.self), let uiImage = UIImage(data: data) {
                DispatchQueue.main.async {
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
        var request = URLRequest(url: URL(string: "\(serverURL)/score")!)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()
        let fields = ["username": user, "subject": subject]
        for (key, value) in fields {
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"\(key)\"\r\n\r\n".data(using: .utf8)!)
            body.append("\(value)\r\n".data(using: .utf8)!)
        }

        body.append(createImageData(image: img1, fieldName: "page1", fileName: "p1.png", boundary: boundary))
        body.append(createImageData(image: img2, fieldName: "page2", fileName: "p2.png", boundary: boundary))
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)

        URLSession.shared.uploadTask(with: request, from: body) { data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    self.isUploading = false
                    self.errorMessage = "Upload error: \(error.localizedDescription)"
                    return
                }
                if let data = data {
                    do {
                        let result = try JSONDecoder().decode(ScoreResponse.self, from: data)
                        self.pollStatus(for: result.job_id)
                    } catch {
                        self.isUploading = false
                        self.errorMessage = "Failed to parse upload response: \(error.localizedDescription)"
                    }
                } else {
                    self.isUploading = false
                    self.errorMessage = "No data received from server"
                }
            }
        }.resume()
    }

    func pollStatus(for jobId: String) {
        let statusURL = URL(string: "\(serverURL)/status/\(jobId)")!
        Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { timer in
            URLSession.shared.dataTask(with: statusURL) { data, _, error in
                if let data = data {
                    do {
                        let status = try JSONDecoder().decode(StatusResponse.self, from: data)
                        DispatchQueue.main.async {
                            if status.status == "completed" {
                                timer.invalidate()
                                self.fetchResults(for: jobId)
                            } else if status.status == "failed" {
                                timer.invalidate()
                                self.isUploading = false
                                self.errorMessage = "Processing failed"
                            }
                            // Continue polling for other statuses
                        }
                    } catch {
                        DispatchQueue.main.async {
                            timer.invalidate()
                            self.isUploading = false
                            self.errorMessage = "Failed to check status"
                        }
                    }
                } else {
                    DispatchQueue.main.async {
                        timer.invalidate()
                        self.isUploading = false
                        self.errorMessage = "Network error while checking status"
                    }
                }
            }.resume()
        }
    }

    func fetchResults(for jobId: String) {
        let resultsURL = URL(string: "\(serverURL)/results/\(jobId)")!
        URLSession.shared.dataTask(with: resultsURL) { data, _, error in
            DispatchQueue.main.async {
                self.isUploading = false
                if let data = data {
                    do {
                        let result = try JSONDecoder().decode(ResultsResponse.self, from: data)
                        self.score = result.score
                        self.scoredImageURLs = result.image_urls
                    } catch {
                        self.errorMessage = "Failed to parse results: \(error.localizedDescription)"
                    }
                } else {
                    self.errorMessage = "Failed to fetch results"
                }
            }
        }.resume()
    }

    func createImageData(image: UIImage, fieldName: String, fileName: String, boundary: String) -> Data {
        var data = Data()
        data.append("--\(boundary)\r\n".data(using: .utf8)!)
        data.append("Content-Disposition: form-data; name=\"\(fieldName)\"; filename=\"\(fileName)\"\r\n".data(using: .utf8)!)
        data.append("Content-Type: image/png\r\n\r\n".data(using: .utf8)!)
        if let pngData = image.pngData() {
            data.append(pngData)
        }
        data.append("\r\n".data(using: .utf8)!)
        return data
    }
}

struct ResultsView: View {
    let score: Int
    let imageURLs: [String]
    let serverURL: String

    var body: some View {
        ScrollView {
            VStack {
                Text("Final Score: \(score)")
                    .font(.largeTitle)
                    .padding()
                ForEach(imageURLs, id: \.self) { urlString in
                    AsyncImage(url: URL(string: serverURL + urlString)) { image in
                        image.resizable().scaledToFit()
                    } placeholder: {
                        ProgressView()
                    }
                    .padding()
                }
            }
        }
        .navigationTitle("Detailed Results")
    }
}

struct Session: Codable, Identifiable {
    let id = UUID()
    let name: String
    let status: String
}

struct ScoreResponse: Codable {
    let job_id: String
}

struct StatusResponse: Codable {
    let status: String
}

struct ResultsResponse: Codable {
    let score: Int
    let image_urls: [String]
}
