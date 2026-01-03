import os
import subprocess
from PIL import Image, ImageOps, ImageDraw, ImageFont
import cv2
import numpy as np

def force_clean(image_path):
    directory = os.path.dirname(image_path)
    filename = os.path.basename(image_path)
    name, _ = os.path.splitext(filename)
    clean_path = os.path.join(directory, f"{name}_clean.png")
    straight_path = os.path.join(directory, f"{name}_clean_straight.png")

    if not os.path.exists(straight_path):
        if not os.path.exists(clean_path):
            print(f"Force-cleaning {filename} with sips...")
            subprocess.run(["sips", "-s", "format", "png", image_path, "--out", clean_path], check=True, capture_output=True)
        # Straighten the cleaned image
        straight_path = straighten_page(clean_path)
    return straight_path

def get_individual_cells(image_path, rows=16, cols=10, buffer_pixels=3, 
                         top_margin=0.1, bottom_margin=0.9, 
                         left_margin=0.05, right_margin=0.95):
    """
    Extract individual cells from a WJ Math test page.
    
    Uses a Content-Box strategy: defines content_top and content_bottom
    (ignoring headers/footers) and divides that specific height by rows.
    This prevents vertical drift by calculating each cell position from
    the content boundaries using integer arithmetic.
    
    Args:
        image_path: Path to the image file
        rows: Number of rows in the grid (default: 8)
        cols: Number of columns in the grid (default: 10)
        buffer_pixels: Outward buffer to prevent clipping (default: 3)
        top_margin: Top margin as fraction of height (default: 0.11)
        bottom_margin: Bottom margin as fraction of height (default: 0.95)
        left_margin: Left margin as fraction of width (default: 0.04)
        right_margin: Right margin as fraction of width (default: 0.96)
    
    Returns:
        List of PIL Image objects, one per cell
    """
    # Apply EXIF orientation fix immediately
    raw_img = Image.open(image_path)
    img = ImageOps.exif_transpose(raw_img)
    w, h = img.size

    # Content-Box Strategy: Define the exact box where problems live
    # This ignores headers, footers, and margins
    content_top = int(h * top_margin)      # Start below the title
    content_bottom = int(h * bottom_margin) # End above the page number
    content_left = int(w * left_margin)     # Skip the left margin
    content_right = int(w * right_margin)   # Skip the right margin

    # Calculate grid dimensions
    grid_h = content_bottom - content_top
    grid_w = content_right - content_left
    
    # Use integer division to prevent cumulative drift
    # Calculate cell dimensions as integers
    pair_h = grid_h // 8  # Height per Q/A pair
    cell_w = grid_w // cols  # 10 columns
    
    cells = []
    os.makedirs("debug_crops", exist_ok=True)

    for r in range(rows):
        pair_i = r // 2
        pair_top = content_top + pair_i * pair_h
        
        if r % 2 == 0:  # Question row
            question_h = int(pair_h * 0.6)
            top = pair_top
            bottom = pair_top + question_h
        else:  # Answer row
            question_h = int(pair_h * 0.6)
            top = pair_top + question_h
            bottom = pair_top + pair_h
        
        for c in range(cols):
            # Calculate cell boundaries using integer arithmetic
            # Each cell position is calculated from content boundaries to prevent drift
            left = content_left + (c * cell_w)
            right = left + cell_w

            # Shift the crop down by 5% of the cell height to ensure 
            # the handwriting (at the bottom) is definitely included.
            shift = int((bottom - top) * 0.05)  # Small shift to focus on answers
            buffer_pixels = 30         # Buffer for context
            crop_top = max(0, int(top + shift - buffer_pixels))
            crop_bottom = min(h, int(bottom + shift + buffer_pixels))
            crop_left = max(0, int(left - buffer_pixels))
            crop_right = min(w, int(right + buffer_pixels))
            
            cell = img.crop((crop_left, crop_top, crop_right, crop_bottom))
            cells.append(cell)
            
            # Export EVERY row's first cell to check for vertical drift
            if c == 0:
                cell.save(f"debug_crops/R{r+1}_C1_check.png")
                
    return cells


def visualize_content_box(image_path, rows=16, cols=10, output_path="debug_cells/content_box_visualization.png",
                          top_margin=0.1, bottom_margin=0.9, left_margin=0.05, right_margin=0.95):
    """
    Visualize the content box and grid boundaries on the original image.
    This helps verify that the content box percentages are correct.
    
    Args:
        image_path: Path to the image file
        rows: Number of rows in the grid
        cols: Number of columns in the grid
        output_path: Path where the visualization will be saved
        top_margin: Top margin as fraction of height (default: 0.11)
        bottom_margin: Bottom margin as fraction of height (default: 0.95)
        left_margin: Left margin as fraction of width (default: 0.04)
        right_margin: Right margin as fraction of width (default: 0.96)
    """
    # Apply EXIF orientation fix
    raw_img = Image.open(image_path)
    img = ImageOps.exif_transpose(raw_img)
    w, h = img.size
    
    # Create a copy for drawing
    vis_img = img.copy()
    draw = ImageDraw.Draw(vis_img)
    
    # Calculate content box (same logic as get_individual_cells)
    content_top = int(h * top_margin)
    content_bottom = int(h * bottom_margin)
    content_left = int(w * left_margin)
    content_right = int(w * right_margin)
    
    grid_h = content_bottom - content_top
    grid_w = content_right - content_left
    pair_h = grid_h // 8
    cell_w = grid_w // cols
    
    # Draw content box outline
    draw.rectangle(
        [(content_left, content_top), (content_right, content_bottom)],
        outline="red",
        width=3
    )
    
    # Draw grid lines
    for pair_i in range(8):
        pair_top = content_top + pair_i * pair_h
        question_h = int(pair_h * 0.6)
        # Horizontal lines
        draw.line([(content_left, pair_top), (content_right, pair_top)], fill="blue", width=1)
        draw.line([(content_left, pair_top + question_h), (content_right, pair_top + question_h)], fill="blue", width=1)
        draw.line([(content_left, pair_top + pair_h), (content_right, pair_top + pair_h)], fill="blue", width=1)
    
    for c in range(cols + 1):
        x = content_left + (c * cell_w)
        draw.line([(x, content_top), (x, content_bottom)], fill="blue", width=1)
    
    # Label first few cells with question numbers
    try:
        # Try to use a default font, fallback to basic if not available
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
    except:
        font = ImageFont.load_default()
    
    for r in range(min(rows, 3)):  # Label first 3 rows
        pair_i = r // 2
        pair_top = content_top + pair_i * pair_h
        if r % 2 == 0:
            question_h = int(pair_h * 0.6)
            top = pair_top
        else:
            question_h = int(pair_h * 0.6)
            top = pair_top + question_h
        for c in range(min(cols, 5)):  # Label first 5 columns
            q_num = (r * cols) + c + 1
            x = content_left + (c * cell_w) + 5
            y = top + 5
            draw.text((x, y), f"Q{q_num}", fill="green", font=font)
    
    # Save visualization
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    vis_img.save(output_path)
    print(f"Content box visualization saved to: {output_path}")
    return vis_img


def create_debug_contact_sheet(cells, rows=8, cols=10, output_path="debug_cells/contact_sheet.png"):
    """
    Create a visual contact sheet showing all cells in a grid layout.
    This helps verify that every math problem is perfectly centered.
    
    Args:
        cells: List of PIL Image objects (should be 80 for 8x10 grid)
        rows: Number of rows in the grid
        cols: Number of columns in the grid
        output_path: Path where the contact sheet will be saved
    """
    if len(cells) != rows * cols:
        print(f"Warning: Expected {rows * cols} cells, got {len(cells)}")
    
    # Get dimensions of first cell (assuming all are similar size)
    cell_w, cell_h = cells[0].size if cells else (100, 100)
    
    # Create a new image for the contact sheet
    contact_w = cell_w * cols
    contact_h = cell_h * rows
    contact_sheet = Image.new('RGB', (contact_w, contact_h), color='white')
    
    # Paste each cell into the grid
    for idx, cell in enumerate(cells):
        if idx >= rows * cols:
            break
        r = idx // cols
        c = idx % cols
        x = c * cell_w
        y = r * cell_h
        contact_sheet.paste(cell, (x, y))
    
    # Save the contact sheet
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    contact_sheet.save(output_path)
    print(f"Debug contact sheet saved to: {output_path}")
    return contact_sheet


def straighten_page(image_path):
    """
    Detect the largest rectangular contour in the image and warp it to a straight rectangle.
    This helps correct for perspective distortion or paper curling.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Path to the straightened image
    """
    straightened_path = image_path.replace('.png', '_straight.png')
    if os.path.exists(straightened_path):
        return straightened_path
    
    img = cv2.imread(image_path)
    if img is None:
        return image_path
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image_path
    
    # Find largest contour
    largest = max(contours, key=cv2.contourArea)
    peri = cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, 0.02 * peri, True)
    
    if len(approx) != 4:
        return image_path
    
    # Order points: top-left, top-right, bottom-right, bottom-left
    pts = approx.reshape(4, 2).astype(np.float32)
    rect = np.zeros((4, 2), dtype=np.float32)
    
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # top-left
    rect[2] = pts[np.argmax(s)]  # bottom-right
    
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right
    rect[3] = pts[np.argmax(diff)]  # bottom-left
    
    # Calculate dimensions
    (tl, tr, br, bl) = rect
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    
    # Destination points
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]
    ], dtype=np.float32)
    
    # Warp
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(img, M, (maxWidth, maxHeight))
    
    cv2.imwrite(straightened_path, warped)
    print(f"Straightened image saved to: {straightened_path}")
    return straightened_path


def get_row_crops(image_path, rows=8, top_margin=0.11, bottom_margin=0.95, 
                  left_margin=0.04, right_margin=0.96):
    """
    Crop the image into individual rows, each containing 10 math problems.
    
    Args:
        image_path: Path to the image file
        rows: Number of rows in the grid (default: 8)
        top_margin: Top margin as fraction of height (default: 0.11)
        bottom_margin: Bottom margin as fraction of height (default: 0.95)
        left_margin: Left margin as fraction of width (default: 0.04)
        right_margin: Right margin as fraction of width (default: 0.96)
    
    Returns:
        List of PIL Image objects, one per row
    """
    # Apply EXIF orientation fix immediately
    raw_img = Image.open(image_path)
    img = ImageOps.exif_transpose(raw_img)
    w, h = img.size

    # Content-Box Strategy
    content_top = int(h * top_margin)
    content_bottom = int(h * bottom_margin)
    content_left = int(w * left_margin)
    content_right = int(w * right_margin)

    # Calculate row dimensions
    grid_h = content_bottom - content_top
    row_h = grid_h // rows
    
    rows_crops = []
    for r in range(rows):
        top = content_top + (r * row_h)
        bottom = top + row_h
        row_crop = img.crop((content_left, top, content_right, bottom))
        rows_crops.append(row_crop)
    
    return rows_crops
