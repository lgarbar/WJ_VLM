import os
import argparse
import sys
from mlx_vlm import load, generate
from image_utils import force_clean, get_individual_cells, visualize_content_box
from config import score_results

# Define fixed margins for straightened pages
PAGE_CONFIGS = {
    0: {"top": 0.00, "bottom": 1, "left": 0.00, "right": 1}, # Page 1
    1: {"top": 0.00, "bottom": 1, "left": 0.00, "right": 1}  # Page 2
}

def run_precision_assessment(p1_path, p2_path):
    # 1. Load Models
    model_ids = [
        "mlx-community/Qwen2-VL-2B-Instruct-4bit",
        "mlx-community/Qwen2-VL-7B-Instruct-4bit"
    ]
    models = []
    processors = []
    for model_id in model_ids:
        print(f"Loading Model: {model_id}...")
        model, processor = load(model_id)
        processor.image_processor.max_pixels = 512 * 512
        models.append(model)
        processors.append(processor) 

    all_scanned_answers = []
    pages = [p1_path, p2_path]


    for p_idx, p_path in enumerate(pages):
        cfg = PAGE_CONFIGS[p_idx]
        clean_path = force_clean(p_path)
        
        visualize_content_box(clean_path, output_path=os.path.join(dirname, f"debug_cells/page_{p_idx+1}_viz.png"),
                              top_margin=cfg['top'], bottom_margin=cfg['bottom'],
                              left_margin=cfg['left'], right_margin=cfg['right'])
        
        # Get individual cells (16 rows x 10 cols, but only process even rows for answers)
        cells = get_individual_cells(clean_path, dirname,
                                    rows=16, cols=10,
                                    top_margin=cfg['top'], 
                                    bottom_margin=cfg['bottom'],
                                    left_margin=cfg['left'],
                                    right_margin=cfg['right'])
        
        # Save sample answer cells for debugging (first 10 answers)
        os.makedirs(os.path.join(dirname, "debug_cells"), exist_ok=True)
        answer_cells = [cells[i] for i in range(10, 20)]  # cells 10-19 are Q1-Q10
        for idx, cell in enumerate(answer_cells):
            cell.save(os.path.join(dirname, f"debug_cells/page_{p_idx+1}_answer_Q{idx+1}.png"))
        
        print(f"Scanning {len(cells)} cells for Page {p_idx + 1}...")
        for c_idx, cell_img in enumerate(cells):
            row = c_idx // 10
            col = c_idx % 10
            # Only process odd rows (0-based, which are 2,4,6,... 1-based for answers)
            if row % 2 == 0:
                continue
            
            # Calculate question number (1-indexed, only for answer rows)
            question_num = (p_idx * 80) + ((row // 2) * 10) + col + 1
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image"},
                        {"type": "text", "text": "Extract the handwritten number from this image. Output only the number or EMPTY."}
                    ]
                }
            ]
            
            # Get responses from both models
            responses = []
            for model, processor in zip(models, processors):
                prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
                response = generate(model, processor, prompt, [cell_img], max_tokens=20, temp=0.0)
                responses.append(response.text.strip().upper())
            
            # Combine responses
            ans1, ans2 = responses
            confidence = (ans1 == ans2)
            if ans1 == ans2:
                text_ans = ans1
            elif ans1 == "EMPTY":
                text_ans = ans2
            elif ans2 == "EMPTY":
                text_ans = ans1
            else:
                # Both different numbers, prefer the first or check if one matches expected, but since we don't know, use ans1
                text_ans = ans1
            
            # Debug: Save problematic cells
            if question_num in [1, 2, 3, 11, 12, 13, 21, 22, 24, 28, 31, 33, 34, 46, 50, 60, 61, 62, 64, 68, 76, 78, 91, 92, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 121, 134]:
                debug_path = os.path.join(dirname, f"debug_cells/Q{question_num}_page{p_idx+1}_cell{c_idx+1}.png")
                cell_img.save(debug_path)
            
            all_scanned_answers.append({"ans": text_ans, "conf": confidence})

    # 3. Final Scoring
    print("\n\nCalculating Final Score...")
    raw_score, report = score_results(all_scanned_answers)

    # 4. Display Report
    print("\n" + "="*50)
    print(f"PRECISION SCORING REPORT (160 ITEMS)")
    print(f"Final Raw Score: {raw_score}")
    print("="*50)
    
    for entry in report:
        ceiling = " [CEILING REACHED]" if entry['ceiling'] else ""
        print(f"Q{entry['question']}: OCR: {entry['detected']} | Expected: {entry['expected']} {entry['status']}{ceiling}")

    # 5. Create colored visualization
    create_colored_visualization(report, p1_path, p2_path)

def create_colored_visualization(report, p1_path, p2_path):
    from PIL import Image, ImageDraw
    from image_utils import force_clean
    
    pages = [p1_path, p2_path]
    for p_idx, p_path in enumerate(pages):
        clean_path = force_clean(p_path)
        img = Image.open(clean_path)
        vis_img = img.copy()
        draw = ImageDraw.Draw(vis_img, "RGBA")
        
        w, h = img.size
        content_top = int(h * 0.0)
        content_bottom = int(h * 1.0)
        content_left = int(w * 0.0)
        content_right = int(w * 1.0)
        
        grid_h = content_bottom - content_top
        grid_w = content_right - content_left
        pair_h = grid_h // 8
        cell_w = grid_w // 10
        
        for r in range(16):
            if r % 2 == 0:
                continue  # only answer rows
            pair_i = r // 2
            pair_top = content_top + pair_i * pair_h
            question_h = int(pair_h * 0.6)
            top = pair_top + question_h
            bottom = pair_top + pair_h
            
            for c in range(10):
                left = content_left + c * cell_w
                right = left + cell_w
                
                question_num = (p_idx * 80) + ((r // 2) * 10) + c + 1
                entry = report[question_num - 1]
                
                if entry["status"] == "✅":
                    color = (0, 255, 0, 128)  # green with alpha
                elif entry["detected"] == "EMPTY":
                    color = (255, 255, 0, 128)  # yellow
                elif entry["conf"]:
                    color = (255, 0, 0, 128)  # red
                else:
                    color = (255, 165, 0, 128)  # orange
                
                draw.rectangle([(left, top), (right, bottom)], fill=color)
        
        output_path = os.path.join(dirname, f"debug_cells/colored_page_{p_idx+1}.png")
        vis_img.save(output_path)
        print(f"Colored visualization saved to: {output_path}")

if __name__ == "__main__":
    # 1. Setup Argparse
    parser = argparse.ArgumentParser(description="WJ-IV Math Scoring Scanner")
    parser.add_argument("--viz", action="store_true", help="Generate grid visualizations and exit (no OCR)")
    parser.add_argument("--limit", type=int, default=None, help="Limit OCR to the first N cells (for quick testing)")
    parser.add_argument("--fpath1", type=str, help="fpath for Page 1")
    parser.add_argument("--fpath2", type=str, help="fpath for Page 2")

    args = parser.parse_args()

    # 2. Define your paths
    page1 = args.fpath1
    page2 = args.fpath2
    dirname = os.path.dirname(page1)
    
    # 3. Handle Logic based on flags
    if args.viz:
        print("\n[!] RUNNING IN VISUALIZATION MODE (Skipping OCR)")
        from image_utils import force_clean, visualize_content_box
        
        # We assume PAGE_CONFIGS is defined globally in main_scanner.py
        for i, p in enumerate([page1, page2]):
            cfg = PAGE_CONFIGS[i]
            print(f"  -> Processing Page {i+1} grid...")
            clean = force_clean(p)
            visualize_content_box(
                clean, 
                output_path=os.path.join(dirname, f"debug_cells/page_{i+1}_viz.png"),
                top_margin=cfg['top'], 
                bottom_margin=cfg['bottom'],
                left_margin=cfg['left'], 
                right_margin=cfg['right']
            )
        print("\nDone! Check the 'debug_cells/' folder for results.")
        sys.exit(0)

    # 4. Standard Run (passing the limit flag if you want to use it in run_precision_assessment)
    # You could modify run_precision_assessment to accept 'limit=args.limit'
    run_precision_assessment(page1, page2)