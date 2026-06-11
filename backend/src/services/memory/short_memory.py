"""Short-memory theo session_id cho endpoint chat.

Store này chỉ lưu trong RAM của một backend process. Mục tiêu là giúp agent hiểu
những câu nối tiếp như "vậy trường hợp đó thì sao?" trong cùng một phiên chat.
"""
from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock

from src.schemas.legal import ChatHistoryMessage


class ShortMemoryStore:
    """Bộ nhớ ngắn hạn dạng vòng tròn theo session_id."""

    def __init__(self, max_turns: int = 6, max_chars: int = 4000) -> None:
        self.max_turns = max_turns
        self.max_messages = max_turns * 2
        self.max_chars = max_chars
        self._items: dict[str, deque[ChatHistoryMessage]] = defaultdict(lambda: deque(maxlen=self.max_messages))
        self._lock = Lock()

    def get(self, session_id: str | None) -> list[ChatHistoryMessage]:
        """Lấy history đã cắt ngắn cho một session."""

        if not session_id:
            return []
        with self._lock:
            messages = list(self._items.get(session_id, []))
        return self._trim_chars(messages)

    def append_turn(self, session_id: str | None, user_message: str, assistant_message: str) -> None:
        """Thêm một lượt user/assistant vào memory."""

        if not session_id:
            return
        with self._lock:
            bucket = self._items[session_id]
            bucket.append(ChatHistoryMessage(role="user", content=user_message))
            bucket.append(ChatHistoryMessage(role="assistant", content=assistant_message))

    def clear(self, session_id: str | None) -> None:
        """Xóa memory của một session, dùng khi UI muốn bắt đầu lại."""

        if not session_id:
            return
        with self._lock:
            self._items.pop(session_id, None)

    def _trim_chars(self, messages: list[ChatHistoryMessage]) -> list[ChatHistoryMessage]:
        """Giữ các message mới nhất sao cho tổng độ dài không vượt max_chars."""

        selected: list[ChatHistoryMessage] = []
        total = 0
        for message in reversed(messages):
            total += len(message.content)
            if total > self.max_chars and selected:
                break
            selected.append(message)
        return list(reversed(selected))
