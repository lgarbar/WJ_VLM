import os
import uuid
import threading
import json
import shutil
import re
from flask import Flask, request, jsonify, send_from_directory
from mlx_vlm import load, generate
from image_utils import force_clean, get_individual_cells, visualize_content_box
from config import score_results
from PIL import Image, ImageDraw

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/data'
jobs = {}

print("--- Initializing Models (2B & 7B Ensemble) ---")
model_ids = ["mlx-community/Qwen2-VL-2B-Instruct-4bit", "mlx-community/Qwen2-VL-7B-Instruct-4bit"]
models = []
processors = []

# Load models once
for m_id in model_ids:
    m, p = load(m_id)
    p.image_processor.max_pixels = 512 * 512
    models.append(m)
    processors.append(p)

def get_debug_list():
    if os.path.exists("debug_list.txt"):
        with open("debug_list.txt", "r") as f:
            return [int(x) for x in re.findall(r'\d+', f.read())]
    return []

# --- NEW: Management Endpoints (Rename/Delete) ---

@app.route('/session/rename', methods=['POST'])
def rename_session():
    data = request.json
    user = data.get('username')
    old_name = data.get('old_name')
    new_name = data.get('new_name')
    
    user_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"user-{user}")
    old_path = os.path.join(user_dir, old_name)
    new_path = os.path.join(user_dir, new_name)
    
    if not os.path.exists(old_path):
        return jsonify({"error": "Session not found"}), 404
    if os.path.exists(new_path):
        return jsonify({"error": "Name already exists"}), 400
        
    os.rename(old_path, new_path)
    return jsonify({"success": True, "new_name": new_name})

@app.route('/session/delete', methods=['POST'])
def delete_session():
    data = request.json
    user = data.get('username')
    subject = data.get('subject')
    
    target_path = os.path.join(app.config['UPLOAD_FOLDER'], f"user-{user}", subject)
    
    if os.path.exists(target_path):
        shutil.rmtree(target_path) # Recursively delete folder
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404

@app.route('/sessions/<user>', methods=['GET'])
def get_sessions(user):
    user_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"user-{user}")
    if not os.path.exists(user_dir):
        return jsonify([])
    
    sessions_list = []
    for subject in os.listdir(user_dir):
        subject_path = os.path.join(user_dir, subject)
        if os.path.isdir(subject_path):
            # Ignore hidden files or non-folders
            if subject.startswith('.'): continue
            
            meta_path = os.path.join(subject_path, 'metadata.json')
            score = None
            status = "completed" # Default if no metadata exists (legacy folders)
            
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r') as f:
                        meta = json.load(f)
                        score = meta.get('score')
                        status = meta.get('status', 'completed')
                except:
                    pass
            
            sessions_list.append({
                "name": subject,
                "status": status,
                "score": score
            })
    return jsonify(sessions_list)

# --- Existing Pipeline Code (Unchanged Functionality) ---

def run_pipeline(p1_path, p2_path, dirname, user, subject):
    all_ans = []
    debug_targets = get_debug_list()
    os.makedirs(os.path.join(dirname, "debug_cells"), exist_ok=True)

    for p_idx, p_path in enumerate([p1_path, p2_path]):
        clean = force_clean(p_path)
        visualize_content_box(clean, os.path.join(dirname, f"debug_cells/page_{p_idx+1}_viz.png"))
        cells = get_individual_cells(clean)
        
        for c_idx, cell_img in enumerate(cells):
            row, col = c_idx // 10, c_idx % 10
            if row % 2 == 0: continue 
            q_num = (p_idx * 80) + ((row // 2) * 10) + col + 1
            
            if q_num in debug_targets:
                cell_img.save(os.path.join(dirname, f"debug_cells/Q{q_num}_debug.png"))

            msgs = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": "Extract handwritten number or EMPTY."}]}]
            res = []
            for m, p in zip(models, processors):
                prompt = p.apply_chat_template(msgs, add_generation_prompt=True)
                r = generate(m, p, prompt, [cell_img], max_tokens=20, temp=0.0)
                res.append(r.text.strip().upper())
            
            final_ans = res[0] if res[0] == res[1] or res[1] == "EMPTY" else (res[1] if res[0] == "EMPTY" else res[0])
            all_ans.append({"ans": final_ans, "conf": (res[0] == res[1])})

    score, report = score_results(all_ans)
    
    image_urls = []
    for p_idx, p_path in enumerate([p1_path, p2_path]):
        img = Image.open(force_clean(p_path))
        draw = ImageDraw.Draw(img, "RGBA")
        ph, cw = img.height // 8, img.width // 10
        for i in range(80):
            q_idx = (p_idx * 80) + i
            r_in_p, c_in_p = i // 10, i % 10
            top = (r_in_p * ph) + int(ph * 0.6)
            bottom = (r_in_p + 1) * ph
            
            status = report[q_idx]["status"]
            detected = report[q_idx]["detected"]
            color = (0, 255, 0, 100) if status == "✅" else (255, 0, 0, 100)
            if detected == "EMPTY": color = (255, 255, 0, 100)
            draw.rectangle([(c_in_p * cw, top), ((c_in_p + 1) * cw, bottom)], fill=color)
        
        out_name = f"colored_page_{p_idx+1}.png"
        img.save(os.path.join(dirname, f"debug_cells/{out_name}"))
        image_urls.append(f"/static/data/user-{user}/{subject}/debug_cells/{out_name}")
        
    return score, image_urls

@app.route('/score', methods=['POST'])
def score_endpoint():
    user = request.form.get('username', 'user')
    subj = request.form.get('subject', 'test')
    path = os.path.join(app.config['UPLOAD_FOLDER'], f"user-{user}", subj)
    os.makedirs(path, exist_ok=True)
    
    p1 = os.path.join(path, 'page1.png')
    p2 = os.path.join(path, 'page2.png')
    request.files['page1'].save(p1)
    request.files['page2'].save(p2)
    
    # IMMEDIATE STATUS UPDATE: PROCESSING
    meta_path = os.path.join(path, 'metadata.json')
    with open(meta_path, 'w') as f:
        json.dump({"status": "processing", "score": None, "timestamp": str(uuid.uuid4())}, f)

    jid = str(uuid.uuid4())
    jobs[jid] = {'status': 'processing'}
    
    def background_task(job_id, p1_f, p2_f, save_path, u_name, s_name):
        try:
            score, urls = run_pipeline(p1_f, p2_f, save_path, u_name, s_name)
            jobs[job_id].update({'status': 'completed', 'res': [score, urls]})
            with open(os.path.join(save_path, 'metadata.json'), 'w') as f:
                json.dump({"status": "completed", "score": score, "image_urls": urls}, f)
        except Exception as e:
            print(f"THREAD ERROR: {e}")
            jobs[job_id].update({'status': 'failed'})
            with open(os.path.join(save_path, 'metadata.json'), 'w') as f:
                json.dump({"status": "failed", "error": str(e)}, f)

    threading.Thread(target=background_task, args=(jid, p1, p2, path, user, subj)).start()
    return jsonify({'job_id': jid})

@app.route('/status/<jid>')
def get_status(jid): return jsonify({'status': jobs.get(jid, {}).get('status', 'not_found')})

@app.route('/results/<jid>')
def get_results(jid): 
    j = jobs.get(jid)
    if j and 'res' in j:
        return jsonify({'score': j['res'][0], 'image_urls': j['res'][1]})
    return jsonify({"error": "not ready"}), 400

@app.route('/static/<path:p>')
def static_proxy(p): return send_from_directory('static', p)

if __name__ == "__main__": app.run(host='0.0.0.0', port=5001, debug=False)