import SwiftUI
import AVFoundation

struct CameraView: View {
    let assessment: AssessmentType
    @Environment(\.presentationMode) private var presentationMode

    private var totalPages: Int {
        switch assessment {
        case .math: return 2
        case .sentence: return 6
        }
    }

    @State private var scannedPages = 0

    var body: some View {
        ZStack(alignment: .top) {
            CameraPreviewView()
                .edgesIgnoringSafeArea(.all)

            HStack {
                Button(action: { presentationMode.wrappedValue.dismiss() }) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.title)
                        .foregroundColor(.white)
                        .padding(12)
                }
                Spacer()
            }
            .padding(.top, 44)

            VStack {
                Spacer()
                Text("Scanned \(scannedPages)/\(totalPages) pages")
                    .font(.headline)
                    .padding(.vertical, 8)
                    .padding(.horizontal, 14)
                    .background(Color.black.opacity(0.6))
                    .foregroundColor(.white)
                    .cornerRadius(10)
                    .padding(.bottom, 32)
            }
        }
        .onAppear {
            // For a future step: wire capture callback to increment scannedPages
            scannedPages = 0
        }
    }
}

struct CameraPreviewView: UIViewRepresentable {
    func makeUIView(context: Context) -> PreviewView {
        let view = PreviewView()
        CameraSession.shared.configurePreview(view)
        CameraSession.shared.start()
        return view
    }

    func updateUIView(_ uiView: PreviewView, context: Context) {}

    static func dismantleUIView(_ uiView: PreviewView, coordinator: ()) {
        CameraSession.shared.stop()
    }
}

class PreviewView: UIView {
    override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
    var previewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
}

final class CameraSession: NSObject {
    static let shared = CameraSession()
    private let session = AVCaptureSession()

    private override init() {
        super.init()
    }

    func configurePreview(_ view: PreviewView) {
        view.previewLayer.videoGravity = .resizeAspectFill
        view.previewLayer.session = session
        configureSessionIfNeeded()
    }

    private func configureSessionIfNeeded() {
        guard session.inputs.isEmpty else { return }

        session.beginConfiguration()
        session.sessionPreset = .high

        if let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) {
            do {
                let input = try AVCaptureDeviceInput(device: device)
                if session.canAddInput(input) {
                    session.addInput(input)
                }
            } catch {
                print("Camera input error: \(error)")
            }
        }

        session.commitConfiguration()
    }

    func start() {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            if !session.isRunning { session.startRunning() }
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { granted in
                if granted { self.start() }
            }
        default:
            break
        }
    }

    func stop() {
        if session.isRunning { session.stopRunning() }
    }
}
