import fitz  # PyMuPDF
import os
import json
import re
from collections import defaultdict
from difflib import SequenceMatcher
import time
from collections import defaultdict
import unicodedata

INPUT_DIR = "input"
OUTPUT_DIR = "output"
MAX_HEADINGS = 30

RE_REPEAT_PATTERNS = re.compile(r'(\b\w{1,3}\b)( \1)+')
RE_REPEATED_CHARS = re.compile(r'(.)\1{4,}')

def is_bold(font_flags):
    return bool(font_flags & 2)

def is_repetitive(text):
    words = text.lower().split()
    return len(set(words)) <= 2 and len(words) > 1

def is_ocr_noise(text):
    if len(RE_REPEAT_PATTERNS.findall(text)) > 1:
        return True
    if RE_REPEATED_CHARS.search(text):
        return True
    if sum(1 for c in text if not c.isalnum() and c != ':') > len(text) * 0.3:
        return True
    return False

def is_label_like(text):
    return text.isupper() and len(text.split()) <= 3

def clean_ocr_artifacts(text):
    words = text.split()
    cleaned = []
    for i, word in enumerate(words):
        if i >= 2 and word == words[i - 1] == words[i - 2]:
            continue
        cleaned.append(word)
    return ' '.join(cleaned)

def collapse_repeats(text):
    return re.sub(r'(\b\w+\b)( \1\b)+', r'\1', text)

def fix_spacing(text):
    text = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', text)
    text = re.sub(r'(?<=\d)(?=[A-Z])', ' ', text)
    text = re.sub(r'([A-Z]{2,})([A-Z][a-z])', r'\1 \2', text)
    return text

def merge_spans_to_lines(blocks):
    lines = []
    for b in blocks:
        if "lines" not in b:
            continue
        for line in b["lines"]:
            spans = line.get("spans", [])
            if not spans:
                continue
            spans_sorted = sorted(spans, key=lambda s: s["bbox"][0])
            merged_text = ""
            prev_x1 = None
            sizes = []
            flags = []
            for span in spans_sorted:
                text = span["text"].strip()
                if not text:
                    continue
                x0 = span["bbox"][0]
                x1 = span["bbox"][2]
                if prev_x1 is not None and (x0 - prev_x1 > 2):
                    merged_text += " "
                merged_text += text
                prev_x1 = x1
                sizes.append(span["size"])
                flags.append(span["flags"])
            y0 = line["bbox"][1]
            if merged_text.strip():
                lines.append({
                    "text": merged_text.strip(),
                    "y0": y0,
                    "sizes": sizes,
                    "flags": flags
                })
    return lines

def group_multiline_headings(lines):
    grouped = []
    i = 0
    while i < len(lines):
        current = lines[i]
        text = current['text']
        sizes = current['sizes'][:]
        flags = current['flags'][:]
        y0 = current['y0']
        j = i + 1
        while j < len(lines):
            next_line = lines[j]
            y_gap = next_line['y0'] - lines[j - 1]['y0']
            size_diff = abs(sum(next_line['sizes']) / len(next_line['sizes']) - sum(current['sizes']) / len(current['sizes']))
            if y_gap < 12 and size_diff < 1:
                text += " " + next_line['text']
                sizes += next_line['sizes']
                flags += next_line['flags']
                j += 1
            else:
                break
        grouped.append({
            "text": text.strip(),
            "sizes": sizes,
            "flags": flags,
            "y0": y0
        })
        i = j
    return grouped

def is_similar(text1, text2, threshold=0.8):
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio() > threshold

def detect_script(text):
    scripts = defaultdict(int)
    for char in text:
        if char.isalpha():
            name = unicodedata.name(char, "")
            if "CJK" in name or "HIRAGANA" in name or "KATAKANA" in name:
                scripts["Japanese"] += 1
            elif "HANGUL" in name:
                scripts["Korean"] += 1
            elif "CYRILLIC" in name:
                scripts["Cyrillic"] += 1
            elif "ARABIC" in name:
                scripts["Arabic"] += 1
            elif "DEVANAGARI" in name:
                scripts["Devanagari"] += 1
            elif "LATIN" in name:
                scripts["Latin"] += 1
    return max(scripts, key=scripts.get) if scripts else "Unknown"


def extract_outline_final(pdf_path):
    doc = fitz.open(pdf_path)
    candidate_headings = []
    possible_titles = []
    seen_texts = []
    font_sizes_by_freq = defaultdict(int)

    for page_number, page in enumerate(doc, start=1):
        blocks = page.get_text("dict")["blocks"]
        raw_lines = merge_spans_to_lines(blocks)
        lines = group_multiline_headings(raw_lines)

        for line in lines:
            raw_text = line["text"]
            text = fix_spacing(raw_text)
            text = clean_ocr_artifacts(text)
            text = collapse_repeats(text)

            if len(text.strip()) < 4 and not text.strip().isupper() and not text.strip().isdigit():
                continue

            if not text or is_repetitive(text) or '@' in text or text.lower().startswith("note:"):
                continue
            if re.fullmatch(r'[\W\s]{3,}', text):
                continue
            if len(text.split()) > 30 or (text.endswith('.') and len(text.split()) < 6):
                continue
            if is_ocr_noise(text):
                continue
            if any(is_similar(text, seen) for seen in seen_texts[-30:]):  # ✅ limit comparisons
                continue

            seen_texts.append(text)

            avg_size = sum(line["sizes"]) / len(line["sizes"])
            bold = any(is_bold(f) for f in line["flags"])
            y0 = line["y0"]
            word_count = len(text.split())

            script = detect_script(text)
            is_multilingual = script != "Latin"

            if is_multilingual:
                cap_ratio = 0  
                script_bonus = 3
            else:
                cap_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
                script_bonus = 0

            score = avg_size + (3 * cap_ratio) + (5 if bold else 0) + script_bonus

            if y0 < 300:
                score += 3
            if word_count < 10:
                score += 2
            if text.endswith(":"):
                score += 2
            if is_label_like(text):
                score -= 3

            font_sizes_by_freq[round(avg_size)] += 1

            if page_number == 1 and y0 < page.rect.height * 0.2 and word_count <= 10:
                possible_titles.append((score, text))

            candidate_headings.append({
                "text": text,
                "page": page_number,
                "size": avg_size,
                "bold": bold,
                "y0": y0,
                "score": score
            })

    base_font_size = max(font_sizes_by_freq.items(), key=lambda x: x[1])[0] if font_sizes_by_freq else 12

    outline = []
    used_texts = set()
    for h in sorted(candidate_headings, key=lambda x: (-x["score"], -x["size"])):
        if h["text"] in used_texts:
            continue
        used_texts.add(h["text"])

        size = h["size"]
        score = h["score"]

        if score > 20 and size >= base_font_size + 6:
            level = "H1"
        elif score > 15 and size >= base_font_size + 3:
            level = "H2"
        elif score > 10 and size > base_font_size:
            level = "H3"
        elif h.get("script") == "Devanagari" and score > 8:
            level = "H3" 
        else:
            continue


        outline.append({
            "level": level,
            "text": h["text"],
            "page": h["page"]-1
        })

        if len(outline) >= MAX_HEADINGS:
            break

    title = max(possible_titles, key=lambda x: x[0])[1] if possible_titles else "UNKNOWN"

    if possible_titles:
        title = max(possible_titles, key=lambda x: x[0])[1]
    else:
        # fallback: pick first H1 from outline
        h1_candidates = [h for h in outline if h["level"] == "H1"]
        title = h1_candidates[0]["text"] if h1_candidates else "UNKNOWN"

    return {
        "title": title,
        "outline": outline
    }

def main():
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pdf_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".pdf")]
    if not pdf_files:
        print("No PDF files found in /input.")
        return

    for pdf_file in pdf_files:
        file_name = os.path.splitext(os.path.basename(pdf_file))[0]
        print(f"🔍 Processing: {file_name}")

        start_time = time.time()
        result = extract_outline_final(os.path.join(INPUT_DIR, pdf_file))

        output_file = os.path.join(OUTPUT_DIR, f"{file_name}_final.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)


        end_time = time.time()
        print(f"✅ Saved: {output_file}")
        print(f"⏱️ Time taken: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    main()
