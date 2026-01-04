import re

WJ_MATH_ANSWER_KEY = [
    0, 3, 4, 2, 3, 0, 0, 3, 1, 6, 5, 2, 7, 8, 5, 2, 5, 8, 3, 3,
    1, 6, 3, 0, 8, 0, 9, 1, 9, 5, 7, 7, 1, 6, 8, 9, 5, 10, 4, 5,
    4, 10, 12, 2, 12, 0, 8, 2, 0, 7, 10, 5, 4, 8, 3, 10, 4, 12, 14, 0,
    1, 9, 14, 6, 5, 2, 5, 0, 14, 5, 10, 4, 7, 17, 9, 1, 4, 6, 3, 12,
    0, 15, 10, 0, 8, 11, 12, 3, 15, 9, 9, 0, 40, 4, 7, 6, 27, 7, 18, 8,
    11, 63, 2, 16, 16, 28, 1, 12, 2, 0, 8, 21, 5, 24, 1, 30, 7, 13, 81, 16,
    0, 6, 45, 49, 3, 54, 11, 42, 2, 56, 15, 32, 3, 2, 2, 18, 36, 4, 35, 13,
    25, 6, 6, 0, 72, 1, 20, 48, 0, 4, 14, 11, 64, 4, 16, 18, 0, 1, 36, 10
]

def score_results(ocr_results):
    raw_score = 0
    detailed_report = []
    
    for i, res in enumerate(ocr_results):
        if i >= len(WJ_MATH_ANSWER_KEY): break
        
        # Normalize input
        raw_text = res["ans"] if isinstance(res, dict) else str(res)
        conf = res.get("conf", True) if isinstance(res, dict) else True
        
        # Clean text: digits only, then common OCR character fixes
        clean_ans = re.sub(r"\D", "", raw_text.strip().upper())
        if not clean_ans:
            if "O" in raw_text: clean_ans = "0"
            elif "I" in raw_text or "L" in raw_text: clean_ans = "1"
        
        correct_ans = str(WJ_MATH_ANSWER_KEY[i])
        is_match = (clean_ans == correct_ans)
        
        if is_match: raw_score += 1
        
        detailed_report.append({
            "question": i + 1,
            "detected": clean_ans if clean_ans else "EMPTY",
            "expected": correct_ans,
            "status": "✅" if is_match else "❌",
            "conf": conf
        })

    return raw_score, detailed_report