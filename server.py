import os
import uuid
import time
import logging
from io import BytesIO
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from PIL import Image
from paddleocr import PaddleOCR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ocr-server")

ocr_instance = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ocr_instance
    logger.info("Initializing PaddleOCR...")
    ocr_instance = PaddleOCR(lang="ch", use_angle_cls=False)
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
  .code-block-wrap { margin: 12px 0; }
  .code-block-head { display: flex; justify-content: flex-end; margin-bottom: 6px; }
  .copy-mini { padding: 6px 10px; background: #444; color: #f4f4f4; border: none; border-radius: 6px; cursor: pointer; font-size: 12px; }
  .copy-mini:hover { opacity: 0.92; }
  .copy-mini.copied { background: #2f7d32; }
  .copy-mini.failed { background: #a93226; }
  .tab { display: flex; gap: 0; margin-bottom: 0; }
  .tab-btn { padding: 8px 16px; background: #eee; border: none; cursor: pointer; font-size: 13px; border-radius: 6px 6px 0 0; margin-right: 4px; }
  .tab-btn.active { background: #2d2d2d; color: #e6e6e6; }
  .tab-content { display: none; }
  .tab-content.active { display: block; }
  .loading { display: none; text-align: center; margin: 12px 0; color: #4a90d9; }
  .status { font-size: 13px; color: #4caf50; text-align: center; margin-bottom: 12px; }
  .error { color: #e74c3c; }
  .doc-actions { display: flex; justify-content: flex-end; margin: 10px 0 14px; }
  .mini-btn { padding: 8px 12px; background: #2d2d2d; color: #e6e6e6; border: none; border-radius: 6px; cursor: pointer; font-size: 12px; }
  .mini-btn:hover { opacity: 0.92; }
  .doc-note { font-size: 13px; color: #666; margin: 10px 0; line-height: 1.7; }
  .doc-note code { background: #f1f1f1; padding: 1px 4px; border-radius: 4px; }
  .copy-status { font-size: 12px; color: #4caf50; margin-left: 8px; align-self: center; }
  .copy-status.error { color: #e74c3c; }
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
      <p style="font-size:13px;color:#888;margin:8px 0;">POST an image to the OCR endpoint. The server accepts one multipart file field named <code>file</code> and returns merged text plus per-line details.</p>
      <div class="code-block-wrap">
        <div class="code-block-head"><button class="copy-mini" type="button" onclick="copyCodeBlock(this)">Copy</button></div>
        <div class="code-block"><code>curl -X POST https://ocr.leejh.cyou/ocr \\
  -F "file=@your_image.png"</code></div>
      </div>
    </div>
    <div class="tab-content" id="tab-python">
      <p style="font-size:13px;color:#888;margin:8px 0;">Use Python requests library.</p>
      <div class="code-block-wrap">
        <div class="code-block-head"><button class="copy-mini" type="button" onclick="copyCodeBlock(this)">Copy</button></div>
        <div class="code-block"><code>import requests

with open("your_image.png", "rb") as f:
    r = requests.post(
        "https://ocr.leejh.cyou/ocr",
        files={"file": f}
    )
print(r.json())</code></div>
      </div>
    </div>
    <div class="tab-content" id="tab-js">
      <p style="font-size:13px;color:#888;margin:8px 0;">Browser or Node.js with fetch.</p>
      <div class="code-block-wrap">
        <div class="code-block-head"><button class="copy-mini" type="button" onclick="copyCodeBlock(this)">Copy</button></div>
        <div class="code-block"><code>const form = new FormData();
form.append("file", fileInput.files[0]);

const res = await fetch("https://ocr.leejh.cyou/ocr", {
  method: "POST",
  body: form
});
console.log(await res.json());</code></div>
      </div>
    </div>
    <div class="doc-actions">
      <button class="mini-btn" type="button" onclick="copyAllApiExamples()">Copy all examples</button>
      <span class="copy-status" id="copyStatus"></span>
    </div>
    <div class="doc-note">
      Accepts one required multipart file field named <code>file</code>. The server currently validates <code>Content-Type</code> with the rule <code>image/*</code>, so common image formats supported by clients and OCR pipelines such as PNG, JPG/JPEG, BMP, WEBP, GIF, and TIFF can be uploaded as long as the request is labeled as an image.
    </div>
    <div class="doc-note">
      Size limit: <code>10MB</code> per image. If no text is recognized, the API still returns <code>200 OK</code> with <code>{"text": "", "lines": []}</code>.
    </div>
    <div style="font-size:13px;color:#666;margin-top:14px;line-height:1.7;">
      <p><strong>Request Example</strong></p>
      <div class="code-block-wrap">
        <div class="code-block-head"><button class="copy-mini" type="button" onclick="copyCodeBlock(this)">Copy</button></div>
        <div class="code-block"><code>POST /ocr
Content-Type: multipart/form-data

file=@your_image.png</code></div>
      </div>
      <p><strong>Response Example</strong></p>
      <div class="code-block-wrap">
        <div class="code-block-head"><button class="copy-mini" type="button" onclick="copyCodeBlock(this)">Copy</button></div>
        <div class="code-block"><code>{
  "text": "示例识别文本",
  "lines": [
    {
      "text": "示例识别文本",
      "confidence": 0.9987,
      "box": [[12.5, 18.0], [220.1, 18.0], [220.1, 52.3], [12.5, 52.3]]
    }
  ]
}</code></div>
      </div>
      <p><strong>Field Reference</strong></p>
      <div class="code-block-wrap">
        <div class="code-block-head"><button class="copy-mini" type="button" onclick="copyCodeBlock(this)">Copy</button></div>
        <div class="code-block"><code>file                required image file field (multipart/form-data)
text                concatenated OCR text from the whole image
lines               array of recognized text lines
lines[].text        text content of the line
lines[].confidence  confidence score, range 0-1
lines[].box         quadrilateral coordinates [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]</code></div>
      </div>
      <p><strong>Error Response Examples</strong></p>
      <div class="code-block-wrap">
        <div class="code-block-head"><button class="copy-mini" type="button" onclick="copyCodeBlock(this)">Copy</button></div>
        <div class="code-block"><code>400 Bad Request
{"detail": "Only image files are accepted"}

400 Bad Request
{"detail": "Image too large (max 10MB)"}

500 Internal Server Error
{"detail": "<runtime error message>"}</code></div>
      </div>
    </div>
    <p style="font-size:12px;color:#aaa;margin-top:12px;">Service URL: <code>https://ocr.leejh.cyou</code> · Health check: <code>GET /health</code></p>
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

async function writeClipboard(text) {
  await navigator.clipboard.writeText(text);
}

async function copyCodeBlock(button) {
  const code = button.closest('.code-block-wrap').querySelector('.code-block code').textContent;
  try {
    await writeClipboard(code);
    button.textContent = 'Copied';
    button.classList.remove('failed');
    button.classList.add('copied');
  } catch (err) {
    button.textContent = 'Failed';
    button.classList.remove('copied');
    button.classList.add('failed');
  }
  setTimeout(() => {
    button.textContent = 'Copy';
    button.classList.remove('copied', 'failed');
  }, 1500);
}

async function copyAllApiExamples() {
  const payload = `Service URL\nhttps://ocr.leejh.cyou\n\nRequest Example\nPOST /ocr\nContent-Type: multipart/form-data\n\nfile=@your_image.png\n\nCurl Example\ncurl -X POST https://ocr.leejh.cyou/ocr \\\n  -F "file=@your_image.png"\n\nPython Example\nimport requests\n\nwith open("your_image.png", "rb") as f:\n    r = requests.post(\n        "https://ocr.leejh.cyou/ocr",\n        files={"file": f}\n    )\nprint(r.json())\n\nJavaScript Example\nconst form = new FormData();\nform.append("file", fileInput.files[0]);\n\nconst res = await fetch("https://ocr.leejh.cyou/ocr", {\n  method: "POST",\n  body: form\n});\nconsole.log(await res.json());\n\nResponse Example\n{\n  "text": "示例识别文本",\n  "lines": [\n    {\n      "text": "示例识别文本",\n      "confidence": 0.9987,\n      "box": [[12.5, 18.0], [220.1, 18.0], [220.1, 52.3], [12.5, 52.3]]\n    }\n  ]\n}\n\nField Reference\nfile                required image file field (multipart/form-data)\ntext                concatenated OCR text from the whole image\nlines               array of recognized text lines\nlines[].text        text content of the line\nlines[].confidence  confidence score, range 0-1\nlines[].box         quadrilateral coordinates [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]\n\nConstraints\n- Required field: file\n- Content-Type must match image/*\n- Max image size: 10MB\n- Empty OCR result returns {"text": "", "lines": []}\n\nError Response Examples\n400 Bad Request\n{"detail": "Only image files are accepted"}\n\n400 Bad Request\n{"detail": "Image too large (max 10MB)"}\n\n500 Internal Server Error\n{"detail": "<runtime error message>"}`;
  const copyStatus = document.getElementById("copyStatus");
  try {
    await writeClipboard(payload);
    copyStatus.textContent = "Copied";
    copyStatus.classList.remove("error");
  } catch (err) {
    copyStatus.textContent = "Copy failed";
    copyStatus.classList.add("error");
  }
  setTimeout(() => {
    copyStatus.textContent = "";
    copyStatus.classList.remove("error");
  }, 1800);
}
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML


MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_WIDTH = 4096
MAX_IMAGE_HEIGHT = 4096
MAX_IMAGE_PIXELS = 12_000_000


@app.post("/ocr")
async def ocr_predict(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are accepted")

    suffix = os.path.splitext(file.filename or "img.png")[1] or ".png"
    filename = f"{uuid.uuid4().hex}{suffix}"
    path = os.path.join("/tmp", filename)

    content = await file.read()
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image too large (max 10MB)")

    try:
        with Image.open(BytesIO(content)) as img:
            width, height = img.size
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or unsupported image file")

    if width > MAX_IMAGE_WIDTH or height > MAX_IMAGE_HEIGHT:
        raise HTTPException(status_code=400, detail="Image dimensions too large (max 4096x4096)")

    if width * height > MAX_IMAGE_PIXELS:
        raise HTTPException(status_code=400, detail="Image pixel count too large (max 12MP)")

    with open(path, "wb") as f:
        f.write(content)

    started_at = time.perf_counter()

    try:
        result = ocr_instance.ocr(path)
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.exception("OCR failed after %.2f ms for %s (%d bytes)", elapsed_ms, file.filename, len(content))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(path):
            os.remove(path)

    if not result or not result[0]:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(
            "OCR completed in %.2f ms for %s (%d bytes, %dx%d), lines=0",
            elapsed_ms,
            file.filename,
            len(content),
            width,
            height,
        )
        return {"text": "", "lines": []}

    first_result = result[0]
    lines = []
    full_text = ""

    if hasattr(first_result, "get") and "rec_texts" in first_result:
        texts = first_result.get("rec_texts", [])
        scores = first_result.get("rec_scores", [])
        polys = first_result.get("rec_polys", [])

        for text, confidence, box in zip(texts, scores, polys):
            rounded_box = [[round(p, 2) for p in pt] for pt in box]
            lines.append(
                {
                    "text": text,
                    "confidence": round(confidence, 4),
                    "box": rounded_box,
                }
            )
            full_text += text
    else:
        for item in first_result:
            text = item[1][0]
            confidence = round(item[1][1], 4)
            box = [[round(p, 2) for p in pt] for pt in item[0]]
            lines.append({"text": text, "confidence": confidence, "box": box})
            full_text += text

    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    logger.info(
        "OCR completed in %.2f ms for %s (%d bytes, %dx%d), lines=%d",
        elapsed_ms,
        file.filename,
        len(content),
        width,
        height,
        len(lines),
    )

    return {"text": full_text, "lines": lines}


@app.get("/health")
async def health():
    return {"status": "ok"}
