import re

WJ_MATH_ANSWER_KEY = [
    0, 3, 4, 2, 3, 0, 0, 3, 1, 6,
    5, 2, 7, 8, 5, 2, 5, 8, 3, 3,
    1, 6, 3, 0, 8, 0, 9, 1, 9, 5,
    7, 7, 1, 6, 8, 9, 5, 10, 4, 5,
    4, 10, 12, 2, 12, 0, 8, 2, 0, 7,
    10, 5, 4, 8, 3, 10, 4, 12, 14, 0,
    1, 9, 14, 6, 5, 2, 5, 0, 14, 5,
    10, 4, 7, 17, 9, 1, 4, 6, 3, 12,
    0, 15, 10, 0, 8, 11, 12, 3, 15, 9,
    9, 0, 40, 4, 7, 6, 27, 7, 18, 8,
    11, 63, 2, 16, 16, 28, 1, 12, 2, 0,
    8, 21, 5, 24, 1, 30, 7, 13, 81, 16,
    0, 6, 45, 49, 3, 54, 11, 42, 2, 56,
    15, 32, 3, 2, 2, 18, 36, 4, 35, 13,
    25, 6, 6, 0, 72, 1, 20, 48, 0, 4,
    14, 11, 64, 4, 16, 18, 0, 1, 36, 10
]

def score_results(ocr_results):
    """
    Score OCR results against the WJ Math answer key.
    
    WJ Scoring Rules:
    - Each correct answer = 1 point
    - Scoring stops at the "ceiling" (6 consecutive wrong answers)
    - No points are awarded after the ceiling is reached
    
    Args:
        ocr_results: List of strings from OCR detection
        
    Returns:
        tuple: (raw_score, detailed_report)
    """
    raw_score = 0
    consecutive_wrong = 0
    detailed_report = []
    ceiling_reached = False  # Disabled for testing all items
    
    # For testing: Score all items, ignore ceiling rule
    for i, user_ans in enumerate(ocr_results):
        if i >= len(WJ_MATH_ANSWER_KEY): 
            break
        
        if isinstance(user_ans, dict):
            raw_text = user_ans["ans"]
            conf = user_ans["conf"]
        else:
            raw_text = str(user_ans).strip().upper()
            conf = True
        
        # Normalize both answer key and OCR result to strings
        correct_ans = str(WJ_MATH_ANSWER_KEY[i]).strip()
        # Handle common OCR confusions
        raw_text = str(raw_text).strip().upper()
        
        # USE REGEX TO EXTRACT ONLY THE DIGITS
        # This prevents "The answer is 5" from being marked wrong
        digits_only = re.sub(r"\D", "", raw_text)
        
        # Common OCR fixes
        if not digits_only:
            # Check for letters that look like numbers if no digits found
            if "O" in raw_text: digits_only = "0"
            elif "I" in raw_text or "L" in raw_text: digits_only = "1"
        
        clean_ans = digits_only
        is_match = (clean_ans == correct_ans)
        
        # For testing: Always award points for matches, score all items
        if is_match:
            raw_score += 1
            consecutive_wrong = 0
        else:
            consecutive_wrong += 1
        # After ceiling is reached, no more points are awarded
        # (raw_score remains unchanged)
        
        detailed_report.append({
            "question": i + 1,
            "detected": clean_ans if clean_ans else "EMPTY",
            "expected": correct_ans,
            "status": "✅" if is_match else "❌",
            "ceiling": False,  # Disabled for testing
            "conf": conf
        })

    return raw_score, detailed_report
