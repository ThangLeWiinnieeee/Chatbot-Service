<div align="center">

# WebTutorCenter — Chatbot Service

**Chatbot hybrid (rule-based + AI fallback) cho nền tảng gia sư WebTutorCenter.**
Rule chạy trước để trả lời tức thì với 0 token; chỉ gọi AI (Groq) khi rule "bó tay".

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)
![Groq](https://img.shields.io/badge/AI-Groq%20LLM-F55036?logo=groq&logoColor=white)
![Tests](https://img.shields.io/badge/tests-38%20passed-brightgreen?logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

</div>

---

## Mục lục

- [Giới thiệu](#giới-thiệu)
- [Tính năng](#tính-năng)
- [Cách hoạt động](#cách-hoạt-động)
- [Công nghệ](#công-nghệ)
- [Bắt đầu nhanh](#bắt-đầu-nhanh)
- [Cấu hình](#cấu-hình)
- [API](#api)
- [Cơ chế bên trong](#cơ-chế-bên-trong)
- [Mở rộng rule](#mở-rộng-rule-flywheel)
- [Kiểm thử](#kiểm-thử)
- [Docker](#docker)
- [Tích hợp với Backend](#tích-hợp-với-backend)
- [Bảo mật](#bảo-mật)
- [Cấu trúc dự án](#cấu-trúc-dự-án)
- [License](#license)

---

## Giới thiệu

Đây là **microservice chatbot** đứng riêng, phục vụ website [WebTutorCenter](../) (kết nối gia sư ↔ học viên).
Backend Node/Express không tự xử lý hội thoại mà **proxy** câu hỏi của người dùng sang service này qua HTTP `POST /api/chat`.

Triết lý thiết kế: **tối ưu chi phí token**. Phần lớn câu hỏi của người dùng là lặp lại và có thể trả lời bằng
luật (chào hỏi, hướng dẫn đăng ký, học phí…). Chatbot chạy các **resolver rule** trước; chỉ khi không luật nào
đủ tự tin mới chuyển câu hỏi cho **mô hình ngôn ngữ (Groq LLM)**.

> Lõi `app/core/` là **logic thuần**, tách hoàn toàn khỏi FastAPI để có thể tái sử dụng cho project khác.

## Tính năng

- **Hybrid rule + AI** — Chain of Responsibility, dùng ngưỡng confidence để chọn rule hay AI.
- **Rule 0 token** — greeting, phân loại ý định, FAQ; trả lời tức thì không gọi mạng.
- **AI fallback (Groq)** — model `llama-3.3-70b-versatile`, kèm **RAG-lite** (nhét FAQ liên quan vào prompt).
- **Gọi ngược Backend** — resolver `data` lấy số liệu sống (danh sách môn, số lượng gia sư) qua API của BE.
- **Dữ liệu cá nhân (JWT)** — resolver `mine` forward Bearer token của người dùng xuống BE để trả lời *"bài đăng của tôi"*, *"hồ sơ của tôi"*, *"đơn ứng tuyển"*, *"lời mời dạy"*; không bao giờ để AI bịa dữ liệu riêng tư.
- **Tối ưu tiếng Việt** — chuẩn hoá bỏ dấu + *distinctive-gate* chống khớp nhầm do token phổ biến.
- **Cache TTL** — câu hỏi lặp không gọi lại AI.
- **Flywheel** — log câu rớt xuống AI để dần biến thành rule mới (0 token).
- **Provider-agnostic** — đổi Groq ↔ Gemini ↔ self-host chỉ bằng cài đặt lại 1 interface.
- **Có test** — 38 test (resolver / engine / API) chạy không cần mạng.

## Cách hoạt động

```
                         ┌──────────────────────────────────────────────┐
  POST /api/chat  ─────► │                  ChatEngine                  │
   { message }           │                                              │
                         │   1. Cache?  ──yes──►  trả lời (0 token)      │
                         │        │ no                                   │
                         │        ▼                                      │
                         │   2. Chuỗi resolver (Chain of Responsibility) │
                         │      greeting → mine → data → keyword → faq   │
                         │        │                                      │
                         │   confidence ≥ ngưỡng?  ──yes──►  trả lời rule│
                         │        │ no                                   │
                         │        ▼                                      │
                         │   3. AI fallback (Groq + RAG-lite)            │
                         │        │                                      │
                         │   4. Log flywheel  ──►  cache  ──►  trả lời   │
                         └──────────────────────────────────────────────┘
```

| Tầng | Khi nào dùng | Chi phí | Ví dụ câu hỏi |
|------|--------------|---------|---------------|
| **Rule** (greeting/intent/FAQ/data) | Câu phổ biến, có mẫu | 0 token | *"xin chào"*, *"làm sao đăng ký"*, *"có bao nhiêu gia sư môn Toán"* |
| **Mine** (dữ liệu cá nhân) | Câu "của tôi", cần đăng nhập | 0 token | *"bài đăng của tôi"*, *"hồ sơ của tôi"*, *"đơn ứng tuyển của tôi"* |
| **AI** (Groq LLM) | Rule không đủ tự tin | Tốn token | *"gia sư ở đây có dạy piano cho người lớn không"* |

## Công nghệ

| Thành phần | Lựa chọn |
|------------|----------|
| Ngôn ngữ | Python ≥ 3.11 (đã kiểm thử trên 3.14) |
| Web framework | FastAPI + Uvicorn |
| Cấu hình | pydantic-settings (đọc `.env`) |
| HTTP client | httpx (async) |
| AI provider | Groq SDK — OpenAI-compatible, free tier |
| Test | pytest + pytest-asyncio |
| Đóng gói | Docker / docker-compose |

## Bắt đầu nhanh

```bash
# 1) Tạo & kích hoạt virtualenv
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate       # macOS / Linux

# 2) Cài dependency (kèm nhóm dev để chạy test)
pip install -e ".[dev]"

# 3) Cấu hình biến môi trường
cp .env.example .env              # rồi điền GROQ_API_KEY
#   (file .env có thể đã được tạo sẵn với key của bạn)

# 4) Chạy service (dev, auto-reload)
uvicorn app.main:app --reload --port 8001

# 5) Chạy test
pytest
```

Kiểm tra nhanh sau khi chạy:

```bash
curl http://localhost:8001/health
# {"status":"ok","ai":true}

curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"làm sao để đăng ký tài khoản\"}"
```

## Cấu hình

Tất cả biến đọc từ `.env` (xem [.env.example](.env.example)).

| Biến | Mặc định | Ý nghĩa |
|------|----------|---------|
| `GROQ_API_KEY` | *(trống)* | API key Groq. Trống ⇒ chạy **rule-only**, không có AI fallback. |
| `AI_MODEL` | `llama-3.3-70b-versatile` | Model Groq. |
| `AI_TEMPERATURE` | `0.3` | Độ sáng tạo của AI. |
| `AI_MAX_TOKENS` | `512` | Giới hạn độ dài câu trả lời AI. |
| `RULE_CONFIDENCE_THRESHOLD` | `0.6` | Rule đạt confidence ≥ ngưỡng ⇒ trả lời luôn, không gọi AI. |
| `FAQ_CONTEXT_K` | `3` | Số FAQ nhét vào prompt AI (RAG-lite). |
| `CACHE_TTL_SECONDS` | `3600` | Thời gian sống của cache câu trả lời. |
| `CACHE_MAX_SIZE` | `512` | Số câu tối đa trong cache (LRU). |
| `BACKEND_BASE_URL` | `http://localhost:5002/api` | Gốc API của Backend để resolver `data` gọi ngược. |
| `INTERNAL_SECRET` | *(trống)* | Secret nội bộ BE ↔ chatbot. Đặt ⇒ `/api/chat` yêu cầu header `X-Internal-Secret`. |
| `REQUEST_TIMEOUT` | `15` | Timeout (giây) khi gọi Groq / Backend. |
| `HOST` / `PORT` | `0.0.0.0` / `8001` | Địa chỉ HTTP server. |
| `CORS_ORIGINS` | `*` | Danh sách origin (ngăn cách bởi dấu phẩy). |
| `LOG_LEVEL` | `INFO` | Mức log. |

## API

### `POST /api/chat`

**Headers** (tuỳ chọn):

| Header | Khi nào | Ý nghĩa |
|--------|---------|---------|
| `X-Internal-Secret` | Nếu đặt `INTERNAL_SECRET` | Xác thực service-to-service (BE ↔ chatbot). |
| `Authorization: Bearer <token>` | Câu hỏi cá nhân | JWT của người dùng cuối, forward xuống BE cho resolver `mine`. Thiếu ⇒ bot nhắc đăng nhập. |

**Request** — chỉ `message` là bắt buộc; `history` giúp AI hiểu ngữ cảnh nhiều lượt; `user.role` (`tutor`/`user`) giúp `mine` định tuyến đúng:

```json
{
  "message": "làm sao để đăng ký tài khoản?",
  "history": [
    { "role": "user", "content": "chào bạn" },
    { "role": "assistant", "content": "Chào bạn! Mình có thể giúp gì?" }
  ],
  "user": { "id": "u_123", "role": "user" },
  "sessionId": "abc-123"
}
```

**Response:**

```json
{
  "answer": "Để đăng ký, bạn nhấn nút 'Đăng ký' ở góc trên bên phải ...",
  "source": "keyword",
  "intent": "register",
  "confidence": 1.0,
  "suggestions": ["Tôi không nhận được mã OTP", "Làm sao để trở thành gia sư?"],
  "meta": { "cache_hit": false }
}
```

| Trường | Kiểu | Mô tả |
|--------|------|-------|
| `answer` | string | Câu trả lời cho người dùng. |
| `source` | string | Nguồn tạo câu trả lời: `greeting \| mine \| keyword \| faq \| data \| ai \| fallback`. |
| `intent` | string \| null | Nhãn ý định (nếu có). |
| `confidence` | number | Độ tin cậy 0–1. |
| `suggestions` | string[] | Gợi ý câu hỏi tiếp theo. |
| `meta` | object | Thông tin phụ (vd `cache_hit`, `rag_contexts`). |

> Câu trả lời lấy từ cache giữ nguyên `source` gốc và có thêm `meta.cache_hit = true`.

### `GET /health`

```json
{ "status": "ok", "ai": true }
```

`ai` = đã cấu hình Groq key hay chưa.

## Cơ chế bên trong

- **Chain of Responsibility** — resolver chạy theo thứ tự `greeting → mine → data → keyword → faq`; resolver đầu tiên
  đạt `confidence ≥ RULE_CONFIDENCE_THRESHOLD` sẽ trả lời. Không resolver nào đủ tự tin ⇒ chuyển AI.
- **Dữ liệu cá nhân an toàn** — khi `mine` đã nhận diện câu "của tôi", nó **không** nhường xuống AI: chưa đăng nhập ⇒
  nhắc login; BE lỗi/không đủ quyền ⇒ xin lỗi. Tránh AI bịa dữ liệu riêng tư. Kết quả luôn `cacheable=false` (theo
  từng user) nên không rò dữ liệu giữa các user qua cache.
- **Rule = Data** — luật nằm trong [app/data/intents.json](app/data/intents.json) và
  [app/data/faq.json](app/data/faq.json), không hard-code trong code.
- **Chuẩn hoá tiếng Việt** — bỏ dấu để so khớp bền với lỗi gõ (*"hoc phi"* khớp *"học phí"*).
- **Distinctive-gate** — vì bỏ dấu gây trùng âm (*chuyện≈chuyển*) và có token quá phổ biến (*"gia sư"* xuất hiện ở
  hầu hết ý định), resolver chỉ chấp nhận match khi có **≥ 1 token đặc trưng** (tần suất < ~20% corpus). Nhờ đó câu
  ngoài phạm vi rơi đúng xuống AI thay vì bị trả lời sai.
- **RAG-lite** — trước khi gọi AI, engine lấy top-K FAQ liên quan nhét vào prompt để câu trả lời bám dữ liệu thật.
- **Cache TTL + LRU** — câu hỏi lặp trả lời ngay, không gọi lại AI.
- **Flywheel** — mọi câu rớt xuống AI được `logger` ghi lại để định kỳ chuyển thành rule mới.

## Mở rộng rule (flywheel)

Thêm/chỉnh luật **chỉ cần sửa file JSON**, không đụng code:

- [app/data/intents.json](app/data/intents.json) — ý định ngắn theo từ khoá. Mỗi intent có `type`:
  - `smalltalk` → resolver **greeting** (chào hỏi / cảm ơn / tạm biệt / bot là ai).
  - `intent` → resolver **keyword** (đăng ký, tìm gia sư, học phí…).
- [app/data/faq.json](app/data/faq.json) — kho tri thức câu hỏi–trả lời (cũng dùng làm ngữ cảnh cho AI).

> Lưu ý: tránh pattern rút gọn còn toàn token phổ biến (vd chỉ `{gia, sư}`) — sẽ bị *distinctive-gate* loại.
> Hãy đặt cụm đặc trưng, nhiều từ (vd *"đăng ký làm gia sư"*, *"tìm gia sư môn toán"*).

## Kiểm thử

```bash
pytest              # 38 test
pytest -v           # chi tiết từng test
```

Test dùng **AI giả** (không gọi mạng) nên chạy nhanh và ổn định:

| File | Phạm vi |
|------|---------|
| [tests/test_resolvers.py](tests/test_resolvers.py) | Từng resolver (greeting/keyword/faq/data/mine) + normalizer |
| [tests/test_engine.py](tests/test_engine.py) | Chain of Responsibility, AI fallback, cache |
| [tests/test_api.py](tests/test_api.py) | Endpoint HTTP (FastAPI TestClient) |

## Docker

```bash
# Build & chạy bằng docker-compose (đọc .env)
docker compose up --build

# Hoặc build tay
docker build -t wtc-chatbot .
docker run --env-file .env -p 8001:8001 wtc-chatbot
```

## Tích hợp với Backend

```
┌──────────┐  POST /api/chat (X-Internal-Secret          ┌─────────────┐
│    BE     │        + Authorization: Bearer <user JWT>)  │   Chatbot   │
│ (Node/    │ ─────────────────────────────────────────► │  (FastAPI)  │
│  Express) │ ◄───────────────────────────────────────── │             │
└──────────┘  data:     GET /subjects, /tutors/search     └─────────────┘
              mine:     GET /users/user-info, /classes/my-posts,
                        /classes/mine, /classes/invitations  (kèm JWT)
```

- **BE → Chatbot**: Backend proxy câu hỏi người dùng tới `POST http://<chatbot>:8001/api/chat`.
  Nếu đặt `INTERNAL_SECRET`, gửi kèm header `X-Internal-Secret`. Với câu hỏi cá nhân, **forward luôn header
  `Authorization: Bearer <token>`** của người dùng — chatbot chỉ chuyển tiếp token này xuống BE, không tự giải mã.
- **Chatbot → BE**:
  - resolver `data` gọi ngược `BACKEND_BASE_URL` cho câu cần dữ liệu **chung** (danh sách môn, số lượng gia sư…).
  - resolver `mine` gọi các endpoint **cá nhân** (kèm JWT của user) để trả lời câu "của tôi".
  Không nối thẳng MongoDB ⇒ chatbot giữ tính generic. BE tắt ⇒ nuốt lỗi (data → rơi xuống AI; mine → xin lỗi, không
  để AI bịa dữ liệu riêng tư), không làm sập chat.

## Bảo mật

- `.env` chứa `GROQ_API_KEY`, đã nằm trong [.gitignore](.gitignore) — **không commit**.
- Đặt `INTERNAL_SECRET` để chỉ Backend (biết secret) mới gọi được `/api/chat`.
- Nếu API key từng lộ (dán vào chat/log/nơi công khai), hãy **thu hồi & tạo key mới** tại
  <https://console.groq.com/keys>.

## Cấu trúc dự án

Xem chi tiết từng file trong [STRUCTURE.md](STRUCTURE.md).

```
app/
├── main.py        # FastAPI app + lifespan
├── config.py      # Cấu hình (.env)
├── api/           # Vỏ HTTP: routes, deps
├── clients/       # Gọi ngược Backend
├── core/          # LÕI: engine, resolvers, providers, cache, prompt...
└── data/          # RULE = DATA: intents.json, faq.json
tests/             # pytest
```

## License

Phát hành theo giấy phép **MIT**.
