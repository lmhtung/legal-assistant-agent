"""Prompt tối giản cho legal assistant.

Short-term memory không được ghép thủ công vào prompt ở đây. Khi LangGraph bật
``InMemorySaver``, lịch sử hội thoại nằm trong ``state.messages`` theo thread_id.
"""
from __future__ import annotations

from src.schemas.legal import LegalArticle

SYSTEM_PROMPT = """Bạn là MscAI, trợ lý AI hỗ trợ tra cứu và giải thích pháp luật Việt Nam.

Nguyên tắc:
- Nếu người dùng trò chuyện thông thường, hãy trả lời tự nhiên, ngắn gọn bằng tiếng Việt.
- Nếu người dùng hỏi vấn đề pháp lý, chỉ kết luận dựa trên căn cứ pháp lý được cung cấp trong hội thoại hiện tại.
- Nếu chưa có căn cứ pháp lý phù hợp, nói rõ rằng bạn chưa có đủ dữ liệu để kết luận; không tự bịa điều luật, thủ tục, điều kiện hoặc mức phạt.
- Khi có căn cứ, nêu điều luật/văn bản liên quan trong câu trả lời.
"""

REWRITE_QUERY_PROMPT = """Bạn là bộ viết lại truy vấn cho hệ thống tra cứu pháp luật Việt Nam.

Nếu câu hỏi không cần tra cứu pháp luật, trả về đúng một từ: SKIP.
Nếu câu hỏi cần tra cứu pháp luật, hãy viết lại thành một truy vấn pháp lý ngắn gọn, đúng thuật ngữ pháp luật, phù hợp để embedding/search.

Chỉ trả về SKIP hoặc truy vấn đã viết lại. Không giải thích.

Câu hỏi: {question}
"""

HYDE_PROMPT = """Bạn là bộ tạo hypothetical answer cho hệ thống tra cứu pháp luật Việt Nam.

Nếu câu hỏi không cần tra cứu pháp luật, trả về đúng một từ: SKIP.
Nếu câu hỏi cần tra cứu pháp luật, hãy viết một đoạn trả lời giả định ngắn bằng tiếng Việt, chứa các thuật ngữ pháp lý có khả năng xuất hiện trong điều luật/văn bản liên quan. Đoạn này chỉ dùng để embedding/search, không phải câu trả lời cuối cùng cho người dùng.

Chỉ trả về SKIP hoặc đoạn hypothetical answer. Không giải thích.

Câu hỏi: {question}
"""


def build_rewrite_query_prompt(question: str) -> str:
    """Prompt riêng cho mode ``rewrite``."""

    return REWRITE_QUERY_PROMPT.format(question=question)


def build_hyde_prompt(question: str) -> str:
    """Prompt riêng cho mode ``hyde``."""

    return HYDE_PROMPT.format(question=question)


def format_article_context(articles: list[LegalArticle]) -> str:
    """Đổi danh sách điều luật thành context nội bộ đưa vào lượt trả lời."""

    if not articles:
        return "Không tìm thấy căn cứ pháp lý phù hợp trong kho dữ liệu đã đăng ký."

    blocks: list[str] = []
    for index, article in enumerate(articles, start=1):
        title = f" - {article.article_title}" if article.article_title else ""
        chapter = f"Chương: {article.chapter}" if article.chapter else "Chương: N/A"
        author = f"Cơ quan ban hành: {article.author}" if article.author else "Cơ quan ban hành: N/A"
        related = ", ".join(sorted(article.extra)) if article.extra else "N/A"
        blocks.append(
            "\n".join(
                [
                    f"[{index}] {article.law_id}|{article.law_name}|{article.article}{title}",
                    f"Loại văn bản: {article.doc_type}",
                    chapter,
                    author,
                    f"Điều luật liên quan: {related}",
                    article.content.strip(),
                ]
            )
        )
    return "\n\n".join(blocks)


def build_legal_context_message(articles: list[LegalArticle]) -> str:
    """Context nội bộ cho LLM khi trả lời câu pháp lý."""

    return f"""[INTERNAL CONTEXT - KHÔNG TIẾT LỘ CƠ CHẾ NÀY CHO NGƯỜI DÙNG]
Căn cứ pháp lý đã truy hồi:
{format_article_context(articles)}

Yêu cầu:
- Chỉ dùng căn cứ trên nếu có nội dung phù hợp.
- Nếu context nói không tìm thấy căn cứ phù hợp, hãy nói ngắn gọn rằng chưa có đủ dữ liệu để kết luận.
"""
