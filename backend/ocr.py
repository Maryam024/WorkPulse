import easyocr
import numpy as np
from PIL import Image
import pyautogui
import time
import difflib

# =========================================
# CONFIGURATION
# =========================================
SIMILARITY_THRESHOLD = 0.95  # 95% similarity = idle
OCR_INTERVAL = 10  # seconds between screenshots

# =========================================
# 1️⃣ Load EasyOCR Reader
# =========================================
print("🔠 Loading EasyOCR reader (this may take a few seconds)...")
reader = easyocr.Reader(["en"], gpu=False)
print("✅ OCR reader loaded successfully!\n")

# =========================================
# 2️⃣ OCR helper
# =========================================
def ocr_img(img: Image.Image) -> str:
    """Extract text from image using EasyOCR."""
    results = reader.readtext(np.array(img), detail=0)
    return " ".join(results)

# =========================================
# 3️⃣ Capture + OCR
# =========================================
def capture_screen_text() -> str:
    """Take a screenshot and return extracted text."""
    screenshot = pyautogui.screenshot()
    return ocr_img(screenshot)

# =========================================
# 4️⃣ Compare two texts
# =========================================
def text_similarity(text1: str, text2: str) -> float:
    """Compute similarity ratio between two strings."""
    return difflib.SequenceMatcher(None, text1, text2).ratio()

# =========================================
# 5️⃣ Main OCR monitoring logic
# =========================================
def monitor_screen():
    """Monitor screen changes using OCR."""
    print(f"📸 Starting OCR-based screen activity monitor...")
    print(f"Will check every {OCR_INTERVAL} seconds.\n")

    last_text = ""
    total_idle_time = 0
    total_active_time = 0
    last_state_change = time.time()
    is_idle = False

    try:
        while True:
            current_text = capture_screen_text()

            if not current_text.strip():
                print("⚠️ No readable text detected, skipping this cycle...")
                time.sleep(OCR_INTERVAL)
                continue

            if last_text:
                sim = text_similarity(last_text, current_text)

                if sim >= SIMILARITY_THRESHOLD:
                    # Screen unchanged → idle
                    if not is_idle:
                        is_idle = True
                        active_duration = time.time() - last_state_change
                        total_active_time += active_duration
                        last_state_change = time.time()
                        print(f"🟡 User is idle — text unchanged ({sim*100:.1f}% match)")
                else:
                    # Screen changed → active
                    if is_idle:
                        is_idle = False
                        idle_duration = time.time() - last_state_change
                        total_idle_time += idle_duration
                        last_state_change = time.time()
                        print(f"🟢 User is active — text changed ({(1-sim)*100:.1f}% diff)")

            last_text = current_text
            time.sleep(OCR_INTERVAL)

    except KeyboardInterrupt:
        print("\n⏹️ Monitoring stopped manually.")

    finally:
        now = time.time()
        if is_idle:
            total_idle_time += now - last_state_change
        else:
            total_active_time += now - last_state_change

        print("\n========== SESSION SUMMARY ==========")
        print(f"🟢 Active time: {total_active_time / 60:.2f} minutes")
        print(f"🟡 Idle time:   {total_idle_time / 60:.2f} minutes")
        print("=====================================")


# =========================================
# Run directly
# =========================================
if __name__ == "__main__":
    monitor_screen()
