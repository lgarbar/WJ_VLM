# WJ-VLM: Woodcock-Johnson Math Scoring App

WJ-VLM is a full-stack solution designed to automate the scoring of Woodcock-Johnson (WJ) Mathematics subtests. It uses a SwiftUI mobile interface for document capture and a Python-based backend leveraging Computer Vision and Vision-Language Models (VLM) via Apple's MLX framework to transcribe handwritten scores.

## 📱 App Features

- **Multi-User Support**: Access specific data sessions by entering a unique User ID.
- **Dynamic Session Management**:
    - **Current Sessions**: Tracks active analysis jobs and newly created subjects.
    - **Previous Sessions**: Review historical scores and visual feedback for completed tests.
    - **Management**: Swipe to **Rename** or **Delete** subjects directly from the list.
- **Advanced Connectivity**: Dedicated Settings menu to configure Server IP and Port with persistent storage.
- **Analysis Workflow**:
    - Dual-page selection using the iOS Photos Picker.
    - Real-time status polling (Processing -> Completed).
    - Detailed results view showing the calculated score out of 160.
    - **Visual Feedback**: View "Scored Pages" where the AI overlays detection boxes on your original images to verify accuracy.

## 🛠 Tech Stack

### Frontend (iOS)
- **SwiftUI**: Modern declarative UI.
- **NavigationStack**: Advanced routing for deep-linking session paths.
- **Combine**: Used for real-time server polling and status updates.
- **PhotosUI**: Seamless integration with the system photo library.

### Backend (Python)
- **Flask**: Lightweight web server handling API requests.
- **MLX-VLM**: Local inference on Apple Silicon using models like `Qwen2-VL`.
- **OpenCV**: Image preprocessing and document alignment.

## 🚀 API Endpoints

The app communicates with the server via the following primary routes:

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/sessions/<user>` | GET | Fetches all subjects and status for a specific user. |
| `/score` | POST | Uploads images (Multipart) to start a background job. |
| `/status/<job_id>` | GET | Polls the current state of a scoring task. |
| `/results/<job_id>` | GET | Retrieves the final score and image paths. |
| `/session/rename` | POST | Renames a subject folder on the server. |
| `/session/delete` | POST | Deletes a subject and its associated data. |

## 📦 Installation & Setup

1. **Server**:
   - Ensure your Python backend is running on your Mac.
   - Note your local IP address (e.g., `192.168.x.x`).

2. **iOS App**:
   - Open the project in Xcode.
   - Run the app on a physical device or simulator.
   - Tap the **Gear Icon** on the home screen.
   - Enter your Mac's IP address and Port (`5001` by default).

3. **Usage**:
   - Enter your User ID (e.g., `DGB`).
   - Create a new Subject Name.
   - Select the two pages of the math test.
   - Tap **Run Analysis** and wait for the status to turn green.

## 📋 Note on Terminology
- **User**: The examiner or administrator (e.g., `DGB`).
- **Subject**: The specific student or test session being scored.
- **Job**: A single instance of the AI analyzing uploaded images.