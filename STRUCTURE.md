# Cấu trúc thư mục — WebTutorCenter Chatbot Service

Tài liệu này mô tả cây thư mục và **nhiệm vụ của từng file**.
Tổng quan tài liệu, cách chạy và API xem ở [README.md](README.md).

## Tổng quan

```
chatbot-service/
├── app/                      # Mã nguồn service
│   ├── __init__.py
│   ├── main.py               # Điểm vào FastAPI
│   ├── config.py             # Cấu hình (.env)
│   ├── api/                  # Vỏ HTTP
│   │   ├── __init__.py
│   │   ├── routes.py         # POST /api/chat
│   │   └── deps.py           # Dựng & inject engine, xác thực secret
│   ├── clients/              # Gọi ra ngoài
│   │   ├── __init__.py
│   │   └── backend.py        # Gọi ngược API của Backend
│   ├── core/                 # LÕI (logic thuần, không phụ thuộc FastAPI)
│   │   ├── __init__.py
│   │   ├── engine.py         # Điều phối cache → resolvers → AI
│   │   ├── types.py          # Kiểu dữ liệu lõi
│   │   ├── normalizer.py     # Chuẩn hoá tiếng Việt
│   │   ├── cache.py          # TTL cache
│   │   ├── prompt.py         # Dựng prompt AI (RAG-lite)
│   │   ├── providers/        # Nhà cung cấp AI
│   │   │   ├── __init__.py
│   │   │   ├── base.py       # Interface AIProvider
│   │   │   └── groq.py       # Cài đặt Groq
│   │   └── resolvers/        # Các mắt xích rule
│   │       ├── __init__.py
│   │       ├── base.py       # Interface Resolver + helper so khớp
│   │       ├── greeting.py   # Chào hỏi / smalltalk
│   │       ├── mine.py       # Dữ liệu cá nhân "của tôi" (JWT → BE)
│   │       ├── keyword.py    # Phân loại ý định điều hướng
│   │       ├── faq.py        # Truy hồi FAQ
│   │       ├── data.py       # Câu cần dữ liệu sống chung (gọi BE)
│   │       └── registry.py   # Lắp ráp chuỗi resolver
│   └── data/                 # RULE = DATA
│       ├── intents.json      # Ý định (smalltalk + điều hướng)
│       └── faq.json          # Kho tri thức FAQ
├── tests/                    # Kiểm thử (pytest)
│   ├── __init__.py
│   ├── conftest.py           # Fixtures + AI/Backend giả
│   ├── test_resolvers.py
│   ├── test_engine.py
│   └── test_api.py
├── .env                      # Cấu hình thật (bí mật, KHÔNG commit)
├── .env.example              # Mẫu cấu hình
├── .gitignore
├── .dockerignore
├── Dockerfile                # Image Docker
├── docker-compose.yml        # Chạy bằng compose
├── pyproject.toml            # Metadata + dependencies + cấu hình test
├── README.md                 # Tài liệu tổng quan
└── STRUCTURE.md              # File này
```

---

## `app/` — Mã nguồn service

| File | Nhiệm vụ |
|------|----------|
| [`__init__.py`](app/__init__.py) | Đánh dấu package, khai báo `__version__`. |
| [`main.py`](app/main.py) | Tạo FastAPI app: bật CORS, `lifespan` dựng/đóng engine khi khởi động/tắt, mount router, endpoint `GET /health`. |
| [`config.py`](app/config.py) | Lớp `Settings` (pydantic-settings) đọc `.env`; `get_settings()` cache theo tiến trình; thuộc tính `data_dir`, `ai_enabled`. |

### `app/api/` — Vỏ HTTP

| File | Nhiệm vụ |
|------|----------|
| [`__init__.py`](app/api/__init__.py) | Export `router`. |
| [`routes.py`](app/api/routes.py) | Định nghĩa `POST /api/chat`; khai báo Pydantic schema `ChatRequest`/`ChatResponse`; bóc header `Authorization: Bearer` → `ChatContext.auth_token`; chuyển request → `ChatContext`, gọi engine, trả kết quả. |
| [`deps.py`](app/api/deps.py) | `build_engine()` lắp engine + backend client + provider từ `Settings`; `get_engine()` lấy engine singleton (từ `app.state`); `verify_secret()` kiểm header `X-Internal-Secret` nếu có cấu hình. |

### `app/clients/` — Gọi ra ngoài

| File | Nhiệm vụ |
|------|----------|
| [`__init__.py`](app/clients/__init__.py) | Export `BackendClient`. |
| [`backend.py`](app/clients/backend.py) | Client httpx gọi **ngược** về Backend. Endpoint chung: `get_subjects()`, `search_tutors()`. Endpoint **cá nhân** (kèm Bearer token qua `_get_data_auth`): `get_my_profile()`, `get_my_posts()`, `get_my_applications()`, `get_my_invitations()`. Bóc `data` trong response `{success,message,data}`; nuốt mọi lỗi mạng → trả `None`. |

### `app/core/` — Lõi logic (tách khỏi FastAPI)

| File | Nhiệm vụ |
|------|----------|
| [`__init__.py`](app/core/__init__.py) | Export `ChatEngine` và các kiểu dữ liệu. |
| [`engine.py`](app/core/engine.py) | `ChatEngine.answer()` — điều phối trung tâm: kiểm **cache** → chạy **chuỗi resolver** (dừng khi đạt ngưỡng confidence) → **AI fallback** (kèm RAG-lite) → **log flywheel** → cache lại. Có suy biến khi không có AI. |
| [`types.py`](app/core/types.py) | Các dataclass thuần: `Source` (enum nguồn, gồm `mine`), `Message`, `ChatContext` (kèm `auth_token` — JWT của user), `Resolution` (câu trả lời + confidence + source + meta). |
| [`normalizer.py`](app/core/normalizer.py) | Chuẩn hoá tiếng Việt: `strip_accents` (bỏ dấu), `normalize`, `tokenize`, `content_tokens` (bỏ stopword) + tập `STOPWORDS`. |
| [`cache.py`](app/core/cache.py) | `TTLCache` — cache LRU + hết hạn theo thời gian, giới hạn kích thước. |
| [`prompt.py`](app/core/prompt.py) | `SYSTEM_PERSONA` + `build_system_prompt` (nhét FAQ làm ngữ cảnh) + `build_messages` (ghép system + lịch sử + câu hỏi cho Groq). |

#### `app/core/providers/` — Nhà cung cấp AI

| File | Nhiệm vụ |
|------|----------|
| [`__init__.py`](app/core/providers/__init__.py) | Export `AIProvider`, `AIProviderError`. |
| [`base.py`](app/core/providers/base.py) | Interface trừu tượng `AIProvider` (`async complete()`, `aclose()`) + lỗi `AIProviderError`. Engine chỉ phụ thuộc interface này. |
| [`groq.py`](app/core/providers/groq.py) | `GroqProvider` — cài đặt gọi Groq SDK (import lười để lõi vẫn test được khi chưa cài `groq`); xử lý lỗi/timeout. |

#### `app/core/resolvers/` — Các mắt xích rule (Chain of Responsibility)

| File | Nhiệm vụ |
|------|----------|
| [`__init__.py`](app/core/resolvers/__init__.py) | Export các resolver + `build_resolvers`. |
| [`base.py`](app/core/resolvers/base.py) | Interface `Resolver` (`async resolve()`) + helper so khớp: `jaccard`, `coverage`, `compute_generic` (xác định token quá phổ biến), `load_json`. |
| [`greeting.py`](app/core/resolvers/greeting.py) | `GreetingResolver` — xử lý smalltalk (chào/cảm ơn/tạm biệt/"bạn là ai"). Chỉ trả lời khi câu **gần như chỉ** là lời chào, không nuốt câu có nội dung nghiệp vụ. |
| [`mine.py`](app/core/resolvers/mine.py) | `MineResolver` — trả lời câu **cá nhân** ("của tôi"): hồ sơ, bài đăng, đơn ứng tuyển, lời mời. Forward JWT (`ctx.auth_token`) xuống BE. Cần tín hiệu sở hữu + danh từ miền mới kích hoạt. Chưa đăng nhập ⇒ nhắc login; đã nhận diện thì **không** nhường AI (tránh bịa dữ liệu riêng tư); gate intent gia sư theo `user.role`; kết quả `cacheable=false`. |
| [`keyword.py`](app/core/resolvers/keyword.py) | `KeywordResolver` — phân loại ý định điều hướng theo coverage từ khoá; **distinctive-gate** (cần ≥1 token đặc trưng) + tie-break theo số token khớp để tránh khớp nhầm. |
| [`faq.py`](app/core/resolvers/faq.py) | `FaqResolver` — truy hồi câu trả lời từ kho FAQ (trộn jaccard + coverage + distinctive-gate); `top_contexts()` cung cấp FAQ liên quan cho RAG-lite. |
| [`data.py`](app/core/resolvers/data.py) | `DataResolver` — nhận diện câu cần **dữ liệu sống**, gọi ngược Backend: đếm gia sư theo môn, liệt kê môn đang dạy. Chỉ kích hoạt khi có trigger rõ ràng; kết quả không cache. |
| [`registry.py`](app/core/resolvers/registry.py) | `build_resolvers()` — nạp `intents.json`/`faq.json`, lắp chuỗi theo thứ tự `greeting → mine → data → keyword → faq`; trả kèm `FaqResolver` để engine dùng cho RAG. |

### `app/data/` — Rule dưới dạng dữ liệu

| File | Nhiệm vụ |
|------|----------|
| [`intents.json`](app/data/intents.json) | 24 ý định. Mỗi intent: `tag`, `type` (`smalltalk`/`intent`), `patterns` (mẫu từ khoá), `responses`, `suggestions`. |
| [`faq.json`](app/data/faq.json) | 16 mục FAQ. Mỗi mục: `id`, `questions` (nhiều biến thể câu hỏi), `answer`, `keywords`, `suggestions`. |

---

## `tests/` — Kiểm thử

| File | Nhiệm vụ |
|------|----------|
| [`__init__.py`](tests/__init__.py) | Đánh dấu package test. |
| [`conftest.py`](tests/conftest.py) | Fixtures dùng chung: `FakeProvider` (AI giả, không gọi mạng), `FakeBackend` (kèm endpoint cá nhân giả), `engine`, `client` (FastAPI TestClient). |
| [`test_resolvers.py`](tests/test_resolvers.py) | Test `normalizer` + từng resolver (greeting/keyword/faq/data/mine). |
| [`test_engine.py`](tests/test_engine.py) | Test engine: Chain of Responsibility, AI fallback, cache, suy biến khi không có AI. |
| [`test_api.py`](tests/test_api.py) | Test endpoint HTTP `/health` và `/api/chat` (kể cả validate input). |

---

## File cấu hình & hạ tầng (thư mục gốc)

| File | Nhiệm vụ |
|------|----------|
| `.env` | Cấu hình **thật** (chứa `GROQ_API_KEY`). Nằm trong `.gitignore` — **không commit**. |
| [`.env.example`](.env.example) | Mẫu cấu hình để copy thành `.env`. |
| [`.gitignore`](.gitignore) | Bỏ qua `.env`, virtualenv, cache, log… khỏi git. |
| [`.dockerignore`](.dockerignore) | Loại file không cần khỏi Docker build context. |
| [`Dockerfile`](Dockerfile) | Dựng image `python:3.12-slim`, cài package, chạy uvicorn. |
| [`docker-compose.yml`](docker-compose.yml) | Chạy service bằng compose: đọc `.env`, map port, healthcheck. |
| [`pyproject.toml`](pyproject.toml) | Metadata dự án, dependencies, extras `dev`, cấu hình `pytest`/`ruff`, build backend (hatchling). |
| [`README.md`](README.md) | Tài liệu tổng quan, hướng dẫn cài đặt/chạy, API. |
| `STRUCTURE.md` | File này — cấu trúc thư mục & giải thích từng file. |

---

## Luồng xử lý một request (để dễ hình dung)

```
POST /api/chat
   │
   ▼
routes.py  ──►  deps.get_engine()  ──►  core/engine.py: ChatEngine.answer()
                                              │
        ┌─────────────────────────────────────┼───────────────────────────────┐
        ▼                                       ▼                               ▼
   cache.py (hit?)       resolvers/* (greeting→mine→data→keyword→faq)    providers/groq.py
        │                    │ dùng normalizer.py + base.py helper        │ (khi rule bó tay,
        │                    │ mine.py/data.py → clients/backend.py       │  kèm prompt.py RAG)
        └───────────────────►└────────────────────────────────────────────┘
                                              │
                                              ▼
                                     Resolution → ChatResponse (routes.py)
```
