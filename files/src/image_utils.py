import os
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageOps, ImageDraw

def force_clean(image_path):
    """
    Strips metadata using SIPS and then runs perspective correction.
    """
    directory, filename = os.path.split(image_path)
    clean_path = os.path.join(directory, f"{os.path.splitext(filename)[0]}_clean.png")
    
    # Try using system SIPS (macOS) to fix orientation/format headers
    try:
        subprocess.run(["sips", "-s", "format", "png", image_path, "--out", clean_path], check=True, capture_output=True)
    except:
        # Fallback if sips fails or not on macOS
        return image_path

    return straighten_page(clean_path)

def straighten_page(image_path):
    """
    Detects the document paper (white rectangle) and warps it to a flat view.
    Includes EXIF transpose to prevent 'sideways' processing.
    """
    pil_img = ImageOps.exif_transpose(Image.open(image_path))
    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours: return image_path
    
    # Find largest contour (the paper)
    cnt = max(contours, key=cv2.contourArea)
    peri = cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
    
    if len(approx) == 4:
        pts = approx.reshape(4, 2).astype(np.float32)
        
        # Order points: TL, TR, BR, BL
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0], rect[2] = pts[np.argmin(s)], pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1], rect[3] = pts[np.argmin(diff)], pts[np.argmax(diff)]
        
        (tl, tr, br, bl) = rect
        w = int(max(np.linalg.norm(br-bl), np.linalg.norm(tr-tl)))
        h = int(max(np.linalg.norm(tr-br), np.linalg.norm(tl-bl)))
        
        dst = np.array([[0,0], [w-1, 0], [w-1, h-1], [0, h-1]], dtype="float32")
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(img, M, (w, h))
        
        out_path = image_path.replace('.png', '_straight.png')
        cv2.imwrite(out_path, warped)
        return out_path

    return image_path

def get_individual_cells(image_path, rows=16, cols=10):
    """
    Grids the image into 160 cells. 
    Assumes standard layout: 8 question pairs per page.
    """
    img = ImageOps.exif_transpose(Image.open(image_path))
    w, h = img.size
    ph = h // 8  # Pair height
    cw = w // cols
    
    cells = []
    for r in range(rows):
        pair_idx = r // 2
        pair_top = pair_idx * ph
        qh = int(ph * 0.6) # Question occupies top 60%
        
        if r % 2 == 0:
            top, bottom = pair_top, pair_top + qh
        else:
            top, bottom = pair_top + qh, pair_top + ph
            
        for c in range(cols):
            left = c * cw
            right = (c + 1) * cw
            
            # Answer row buffer logic
            v_shift = int((bottom-top)*0.05) if r % 2 != 0 else 0
            
            # Crop with 30px safety buffer
            cell = img.crop((max(0, left-30), max(0, top+v_shift-30), 
                             min(w, right+30), min(h, bottom+v_shift+30)))
            cells.append(cell)
    return cells

def visualize_content_box(image_path, output_path):
    """
    Draws the grid lines on the image for debugging alignment.
    """
    img = ImageOps.exif_transpose(Image.open(image_path))
    draw = ImageDraw.Draw(img)
    w, h = img.size
    ph = h // 8
    for i in range(8):
        y = i * ph
        # Draw Pair Divider
        draw.line([(0, y), (w, y)], fill="blue", width=3)
        # Draw Question/Answer Split
        split_y = y + int(ph * 0.6)
        draw.line([(0, split_y), (w, split_y)], fill="blue", width=3)
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path)