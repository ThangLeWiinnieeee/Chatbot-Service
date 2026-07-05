"""Resolver dữ liệu CÁ NHÂN — trả lời câu hỏi về chính người dùng đang đăng nhập.

Bốn năng lực (gọi ngược BE kèm Bearer token của user):
  A. Hồ sơ         ("hồ sơ của tôi", "tài khoản của tôi", "email của tôi")
  B. Bài đăng      ("bài đăng của tôi", "lớp tôi đã đăng")            — người đăng
  C. Đơn ứng tuyển ("lớp tôi ứng tuyển", "đơn ứng tuyển của tôi")     — gia sư
  D. Lời mời       ("lời mời của tôi", "ai mời tôi dạy")              — gia sư

Chỉ kích hoạt khi câu có TÍN HIỆU SỞ HỮU ("của tôi/mình", "tôi") *và* một danh
từ miền cá nhân. Vì "tôi/của/mình" là stopword của so khớp nội dung, ta dò trực
tiếp trên chuỗi đã normalize (giống DataResolver), không qua `content_set`.

Khi đã nhận diện là câu cá nhân, resolver KHÔNG nhường xuống AI:
  - chưa đăng nhập → nhắc đăng nhập;
  - BE lỗi / không có quyền → xin lỗi.
Tránh để AI bịa dữ liệu riêng tư. Mọi kết quả `cacheable=False` (theo từng user).
"""
from __future__ import annotations

from ..normalizer import normalize, tokenize
from ..types import ChatContext, Resolution, Source
from .base import Resolver

_LOGIN_MSG = (
    "Bạn cần đăng nhập để mình xem được thông tin cá nhân (hồ sơ, bài đăng, "
    "đơn ứng tuyển). Bạn đăng nhập rồi hỏi lại giúp mình nhé."
)
_ERROR_MSG = "Mình chưa lấy được thông tin của bạn lúc này. Bạn thử lại sau ít phút nhé."
_TUTOR_ONLY_MSG = (
    "Mục {what} chỉ dành cho tài khoản gia sư. Nếu bạn muốn tìm gia sư, "
    "hãy vào trang Đăng tin để đăng bài nhé."
)

# Nhãn trạng thái để câu trả lời dễ đọc.
_CLASS_STATUS = {
    "open": "đang mở",
    "matched": "đã ghép gia sư",
    "expired": "đã hết hạn",
    "completed": "đã hoàn thành",
}


class MineResolver(Resolver):
    name = "mine"

    def __init__(self, backend) -> None:
        self._backend = backend

    def _intent(self, q_norm: str, q_tokens: set[str], is_tutor: bool | None) -> str | None:
        """Xác định sub-intent cá nhân, hoặc None nếu không phải câu cá nhân."""
        possessive = bool({"toi", "minh"} & q_tokens)
        if not possessive:
            return None

        # D: lời mời (gia sư) — "lời mời", "ai mời tôi dạy"
        if "loi moi" in q_norm or ("moi" in q_tokens and {"day", "lop"} & q_tokens):
            return "invitations"
        # C: đơn ứng tuyển (gia sư) — "ứng tuyển", "tôi nhận lớp nào"
        if "ung tuyen" in q_norm or ("nhan" in q_tokens and "lop" in q_tokens):
            return "applications"
        # B: bài đăng (người đăng) — "bài đăng", "lớp tôi đăng", "tin tôi đăng"
        if "bai dang" in q_norm or "bai viet" in q_norm or (
            "dang" in q_tokens and {"lop", "bai", "tin"} & q_tokens
        ):
            return "posts"
        # A: hồ sơ — "hồ sơ", "tài khoản", "thông tin cá nhân", "email/sđt của tôi"
        if (
            "ho so" in q_norm
            or "tai khoan" in q_norm
            or "thong tin ca nhan" in q_norm
            or {"email", "sdt", "profile"} & q_tokens
            or "so dien thoai" in q_norm
        ):
            return "profile"
        # "lớp của tôi" chung chung → định tuyến theo vai trò nếu biết.
        if "lop" in q_tokens:
            return "applications" if is_tutor else "posts"
        return None

    async def resolve(self, query: str, ctx: ChatContext) -> Resolution | None:
        if self._backend is None:
            return None

        q_norm = normalize(query)
        q_tokens = set(tokenize(query))
        role = (ctx.user or {}).get("role")
        is_tutor = role == "tutor" if role in ("tutor", "user") else None

        intent = self._intent(q_norm, q_tokens, is_tutor)
        if intent is None:
            return None

        if not ctx.auth_token:
            return self._msg(_LOGIN_MSG, intent="auth_required")

        # Chặn sớm intent chỉ dành cho gia sư nếu đã biết vai trò khác.
        if intent in ("applications", "invitations") and is_tutor is False:
            what = "đơn ứng tuyển" if intent == "applications" else "lời mời dạy"
            return self._msg(_TUTOR_ONLY_MSG.format(what=what), intent=intent)

        token = ctx.auth_token
        if intent == "profile":
            return await self._profile(token)
        if intent == "posts":
            return await self._posts(token)
        if intent == "applications":
            return await self._applications(token)
        return await self._invitations(token)

    # --- builders ---

    async def _profile(self, token: str) -> Resolution:
        user = await self._backend.get_my_profile(token)
        if not user:
            return self._msg(_ERROR_MSG, intent="profile")
        name = user.get("fullName") or "bạn"
        role_label = {"tutor": "gia sư", "user": "học viên", "admin": "quản trị"}.get(
            user.get("role"), "thành viên"
        )
        parts = [f"Bạn đang đăng nhập với tên {name} (vai trò: {role_label})."]
        if user.get("email"):
            parts.append(f"Email: {user['email']}.")
        if user.get("phone"):
            parts.append(f"SĐT: {user['phone']}.")
        return self._msg(" ".join(parts), intent="profile")

    async def _posts(self, token: str) -> Resolution:
        data = await self._backend.get_my_posts(token)
        if data is None:
            return self._msg(_ERROR_MSG, intent="posts")
        classes = data.get("classes") or []
        total = _total(data, len(classes))
        if not total:
            return self._msg(
                "Bạn chưa đăng bài tìm gia sư nào. Vào trang Đăng tin để tạo bài mới nhé.",
                intent="posts",
                suggestions=["Làm sao để đăng tin tìm gia sư?"],
            )
        lines = []
        for c in classes[:5]:
            status = _CLASS_STATUS.get(c.get("status"), c.get("status", ""))
            summary = f" — {c['summary']}" if c.get("summary") else ""
            lines.append(f"- {c.get('subject', 'Lớp')}: {status}{summary}")
        more = f"\n… và {total - 5} bài khác." if total > 5 else ""
        return self._msg(
            f"Bạn có {total} bài đăng tìm gia sư:\n" + "\n".join(lines) + more,
            intent="posts",
            suggestions=["Bài đăng của tôi có gia sư nào ứng tuyển chưa?"],
        )

    async def _applications(self, token: str) -> Resolution:
        data = await self._backend.get_my_applications(token)
        if data is None:
            return self._msg(_ERROR_MSG, intent="applications")
        counts = data.get("counts") or {}
        total = counts.get("all", _total(data, len(data.get("applications") or [])))
        if not total:
            return self._msg(
                "Bạn chưa ứng tuyển lớp nào. Vào trang Lớp học để tìm lớp phù hợp nhé.",
                intent="applications",
                suggestions=["Có lớp nào đang cần gia sư không?"],
            )
        detail = []
        for key, label in (
            ("pending", "đang chờ"),
            ("selected", "được chọn"),
            ("approved", "đã nhận lớp"),
        ):
            if counts.get(key):
                detail.append(f"{counts[key]} {label}")
        tail = f" ({', '.join(detail)})" if detail else ""
        return self._msg(
            f"Bạn đã ứng tuyển {total} lớp{tail}. Xem chi tiết ở trang Đơn ứng tuyển của tôi nhé.",
            intent="applications",
        )

    async def _invitations(self, token: str) -> Resolution:
        data = await self._backend.get_my_invitations(token)
        if data is None:
            return self._msg(_ERROR_MSG, intent="invitations")
        invitations = data.get("invitations") or []
        total = _total(data, len(invitations))
        if not total:
            return self._msg(
                "Hiện bạn chưa có lời mời dạy nào đang chờ phản hồi.",
                intent="invitations",
            )
        return self._msg(
            f"Bạn có {total} lời mời dạy đang chờ phản hồi. "
            "Vào trang Lời mời để đồng ý hoặc từ chối nhé.",
            intent="invitations",
        )

    @staticmethod
    def _msg(answer: str, *, intent: str, suggestions: list[str] | None = None) -> Resolution:
        return Resolution(
            answer=answer,
            confidence=0.9,
            source=Source.MINE.value,
            intent=intent,
            suggestions=suggestions or [],
            cacheable=False,  # dữ liệu theo từng user + trạng thái đăng nhập → không cache
        )


def _total(data: dict, fallback: int) -> int:
    pagination = data.get("pagination")
    if isinstance(pagination, dict) and isinstance(pagination.get("totalItems"), int):
        return pagination["totalItems"]
    return fallback
