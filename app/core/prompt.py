"""Dựng prompt cho AI — kèm RAG-lite (nhét FAQ liên quan làm ngữ cảnh)."""
from __future__ import annotations

from .types import Message

SYSTEM_PERSONA = (
    "Bạn là trợ lý ảo của WebTutorCenter — nền tảng kết nối gia sư và học viên "
    "(tìm gia sư, đăng tin tìm lớp, gia sư ứng tuyển/nhận lớp, đánh giá, mã ưu đãi, "
    "báo giá học phí, chat với admin).\n"
    "Quy tắc trả lời:\n"
    "- Trả lời bằng tiếng Việt, thân thiện, NGẮN GỌN (2-4 câu), đi thẳng vào việc.\n"
    "- Chỉ trả lời trong phạm vi WebTutorCenter. Câu ngoài phạm vi: lịch sự từ chối "
    "và gợi ý hỏi về dịch vụ của trung tâm.\n"
    "- Nếu không chắc, khuyên người dùng liên hệ hỗ trợ hoặc chat với admin, "
    "KHÔNG bịa thông tin (số liệu, giá, chính sách).\n"
    "- Ưu tiên dùng thông tin trong phần 'NGỮ CẢNH' nếu có liên quan."
)


def build_system_prompt(faq_contexts: list[str]) -> str:
    """Ghép persona + ngữ cảnh FAQ (nếu có)."""
    if not faq_contexts:
        return SYSTEM_PERSONA
    context_block = "\n\n".join(f"- {c}" for c in faq_contexts)
    return f"{SYSTEM_PERSONA}\n\nNGỮ CẢNH (tham khảo, có thể không đầy đủ):\n{context_block}"


def build_messages(
    query: str,
    history: list[Message],
    faq_contexts: list[str],
    *,
    max_history: int = 6,
) -> list[dict[str, str]]:
    """Tạo danh sách message dạng OpenAI/Groq: [system, ...history, user]."""
    messages: list[dict[str, str]] = [
        {"role": "system", "content": build_system_prompt(faq_contexts)}
    ]
    for msg in history[-max_history:]:
        role = msg.role if msg.role in ("user", "assistant") else "user"
        if msg.content and msg.content.strip():
            messages.append({"role": role, "content": msg.content.strip()})
    messages.append({"role": "user", "content": query.strip()})
    return messages
