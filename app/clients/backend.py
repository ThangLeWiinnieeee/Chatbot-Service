"""Client gọi NGƯỢC về API của WebTutorCenter backend (Node/Express).

Dùng cho `data` resolver: lấy dữ liệu sống (danh sách môn, số lượng gia sư…).
KHÔNG nối thẳng MongoDB → giữ chatbot generic + là nền cho AI tool-use sau này.

Mọi lỗi mạng/BE đều nuốt và trả None → resolver rơi xuống AI, không làm sập chat.
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class BackendClient:
    def __init__(self, base_url: str, *, secret: str = "", timeout: float = 15.0) -> None:
        # httpx merge base_url + relative path chuẩn RFC khi base_url kết thúc bằng "/".
        normalized = base_url.rstrip("/") + "/"
        headers = {"X-Internal-Secret": secret} if secret else {}
        self._client = httpx.AsyncClient(base_url=normalized, timeout=timeout, headers=headers)

    async def _get_data(self, path: str, params: dict | None = None):
        """GET rồi bóc `data` trong response chuẩn `{ success, message, data }`."""
        try:
            resp = await self._client.get(path, params=params)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001 - chủ đích nuốt mọi lỗi
            logger.warning("Backend GET %s failed: %s", path, exc)
            return None
        if isinstance(payload, dict):
            return payload.get("data")
        return None

    async def _get_data_auth(self, path: str, token: str, params: dict | None = None):
        """Như `_get_data` nhưng kèm Bearer token của người dùng cuối.

        Dùng cho endpoint cá nhân (BE yêu cầu authMiddleware). 401/403/lỗi mạng
        → None; resolver tự quyết định (báo đăng nhập / xin lỗi), KHÔNG rơi xuống
        AI để tránh bịa dữ liệu riêng tư của user.
        """
        try:
            resp = await self._client.get(
                path, params=params, headers={"Authorization": f"Bearer {token}"}
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001 - chủ đích nuốt mọi lỗi
            logger.warning("Backend GET %s (auth) failed: %s", path, exc)
            return None
        if isinstance(payload, dict):
            return payload.get("data")
        return None

    async def get_my_profile(self, token: str) -> dict | None:
        """GET /users/user-info → hồ sơ người dùng đang đăng nhập."""
        data = await self._get_data_auth("users/user-info", token)
        if isinstance(data, dict):
            user = data.get("user")
            if isinstance(user, dict):
                return user
        return None

    async def get_my_posts(self, token: str) -> dict | None:
        """GET /classes/my-posts → `{ classes: [...], pagination }` của người đăng."""
        data = await self._get_data_auth("classes/my-posts", token)
        return data if isinstance(data, dict) else None

    async def get_my_applications(self, token: str) -> dict | None:
        """GET /classes/mine → `{ applications, counts, pagination }` (gia sư)."""
        data = await self._get_data_auth("classes/mine", token)
        return data if isinstance(data, dict) else None

    async def get_my_invitations(self, token: str) -> dict | None:
        """GET /classes/invitations → `{ invitations, pagination }` (gia sư)."""
        data = await self._get_data_auth("classes/invitations", token)
        return data if isinstance(data, dict) else None

    async def get_subjects(self) -> list[str] | None:
        """GET /subjects → danh sách tên môn đang bật."""
        data = await self._get_data("subjects")
        if isinstance(data, dict):
            subjects = data.get("subjects")
            if isinstance(subjects, list):
                return [str(s) for s in subjects]
        return None

    async def search_tutors(
        self, *, subject: str | None = None, name: str | None = None, limit: int = 3
    ) -> dict | None:
        """GET /tutors/search → `{ tutors: [...], total: N }` (đã bóc `data`)."""
        params: dict[str, object] = {"page": 1, "limit": limit}
        if subject:
            params["subject"] = subject
        if name:
            params["name"] = name
        data = await self._get_data("tutors/search", params=params)
        return data if isinstance(data, dict) else None

    async def aclose(self) -> None:
        await self._client.aclose()
