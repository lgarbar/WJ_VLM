# WJ Scoring (iOS)

This small SwiftUI app shows a simple home screen to choose between scoring Math or Sentence Writing and opens a camera preview. It is intended as the UI scaffold; model integration with `ml-fastvlm` will be a next step.

Files added:

- `ScoringApp.swift` — app entry point
- `ContentView.swift` — home screen with two buttons
- `CameraView.swift` — camera preview + scanned pages counter overlay
- `Info.plist` — contains `NSCameraUsageDescription`

To run: open an Xcode project or create one that includes the files in this folder, then build & run on a physical device (camera not available in Simulator).
