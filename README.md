# PaddleOCR Server

一个基于 FastAPI 的轻量 OCR 服务，提供网页上传体验和 HTTP API，适合在 Dokploy / Docker Compose 环境中部署。

## Features

- 单张图片 OCR 接口：`POST /ocr`
- 内置测试页面：`GET /`
- 健康检查：`GET /health`
- 返回整图文本与逐行识别结果
- 面向生产的基础资源保护：
  - 文件大小限制：10MB
  - 最大宽高：4096 x 4096
  - 最大像素数：12MP
- 基础并发调优：
  - `uvicorn --workers 2`
  - `--limit-concurrency 8`

## Tech Stack

- Python 3.10
- FastAPI
- Uvicorn
- PaddlePaddle 2.6.2
- PaddleOCR 2.7.3
- Docker / Docker Compose

## Project Files

- `server.py` — FastAPI 应用、网页 UI、OCR 接口实现
- `Dockerfile` — 容器镜像构建
- `docker-compose.yml` — Compose 部署配置
- `requirements.txt` — Python 依赖
- `tests/test_server.py` — 回归测试

## API

### `POST /ocr`

使用 `multipart/form-data` 上传图片，字段名必须为 `file`。

#### Request Example

```http
POST /ocr
Content-Type: multipart/form-data

file=@your_image.png
```

#### curl Example

```bash
curl -X POST https://ocr.leejh.cyou/ocr \
  -F "file=@your_image.png"
```

#### Python Example

```python
import requests

with open("your_image.png", "rb") as f:
    r = requests.post(
        "https://ocr.leejh.cyou/ocr",
        files={"file": f}
    )
print(r.json())
```

#### JavaScript Example

```javascript
const form = new FormData();
form.append("file", fileInput.files[0]);

const res = await fetch("https://ocr.leejh.cyou/ocr", {
  method: "POST",
  body: form
});
console.log(await res.json());
```

#### Response Example

```json
{
  "text": "示例识别文本",
  "lines": [
    {
      "text": "示例识别文本",
      "confidence": 0.9987,
      "box": [[12.5, 18.0], [220.1, 18.0], [220.1, 52.3], [12.5, 52.3]]
    }
  ]
}
```

#### Response Fields

- `text` — 整张图片识别出的拼接文本
- `lines` — 逐行识别结果数组
- `lines[].text` — 当前行文本
- `lines[].confidence` — 当前行置信度，范围 0~1
- `lines[].box` — 当前行四边形坐标，格式为 `[[x1,y1],[x2,y2],[x3,y3],[x4,y4]]`

#### Constraints

- 请求字段：`file`
- `Content-Type` 必须匹配 `image/*`
- 当前可接受常见图片类型，如 PNG / JPG / JPEG / BMP / WEBP / GIF / TIFF
- 单张图片大小限制：`10MB`
- 最大宽高：`4096 x 4096`
- 最大像素数：`12MP`
- 如果图片中没有识别到文本，返回：

```json
{"text": "", "lines": []}
```

#### Common Error Responses

```text
400 Bad Request
{"detail": "Only image files are accepted"}

400 Bad Request
{"detail": "Image too large (max 10MB)"}

400 Bad Request
{"detail": "Invalid or unsupported image file"}

400 Bad Request
{"detail": "Image dimensions too large (max 4096x4096)"}

400 Bad Request
{"detail": "Image pixel count too large (max 12MP)"}

500 Internal Server Error
{"detail": "<runtime error message>"}
```

### `GET /health`

```json
{"status": "ok"}
```

## Local Run

### Install

```bash
pip install -r requirements.txt
```

### Start

```bash
uvicorn server:app --host 0.0.0.0 --port 8000 --workers 2 --limit-concurrency 8 --timeout-keep-alive 5
```

服务默认监听：

- `http://127.0.0.1:8000`

## Docker

### Build

```bash
docker build -t paddleocr-server .
```

### Run

```bash
docker run --rm -p 18001:8000 paddleocr-server
```

## Docker Compose

```yaml
services:
  ocr:
    build: .
    container_name: paddleocr-server
    restart: unless-stopped
    ports:
      - "18001:8000"
    environment:
      - TZ=Asia/Shanghai
    volumes:
      - ocr_models:/root/.paddleocr

volumes:
  ocr_models:
```

## Dokploy Notes

当前推荐按 **ARM 原生** 路线部署：

- 不要在 `docker-compose.yml` 中强制 `platform: linux/amd64`
- 直接使用当前仓库中的 ARM 原生依赖组合：
  - `paddlepaddle==2.6.2`
  - `paddleocr==2.7.3`
  - `numpy==1.26.4`

如果部署在 Dokploy：

1. 拉取最新 GitHub 代码
2. 重新部署 Compose
3. 部署后验证：

```bash
uname -m
curl http://127.0.0.1:8000/health
```

理想情况下：

- `uname -m` 输出 `aarch64`
- `/health` 返回 `{"status":"ok"}`

## Performance Notes

当前服务不是高并发 OCR 设计，属于保守配置：

- 每个 worker 各自持有一个 PaddleOCR 实例
- 默认 2 个 worker
- 总并发限制 8
- 更适合低到中等并发的图片 OCR 请求

如果并发继续上升，建议结合实际日志观察：

- 单张图 OCR 耗时
- 平均图片尺寸
- CPU 使用率
- 内存占用

## Logging

服务会记录：

- OCR 成功耗时
- OCR 失败耗时
- 文件名
- 文件大小
- 图片分辨率
- 识别到的行数

这有助于后续做性能分析和限流调优。

## Test

```bash
pytest tests/test_server.py -v
```

当前测试覆盖：

- 3.x/2.x 风格返回结构兼容
- 非法图片拒绝
- 大图/高像素图片拒绝
- 成功/失败日志输出
- 空识别结果返回结构

## Hosted Service

当前线上域名：

- `https://ocr.leejh.cyou/`
