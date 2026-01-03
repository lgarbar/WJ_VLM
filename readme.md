# WJ-IV Calculation Scoring App (MLX-VLM)

This application automates the scoring of the **Woodcock-Johnson IV (WJ-IV) Calculation subtest** using a local Vision-Language Model (VLM). It processes handwritten math tests, extracts student answers using a precision-grid strategy, and applies standardized scoring rules.

## Core Features

* **Grid-Based OCR:** Slices high-resolution test pages into an 8x10 grid (80 cells per page) to force model focus on individual handwriting samples.
* **Content-Box Strategy:** Uses percentage-based margins to define the "active area" of a test page, preventing cumulative vertical drift across rows.
* **EXIF Correction:** Automatically handles smartphone photo rotation issues using `ImageOps.exif_transpose`.
* **Standardized Scoring:** Implements the WJ-IV "Ceiling Rule" (scoring stops after 6 consecutive incorrect responses).
* **Visual Debugging:** Generates "Content Box" visualizations and "Contact Sheets" so you can verify grid alignment before running the OCR.

## File Structure

### 1. `main_scanner.py`
The execution engine.
* Loads the `mlx-community/Qwen2-VL-2B-Instruct-4bit` model.
* Manages the page-by-page loop.
* Contains `PAGE_CONFIGS` to allow unique geometric calibration for different photo angles or page types.
* Orchestrates the prompting: *"Extract the handwritten number from this image. Output only the number or EMPTY."*

### 2. `image_utils.py`
The geometry and image processing toolkit.
* **`get_individual_cells`**: The primary slicer. It applies a vertical `shift` and `buffer_pixels` to ensure student handwriting (usually at the bottom of a math problem) is perfectly captured.
* **`visualize_content_box`**: Draws a blue grid over the original image to show exactly where the app is "looking."
* **`create_debug_contact_sheet`**: Merges all 80 cell crops into a single image for rapid human verification of alignment.
* **`force_clean`**: Uses system-level `sips` to ensure images are in a clean PNG format.

### 3. `config.py`
The scoring and domain logic.
* Contains the **160-item Answer Key** for the Calculation subtest.
* **`score_results`**: Uses Regex to clean OCR output (removing conversational filler) and handles common character confusions (e.g., 'O' vs '0', 'I' vs '1').

## Geometric Calibration

To ensure 100% accuracy, you must align the grid to your specific photos:

1.  Run the scanner and check `debug_cells/page_1_viz.png`.
2.  If the blue boxes are too high, increase the `top_margin` in `main_scanner.py`.
3.  If the boxes are too low, decrease the `top_margin`.
4.  Verify that `buffer_pixels` in `image_utils.py` are sufficient to capture two-digit numbers without clipping.

## Requirements

* Apple Silicon (M1/M2/M3) for `mlx` performance.
* `PIL` (Pillow) for image manipulation.
* `mlx-vlm` for model inference.
