import os
import tempfile
import uuid
import threading
import time
from flask import Flask, request, jsonify, send_from_directory
from mlx_vlm import load, generate
from image_utils import force_clean, get_individual_cells, visualize_content_box
from config import score_results

# Define fixed margins for straightened pages
PAGE_CONFIGS = {
    0: {"top": 0.00, "bottom": 1, "left": 0.00, "right": 1}, # Page 1
    1: {"top": 0.00, "bottom": 1, "left": 0.00, "right": 1}  # Page 2
}

# Load models once at startup
print("Loading MLX VLM models...")
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
print("Models loaded successfully.")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/data'

# In-memory job storage (for simplicity; in production, use database)
jobs = {}

def process_job(job_id, p1_path, p2_path, dirname, user, subject):
    try:
        jobs[job_id]['status'] = 'processing'
        score, image_urls = run_pipeline(p1_path, p2_path, dirname, models, processors, user, subject)
        jobs[job_id]['status'] = 'completed'
        jobs[job_id]['score'] = score
        jobs[job_id]['image_urls'] = image_urls
    except Exception as e:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = str(e)

@app.route('/score', methods=['POST'])
def score_endpoint():
    if 'page1' not in request.files or 'page2' not in request.files:
        return jsonify({'error': 'Missing page1 or page2 files'}), 400

    # Get user and subject info
    user = request.form.get('username', 'default_user')
    subject = request.form.get('subject', 'default_test')

    # Create directory structure: static/data/user-{user}/{subject}
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], f"user-{user}", subject)
    os.makedirs(save_path, exist_ok=True)

    page1_file = request.files['page1']
    page2_file = request.files['page2']

    p1_path = os.path.join(save_path, 'page1.png')
    p2_path = os.path.join(save_path, 'page2.png')

    page1_file.save(p1_path)
    page2_file.save(p2_path)

    # Create job
    job_id = str(uuid.uuid4())
    jobs[job_id] = {'status': 'queued', 'user': user, 'subject': subject}

    # Start processing in background
    thread = threading.Thread(target=process_job, args=(job_id, p1_path, p2_path, save_path, user, subject))
    thread.start()

    return jsonify({'job_id': job_id})

def run_pipeline(p1_path, p2_path, dirname, models, processors, user, subject):
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

    # 4. Create colored visualization
    image_urls = create_colored_visualization(report, p1_path, p2_path, dirname, user, subject)

    return raw_score, image_urls

def create_colored_visualization(report, p1_path, p2_path, dirname, user, subject):
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
    
    # Return URLs for the images
    image_urls = [
        f"/static/data/user-{user}/{subject}/debug_cells/colored_page_1.png",
        f"/static/data/user-{user}/{subject}/debug_cells/colored_page_2.png"
    ]
    return image_urls

@app.route('/status/<job_id>')
def get_status(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify({'status': jobs[job_id]['status']})

@app.route('/results/<job_id>')
def get_results(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    job = jobs[job_id]
    if job['status'] != 'completed':
        return jsonify({'error': 'Job not completed'}), 400
    return jsonify({'score': job['score'], 'image_urls': job['image_urls']})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001, debug=True)