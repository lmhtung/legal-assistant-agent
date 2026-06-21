"""Prompt tối giản cho legal assistant."""
from __future__ import annotations

from src.schemas.legal import LegalArticle

SYSTEM_PROMPT = """Bạn là MscAI, trợ lý AI hỗ trợ tra cứu và giải thích pháp luật Việt Nam.

Nguyên tắc:
- Nếu người dùng trò chuyện thông thường, hãy trả lời tự nhiên, ngắn gọn bằng tiếng Việt.
- Nếu người dùng hỏi vấn đề pháp lý, chỉ kết luận dựa trên căn cứ pháp lý được cung cấp trong hội thoại hiện tại.
- Nếu chưa có căn cứ pháp lý phù hợp, nói rõ rằng bạn chưa có đủ dữ liệu để kết luận; không tự bịa điều luật, thủ tục, điều kiện hoặc mức phạt.
- Khi có căn cứ, nêu điều luật/văn bản liên quan trong câu trả lời.
"""

INTENT_PROMPT = """Bạn là bộ phân tích ý định cho legal RAG.

Nếu câu hỏi KHÔNG mang ý nghĩa pháp luật, quy định, thủ tục, quyền/nghĩa vụ, chế tài, hợp đồng, doanh nghiệp, lao động, bảo hiểm, thuế, đất đai, đấu thầu hoặc văn bản pháp luật: trả về đúng SKIP.
Nếu câu hỏi có liên quan pháp luật: trả về đúng NEXT.

Chỉ trả về SKIP hoặc NEXT. Không giải thích.

Câu hỏi: {question}
"""

REWRITE_QUERY_PROMPT = """Bạn là bộ viết lại truy vấn cho hệ thống tra cứu pháp luật Việt Nam.

Hãy viết lại câu hỏi thành một truy vấn pháp lý ngắn gọn, rõ ý, đúng thuật ngữ pháp luật, phù hợp để embedding/search.
Chỉ trả về truy vấn đã viết lại. Không giải thích.

Câu hỏi: {question}
"""

HYDE_PROMPT = """Bạn là bộ tạo hypothetical answer cho hệ thống tra cứu pháp luật Việt Nam.

Hãy viết một đoạn trả lời giả định ngắn bằng tiếng Việt, chứa các thuật ngữ pháp lý có khả năng xuất hiện trong điều luật/văn bản liên quan. Đoạn này chỉ dùng để embedding/search, không phải câu trả lời cuối cùng cho người dùng.
Chỉ trả về đoạn hypothetical answer. Không giải thích.

Câu hỏi: {question}
"""

CATEGORY_PROMPT = """Bạn là bộ phân loại category luật cho legal RAG.

Dựa trên câu hỏi/truy vấn, chọn các category pháp luật liên quan nhất từ danh sách cho sẵn. Chỉ chọn category có trong danh sách.
Trả về JSON array, ví dụ: ["luat_dau_thau", "luat_ho_tro_doanh_nghiep_vua_va_nho"].
Nếu không chắc, trả về tối đa 3 category có khả năng liên quan nhất.

Danh sách category:
{categories}

Truy vấn: {query}
"""


def build_intent_prompt(question: str) -> str:
    return INTENT_PROMPT.format(question=question)


def build_rewrite_query_prompt(question: str) -> str:
    return REWRITE_QUERY_PROMPT.format(question=question)


def build_hyde_prompt(question: str) -> str:
    return HYDE_PROMPT.format(question=question)


def build_category_prompt(query: str, categories: list[str]) -> str:
    values = "\n".join(f"- {item}" for item in categories)
    return CATEGORY_PROMPT.format(query=query, categories=values)


def format_article_context(articles: list[LegalArticle]) -> str:
    """Đổi danh sách điều luật thành context nội bộ đưa vào lượt trả lời."""

    if not articles:
        return "Không tìm thấy căn cứ pháp lý phù hợp trong kho dữ liệu đã đăng ký."

    blocks: list[str] = []
    for index, article in enumerate(articles, start=1):
        title = f" - {article.article_title}" if article.article_title else ""
        category = f"Category: {article.category}" if article.category else "Category: default"
        author = f"Cơ quan ban hành: {article.author}" if article.author else "Cơ quan ban hành: N/A"
        related = ", ".join(sorted(article.extra)) if article.extra else "N/A"
        blocks.append(
            "\n".join(
                [
                    f"[{index}] {article.law_id}|{article.law_name}|{article.article}{title}",
                    f"Loại văn bản: {article.doc_type}",
                    category,
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
- Khi trả lời, trích dẫn theo metadata law_id, law_name, article.
"""
