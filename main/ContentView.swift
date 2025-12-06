import SwiftUI

enum AssessmentType: Equatable {
    case math
    case sentence
}

struct ContentView: View {
    @State private var selection: AssessmentType? = nil
    @State private var showCamera = false

    var body: some View {
        NavigationView {
            VStack(spacing: 28) {
                Spacer()
                Text("WJ Scoring")
                    .font(.largeTitle)
                    .bold()

                Button(action: {
                    selection = .math
                    showCamera = true
                }) {
                    HStack {
                        Spacer()
                        Text("Score Math")
                            .font(.title2)
                            .foregroundColor(.white)
                        Spacer()
                    }
                    .padding()
                    .background(Color.blue)
                    .cornerRadius(10)
                }
                .padding(.horizontal, 40)

                Button(action: {
                    selection = .sentence
                    showCamera = true
                }) {
                    HStack {
                        Spacer()
                        Text("Score Sentence Writing")
                            .font(.title2)
                            .foregroundColor(.white)
                        Spacer()
                    }
                    .padding()
                    .background(Color.green)
                    .cornerRadius(10)
                }
                .padding(.horizontal, 24)

                Spacer()

                Text("Select an assessment to begin scanning")
                    .font(.footnote)
                    .foregroundColor(.secondary)
                Spacer()
            }
            .navigationBarHidden(true)
            .sheet(isPresented: $showCamera) {
                if let sel = selection {
                    CameraView(assessment: sel)
                } else {
                    EmptyView()
                }
            }
        }
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
