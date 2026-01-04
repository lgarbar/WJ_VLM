import os
import uuid
import threading
import time
import json
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

# In-memory job storage
jobs = {}

@app.route('/sessions/<user>', methods=['GET'])
def get_sessions(user):
    user_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"user-{user}")
    if not os.path.exists(user_dir):
        return jsonify([])

    sessions_list = []
    # Scan the user's directory for subject folders
    for subject in os.listdir(user_dir):
        subject_path = os.path.join(user_dir, subject)
        if os.path.isdir(subject_path):
            meta_path = os.path.join(subject_path, 'metadata.json')
            status = "not_started"
            score = None
            
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r') as f:
                        meta = json.load(f)
                        status = meta.get('status', 'not_started')
                        score = meta.get('score')
                except Exception as e:
                    print(f"Error reading metadata for {subject}: {e}")
            
            sessions_list.append({
                "name": subject,
                "status": status,
                "score": score
            })
    
    return jsonify(sessions_list)

def process_job(job_id, p1_path, p2_path, dirname, user, subject):
    meta_path = os.path.join(dirname, 'metadata.json')
    try:
        jobs[job_id]['status'] = 'processing'
        # Update metadata to in_progress
        with open(meta_path, 'w') as f:
            json.dump({"status": "in_progress", "user": user, "subject": subject}, f)

        # Pipeline expects models and processors (using globals)
        score, image_urls = run_pipeline(p1_path, p2_path, dirname, models, processors, user, subject)
        
        jobs[job_id].update({'status': 'completed', 'score': score, 'image_urls': image_urls})
        
        # Save final metadata to disk for persistence
        with open(meta_path, 'w') as f:
            json.dump({
                "status": "completed",
                "score": score,
                "image_urls": image_urls,
                "timestamp": time.time()
            }, f)
        print(f"Job {job_id} completed successfully.")

    except Exception as e:
        print(f"Job {job_id} failed: {e}")
        jobs[job_id]['status'] = 'failed'
        with open(meta_path, 'w') as f:
            json.dump({"status": "failed", "error": str(e)}, f)

@app.route('/score', methods=['POST'])
def score_endpoint():
    if 'page1' not in request.files or 'page2' not in request.files:
        return jsonify({'error': 'Missing page1 or page2 files'}), 400

    user = request.form.get('username', 'default_user')
    subject = request.form.get('subject', 'default_test')

    save_path = os.path.join(app.config['UPLOAD_FOLDER'], f"user-{user}", subject)
    os.makedirs(save_path, exist_ok=True)

    p1_path = os.path.join(save_path, 'page1.png')
    p2_path = os.path.join(save_path, 'page2.png')

    request.files['page1'].save(p1_path)
    request.files['page2'].save(p2_path)

    job_id = str(uuid.uuid4())
    jobs[job_id] = {'status': 'queued', 'user': user, 'subject': subject}

    # FIX: Arguments now match process_job(job_id, p1_path, p2_path, dirname, user, subject)
    thread = threading.Thread(target=process_job, args=(job_id, p1_path, p2_path, save_path, user, subject))
    thread.start()

    return jsonify({'job_id': job_id})

def run_pipeline(p1_path, p2_path, dirname, models, processors, user, subject):
    all_scanned_answers = []
    pages = [p1_path, p2_path]

    for p_idx, p_path in enumerate(pages):
        cfg = PAGE_CONFIGS[p_idx]
        clean_path = force_clean(p_path)
        
        os.makedirs(os.path.join(dirname, "debug_cells"), exist_ok=True)
        
        visualize_content_box(clean_path, output_path=os.path.join(dirname, f"debug_cells/page_{p_idx+1}_viz.png"),
                              top_margin=cfg['top'], bottom_margin=cfg['bottom'],
                              left_margin=cfg['left'], right_margin=cfg['right'])
        
        cells = get_individual_cells(clean_path, dirname,
                                    rows=16, cols=10,
                                    top_margin=cfg['top'], 
                                    bottom_margin=cfg['bottom'],
                                    left_margin=cfg['left'],
                                    right_margin=cfg['right'])
        
        print(f"Scanning {len(cells)} cells for Page {p_idx + 1}...")
        for c_idx, cell_img in enumerate(cells):
            row = c_idx // 10
            col = c_idx % 10
            if row % 2 == 0: continue # Skip prompt rows
            
            question_num = (p_idx * 80) + ((row // 2) * 10) + col + 1
            messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": "Extract number or EMPTY."}]}]
            
            responses = []
            for model, processor in zip(models, processors):
                prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
                response = generate(model, processor, prompt, [cell_img], max_tokens=20, temp=0.0)
                responses.append(response.text.strip().upper())
            
            ans1, ans2 = responses
            confidence = (ans1 == ans2)
            text_ans = ans1 if ans1 == ans2 or ans2 == "EMPTY" else (ans2 if ans1 == "EMPTY" else ans1)
            
            all_scanned_answers.append({"ans": text_ans, "conf": confidence})

    raw_score, report = score_results(all_scanned_answers)
    image_urls = create_colored_visualization(report, p1_path, p2_path, dirname, user, subject)
    return raw_score, image_urls

def create_colored_visualization(report, p1_path, p2_path, dirname, user, subject):
    from PIL import Image, ImageDraw
    pages = [p1_path, p2_path]
    for p_idx, p_path in enumerate(pages):
        img = Image.open(force_clean(p_path))
        vis_img = img.copy()
        draw = ImageDraw.Draw(vis_img, "RGBA")
        w, h = img.size
        
        pair_h = h // 8
        cell_w = w // 10
        
        for r in range(16):
            if r % 2 == 0: continue
            pair_i = r // 2
            top = (pair_i * pair_h) + int(pair_h * 0.6)
            bottom = (pair_i + 1) * pair_h
            
            for c in range(10):
                left, right = c * cell_w, (c + 1) * cell_w
                q_idx = (p_idx * 80) + (pair_i * 10) + c
                entry = report[q_idx]
                
                color = (0, 255, 0, 100) if entry["status"] == "✅" else (255, 0, 0, 100)
                if entry["detected"] == "EMPTY": color = (255, 255, 0, 100)
                
                draw.rectangle([(left, top), (right, bottom)], fill=color)
        
        vis_img.save(os.path.join(dirname, f"debug_cells/colored_page_{p_idx+1}.png"))
    
    return [f"/static/data/user-{user}/{subject}/debug_cells/colored_page_{i}.png" for i in [1, 2]]

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/status/<job_id>')
def get_status(job_id):
    if job_id not in jobs: return jsonify({'error': 'Not found'}), 404
    return jsonify({'status': jobs[job_id]['status']})

@app.route('/results/<job_id>')
def get_results(job_id):
    job = jobs.get(job_id)
    if not job or job['status'] != 'completed': return jsonify({'error': 'Not ready'}), 400
    return jsonify({'score': job['score'], 'image_urls': job['image_urls']})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001, debug=True)