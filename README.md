## Document Structure Extractor (PDF → Structured Outline)

## 🚀 Challenge: Connecting the Dots Through Docs — Round 1A

This solution extracts a **structured outline (Title + H1, H2, H3)** from any PDF file up to 50 pages, even if the content is **multilingual** or contains **noisy OCR artifacts**. The output is a clean, hierarchical JSON file suitable for downstream tasks like semantic search, summarization, or insight generation.

---

## 🧩 What This Project Does

✅ Accepts all PDFs in `/app/input/`  
✅ Extracts:  
- Title (top of first page or prominent section)
- Headings: H1, H2, H3 with page number and hierarchy  
✅ Handles multilingual scripts (e.g., **Hindi, Arabic, Chinese, Japanese**)  
✅ Outputs valid JSON to `/app/output/`  
✅ Runs completely **offline**, **within 10 seconds** on 50-page files  
✅ Docker-compatible and CPU-compliant (no GPU/model >200MB used)

---

## 📁 Sample Output Format

```json
{
  "title": "Understanding AI",
  "outline": [
    { "level": "H1", "text": "Introduction", "page": 1 },
    { "level": "H2", "text": "What is AI?", "page": 2 },
    { "level": "H3", "text": "History of AI", "page": 3 }
  ]
}
```
## 📚 How It Works — Core Pipeline (`extract_outline_final`)

### 1. Text Extraction
- Uses **PyMuPDF (fitz)** to extract raw text spans and layout metadata from each PDF page.

### 2. Line Reconstruction
- `merge_spans_to_lines`:  
   Groups fragmented spans horizontally to form single lines.
- `group_multiline_headings`:  
   Merges multi-line headings that belong together based on font size and vertical spacing.

### 3. Cleaning & Heuristics
- **Removes** noisy OCR artifacts, excessive symbols, repeated patterns.
- Applies intelligent **spacing fixes** (e.g., `DeepLearning` → `Deep Learning`).
- Uses **Unicode script detection** to identify text language:  
  Supports multilingual content such as:
  - **Hindi (Devanagari)**
  - **Chinese / Japanese / Korean (CJK)**
  - **Arabic**
  - **Latin, Cyrillic** etc.

### 4. Heading Scoring
Each line is scored using the following features:
- **Font size** (larger gets priority)
- **Boldness** (bold text is preferred)
- **Capitalization ratio** (fully or mostly uppercase)
- **Script type** (multilingual gets a bonus)
- **Vertical position** on the page (top-heavy headings prioritized)
- **Word count & punctuation** (short and clean lines preferred)

### 5. Heading Classification
Based on score and size relative to the most frequent font size:
- `H1`: Highest scores, large & bold
- `H2`: Moderately prominent
- `H3`: Smaller but structured
- **Title**: Extracted from top of page 1 or from early `H1` candidates

### 6. Deduplication
- Avoids duplicate or near-duplicate headings using:
  - Fuzzy matching via `difflib.SequenceMatcher`

---

## 🧠 Why This Is Special

| Feature                         | Benefit |
|--------------------------------|---------|
| ✅ **Multilingual support**     | Accurately detects headings in **Hindi, Arabic, Japanese, Chinese** |
| ✅ **No model needed**          | Extremely lightweight; works offline without ML inference |
| ✅ **Modular pipeline**         | Components are reusable and adaptable for Round 1B |
| ✅ **Not font-size reliant**    | Uses hybrid logic with position, weight, capitalization |
| ✅ **Docker ready**             | Fully compatible with `linux/amd64` architecture |

---
## 🐳 How to Build & Run 

```bash
$ docker build --platform linux/amd64 -t pdf-outline-extractor:latest .
```

```bash
docker run --rm \
  -v "$(pwd -W)/input:/app/input" \
  -v "$(pwd -W)/output:/app/output" \
  --network none \
  pdf-outline-extractor:latest
```
if this test line doesnt work try:
```
docker run --rm \
  -v "$(pwd)/input:/app/input" \
  -v "$(pwd)/output:/app/output" \
  --network none \
  pdf-outline-extractor:latest
```

