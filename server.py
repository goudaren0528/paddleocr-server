import os
import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException
from paddleocr import PaddleOCR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ocr-server")

ocr_instance = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ocr_instance
    logger.info("Initializing PaddleOCR...")
    ocr_instance = PaddleOCR(lang="ch", use_angle_cls=False, use_gpu=False)
    logger.info("PaddleOCR initialized.")
    yield
    ocr_instance = None


app = FastAPI(title="OCR Service", version="1.0.0", lifespan=lifespan)


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
