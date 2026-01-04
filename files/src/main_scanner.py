import os
import argparse
import re
from PIL import Image, ImageDraw
from image_utils import force_clean, get_individual_cells, visualize_content_box
from config import score_results
from mlx_vlm import load, generate

def run_local(p1, p2, out_dir, debug_file):
    print("--- Loading MLX Models (Offline Mode) ---")
    model_ids = ["mlx-community/Qwen2-VL-2B-Instruct-4bit", "mlx-community/Qwen2-VL-7B-Instruct-4bit"]
    models = []
    processors = []
    for m_id in model_ids:
        m, p = load(m_id)
        # Match server setting to prevent drift
        p.image_processor.max_pixels = 512 * 512
        models.append(m)
        processors.append(p)
    
    # Parse debug list if provided
    db_list = []
    if debug_file and os.path.exists(debug_file):
        with open(debug_file, "r") as f:
            db_list = [int(x) for x in re.findall(r'\d+', f.read())]
            
    os.makedirs(os.path.join(out_dir, "debug_cells"), exist_ok=True)
    all_ans = []

    print("--- Starting Processing ---")
    for p_idx, p_path in enumerate([p1, p2]):
        clean = force_clean(p_path)
        visualize_content_box(clean, os.path.join(out_dir, f"debug_cells/page_{p_idx+1}_viz.png"))
        cells = get_individual_cells(clean)
        
        for c_idx, cell in enumerate(cells):
            row, col = c_idx // 10, c_idx % 10
            
            if row % 2 == 0: continue
            
            q_num = (p_idx * 80) + ((row // 2) * 10) + col + 1
            
            if q_num in db_list:
                cell.save(os.path.join(out_dir, f"debug_cells/Q{q_num}_debug.png"))
                print(f"Saved Debug Crop: Q{q_num}")
                
            msgs = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": "Extract handwritten number or EMPTY."}]}]
            res = []
            for m, p in zip(models, processors):
                prompt = p.apply_chat_template(msgs, add_generation_prompt=True)
                r = generate(m, p, prompt, [cell], max_tokens=20, temp=0.0)
                res.append(r.text.strip().upper())
            
            ans = res[0] if res[0] == res[1] or res[1] == "EMPTY" else (res[1] if res[0] == "EMPTY" else res[0])
            all_ans.append({"ans": ans, "conf": (res[0] == res[1])})

    score, report = score_results(all_ans)
    
    # Generate Feedback Images
    for p_idx, p_path in enumerate([p1, p2]):
        img = Image.open(force_clean(p_path))
        draw = ImageDraw.Draw(img, "RGBA")
        ph, cw = img.height // 8, img.width // 10
        for i in range(80):
            q_idx = (p_idx * 80) + i
            r_in_p, c_in_p = i // 10, i % 10
            top = (r_in_p * ph) + int(ph * 0.6)
            bottom = (r_in_p + 1) * ph
            
            entry = report[q_idx]
            color = (0, 255, 0, 100) if entry["status"] == "✅" else (255, 0, 0, 100)
            if entry["detected"] == "EMPTY": color = (255, 255, 0, 100)
            
            draw.rectangle([(c_in_p * cw, top), ((c_in_p + 1) * cw, bottom)], fill=color)
        img.save(os.path.join(out_dir, f"debug_cells/colored_page_{p_idx+1}.png"))

    print(f"\n--- Results ---")
    print(f"Final Score: {score}/160")
    print(f"Visual feedback saved to: {os.path.join(out_dir, 'debug_cells')}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fpath1", required=True)
    parser.add_argument("--fpath2", required=True)
    parser.add_argument("--debug_file")
    args = parser.parse_args()
    
    run_local(args.fpath1, args.fpath2, os.path.dirname(args.fpath1), args.debug_file)