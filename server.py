import os
import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from paddleocr import PaddleOCR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ocr-server")

ocr_instance = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ocr_instance
    logger.info("Initializing PaddleOCR...")
    ocr_instance = PaddleOCR(lang="ch", use_textline_orientation=False)
    logger.info("PaddleOCR initialized.")
    yield
    ocr_instance = None


app = FastAPI(title="OCR Service", version="1.0.0", lifespan=lifespan)

INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PaddleOCR Test</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f5f5; color: #333; }
  .container { max-width: 800px; margin: 40px auto; padding: 0 20px; }
  h1 { text-align: center; margin-bottom: 8px; font-size: 24px; }
  .subtitle { text-align: center; color: #888; margin-bottom: 24px; font-size: 14px; }
  .card { background: #fff; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
  .card h2 { font-size: 18px; margin-bottom: 16px; }
  .upload-area { border: 2px dashed #ddd; border-radius: 8px; padding: 40px; text-align: center; cursor: pointer; transition: border-color .2s; }
  .upload-area:hover, .upload-area.dragover { border-color: #4a90d9; }
  .upload-area p { color: #999; margin: 8px 0; }
  .upload-area img { max-width: 100%; max-height: 300px; display: none; }
  #fileInput { display: none; }
  .btn { display: inline-block; padding: 10px 24px; background: #4a90d9; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; margin-top: 12px; }
  .btn:disabled { background: #ccc; cursor: not-allowed; }
  .btn-group { text-align: center; }
  .result { margin-top: 16px; display: none; }
  .result pre { background: #f9f9f9; padding: 16px; border-radius: 8px; overflow-x: auto; font-size: 13px; line-height: 1.6; white-space: pre-wrap; word-break: break-all; }
  .code-block { background: #2d2d2d; color: #e6e6e6; padding: 16px; border-radius: 8px; overflow-x: auto; font-size: 13px; line-height: 1.6; margin: 12px 0; }
  .code-block code { font-family: "Fira Code", "Consolas", monospace; }
  .tab { display: flex; gap: 0; margin-bottom: 0; }
  .tab-btn { padding: 8px 16px; background: #eee; border: none; cursor: pointer; font-size: 13px; border-radius: 6px 6px 0 0; margin-right: 4px; }
  .tab-btn.active { background: #2d2d2d; color: #e6e6e6; }
  .tab-content { display: none; }
  .tab-content.active { display: block; }
  .loading { display: none; text-align: center; margin: 12px 0; color: #4a90d9; }
  .status { font-size: 13px; color: #4caf50; text-align: center; margin-bottom: 12px; }
  .error { color: #e74c3c; }
</style>
</head>
<body>
<div class="container">
  <h1>PaddleOCR Test</h1>
  <p class="subtitle">PP-OCRv5 · CPU Inference</p>

  <div class="card">
    <h2>Upload Image</h2>
    <div class="upload-area" id="dropZone">
      <p>Click or drag image here</p>
      <p style="font-size:12px;color:#bbb;">Supports PNG, JPG, BMP, WEBP · Max 10MB</p>
      <img id="preview" alt="Preview">
    </div>
    <input type="file" id="fileInput" accept="image/*">
    <div class="loading" id="loading">Processing...</div>
    <div class="btn-group">
      <button class="btn" id="recognizeBtn" disabled>Recognize</button>
    </div>
    <div class="result" id="result">
      <h3 style="margin-bottom:8px;">Result</h3>
      <pre id="resultText"></pre>
    </div>
  </div>

  <div class="card">
    <h2>API Usage</h2>
    <div class="tab">
      <button class="tab-btn active" onclick="switchTab('curl')">curl</button>
      <button class="tab-btn" onclick="switchTab('python')">Python</button>
      <button class="tab-btn" onclick="switchTab('js')">JavaScript</button>
    </div>
    <div class="tab-content active" id="tab-curl">
      <p style="font-size:13px;color:#888;margin:8px 0;">POST an image, returns recognized text and per-line confidence.</p>
      <div class="code-block"><code>curl -X POST http://HOST:18001/ocr \\
  -F "file=@your_image.png"</code></div>
    </div>
    <div class="tab-content" id="tab-python">
      <p style="font-size:13px;color:#888;margin:8px 0;">Use Python requests library.</p>
      <div class="code-block"><code>import requests

with open("your_image.png", "rb") as f:
    r = requests.post(
        "http://HOST:18001/ocr",
        files={"file": f}
    )
print(r.json())</code></div>
    </div>
    <div class="tab-content" id="tab-js">
      <p style="font-size:13px;color:#888;margin:8px 0;">Browser or Node.js with fetch.</p>
      <div class="code-block"><code>const form = new FormData();
form.append("file", fileInput.files[0]);

const res = await fetch("http://HOST:18001/ocr", {
  method: "POST",
  body: form
});
console.log(await res.json());</code></div>
    </div>
    <p style="font-size:12px;color:#aaa;margin-top:12px;">Replace <code>HOST</code> with your server IP. Health check: <code>GET /health</code></p>
  </div>
</div>

<script>
const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const preview = document.getElementById("preview");
const recognizeBtn = document.getElementById("recognizeBtn");
const loading = document.getElementById("loading");
const resultDiv = document.getElementById("result");
const resultText = document.getElementById("resultText");
let selectedFile = null;

dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("dragover"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
dropZone.addEventListener("drop", e => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});
fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (file) handleFile(file);
});

function handleFile(file) {
  if (!file.type.startsWith("image/")) { alert("Please select an image file"); return; }
  selectedFile = file;
  recognizeBtn.disabled = false;
  const reader = new FileReader();
  reader.onload = e => {
    preview.src = e.target.result;
    preview.style.display = "block";
    dropZone.querySelectorAll("p").forEach(p => p.style.display = "none");
  };
  reader.readAsDataURL(file);
  resultDiv.style.display = "none";
}

recognizeBtn.addEventListener("click", async () => {
  if (!selectedFile) return;
  loading.style.display = "block";
  recognizeBtn.disabled = true;
  resultDiv.style.display = "none";
  const form = new FormData();
  form.append("file", selectedFile);
  try {
    const res = await fetch("/ocr", { method: "POST", body: form });
    const data = await res.json();
    resultText.textContent = JSON.stringify(data, null, 2);
    resultDiv.style.display = "block";
  } catch (err) {
    resultText.textContent = "Error: " + err.message;
    resultDiv.style.display = "block";
  }
  loading.style.display = "none";
  recognizeBtn.disabled = false;
});

function switchTab(name) {
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
  document.querySelector(`[onclick="switchTab('${name}')"]`).classList.add("active");
  document.getElementById(`tab-${name}`).classList.add("active");
}
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML


@app.post("/ocr")
async def ocr_predict(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are accepted")

    suffix = os.path.splitext(file.filename or "img.png")[1] or ".png"
    filename = f"{uuid.uuid4().hex}{suffix}"
    path = os.path.join("/tmp", filename)

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 10MB)")

    with open(path, "wb") as f:
        f.write(content)

    try:
        result = ocr_instance.ocr(path, cls=False)
    except Exception as e:
        logger.exception("OCR failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(path):
            os.remove(path)

    if not result or not result[0]:
        return {"text": "", "lines": []}

    lines = []
    full_text = ""
    for item in result[0]:
        text = item[1][0]
        confidence = round(item[1][1], 4)
        box = [[round(p, 2) for p in pt] for pt in item[0]]
        lines.append({"text": text, "confidence": confidence, "box": box})
        full_text += text

    return {"text": full_text, "lines": lines}


@app.get("/health")
async def health():
    return {"status": "ok"}
