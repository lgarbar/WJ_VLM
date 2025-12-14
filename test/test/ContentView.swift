//
//  CameraView.swift
//  test
//
//  Created by Daniel Garcia-Barnett on 12/14/25.
//
import SwiftUI

struct ContentView: View {
    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                NavigationLink("Math") {
                    CameraScreen(title: "Math")
                }

                NavigationLink("Sentence Writing") {
                    CameraScreen(title: "Sentence Writing")
                }
            }
            .padding()
        }
    }
}

struct CameraScreen: View {
    let title: String

    var body: some View {
        CameraView()
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
    }
}
