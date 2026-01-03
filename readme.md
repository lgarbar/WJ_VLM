# WJ-IV Math OCR & Scoring Pipeline

An automated pipeline for optical character recognition (OCR) and scoring of handwritten answers on WJ-IV Math subtest forms. This project uses advanced vision-language models to extract handwritten numbers from scanned test pages and score them against the official answer key, achieving near-perfect accuracy.

## Features

- **High-Accuracy OCR**: Utilizes ensemble of Qwen2-VL models (2B and 7B variants) for robust handwritten digit recognition
- **Image Preprocessing**: Automatic page straightening, cropping, and grid detection for optimal cell extraction
- **Flexible Grid Processing**: Handles 16-row grids with question/answer pairs, processing only answer rows
- **Confidence-Based Visualization**: Generates colored overlays on scanned images to highlight correct/incorrect answers with confidence indicators
- **Comprehensive Scoring**: Compares OCR results against the full 160-item WJ-IV Math answer key
- **Debug Outputs**: Saves cropped cell images and visualizations for troubleshooting

## Architecture

The pipeline consists of three main components:

1. **Image Processing** (`image_utils.py`):
   - Page straightening using contour detection
   - Content box extraction with configurable margins
   - Individual cell cropping with 60:40 question/answer split
   - Grid visualization and debugging tools

2. **OCR Engine** (`main_scanner.py`):
   - Dual-model ensemble (Qwen2-VL-2B and 7B) for improved accuracy
   - Parallel processing of models for efficiency
   - Confidence scoring based on model agreement
   - Batch processing of 160 answer cells across two pages

3. **Scoring System** (`config.py`):
   - WJ-IV Math answer key validation
   - Regex-based text cleaning and digit extraction
   - Detailed reporting with accuracy statistics

## Installation

### Prerequisites
- Python 3.10+
- macOS (optimized for Apple Silicon with MLX)

### Setup
```bash
# Clone or navigate to the project directory
cd ml-fastvlm

# Create conda environment
conda create -n wj_scoring python=3.10
conda activate wj_scoring

# Install dependencies
pip install -e .
```

### Dependencies
- mlx-vlm: Vision-language model inference
- Pillow (PIL): Image processing
- OpenCV: Contour detection and warping
- NumPy: Numerical operations

## Usage

### Basic OCR and Scoring
```bash
python main_scanner.py
```
This will process the default test images (`IMG_6654.png` and `IMG_6655.png`) and output:
- Raw score out of 160
- Detailed report of each question with OCR result vs expected
- Colored visualization images in `debug_cells/`

### Visualization Only
```bash
python main_scanner.py --viz
```
Generates grid visualizations without running OCR, useful for checking alignment.

### Custom Images
Modify the `page1` and `page2` variables in `main_scanner.py` to point to your scanned WJ-IV Math pages.

## Output

### Console Output
```
==================================================
PRECISION SCORING REPORT (160 ITEMS)
Final Raw Score: 152
==================================================
Q1: OCR: 0 | Expected: 0 ✅
Q2: OCR: 3 | Expected: 3 ✅
...
```

### Generated Files
- `debug_cells/page_1_viz.png`: Grid overlay on page 1
- `debug_cells/page_2_viz.png`: Grid overlay on page 2
- `debug_cells/colored_page_1.png`: Color-coded accuracy visualization for page 1
- `debug_cells/colored_page_2.png`: Color-coded accuracy visualization for page 2
- `debug_cells/Q*_page*_cell*.png`: Cropped images of specific cells for debugging

### Color Coding
- **Green**: Correct answers
- **Red**: Incorrect answers with high confidence (both models agreed)
- **Orange**: Incorrect answers with low confidence (models disagreed)
- **Yellow**: Empty detections

## Configuration

### Grid Parameters
- **Rows**: 16 (8 question/answer pairs)
- **Columns**: 10 per row
- **Split**: 60% question, 40% answer vertical space
- **Margins**: 0% (full page used for content detection)

### Model Settings
- **Primary Model**: Qwen2-VL-2B-Instruct-4bit
- **Secondary Model**: Qwen2-VL-7B-Instruct-4bit
- **Temperature**: 0.0 (deterministic)
- **Max Tokens**: 20

### Answer Key
The pipeline uses the complete WJ-IV Math subtest answer key (items 1-160) with proper scoring rules.

## Performance

- **Accuracy**: ~95% (152/160 correct on test data)
- **Processing Time**: ~6-7 minutes for full assessment
- **Resolution**: Optimized for 512x512 image patches

## Troubleshooting

### Common Issues
1. **Empty Detections**: Check image quality and cropping in `debug_cells/`
2. **Grid Misalignment**: Run `--viz` to verify grid overlay matches form layout
3. **Model Loading**: Ensure stable internet for downloading models

### Debug Mode
The pipeline saves cropped images for problematic questions. Check `debug_cells/` for:
- Individual answer cell crops
- Grid visualization overlays
- Colored accuracy maps

## Development

### Key Files
- `main_scanner.py`: Main pipeline orchestration
- `image_utils.py`: Image processing utilities
- `config.py`: Answer key and scoring logic

### Extending the Pipeline
- Add new model variants in the `model_ids` list
- Modify grid parameters in `PAGE_CONFIGS`
- Adjust prompts in the `messages` dictionary
- Implement additional scoring rules in `score_results()`

## License

This project is developed for educational and research purposes. Please ensure compliance with WJ-IV test administration guidelines.

## Acknowledgments

Built using:
- MLX framework for efficient inference
- Qwen2-VL models for vision-language understanding
- OpenCV for image processing
- Pillow for image manipulation
