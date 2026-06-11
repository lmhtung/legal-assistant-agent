"""Prompt builders for query preparation and grounded answer generation."""
from __future__ import annotations

from src.schemas.legal import LegalArticle

SYSTEM_PROMPT = """Bạn là trợ lý pháp lý AI cho doanh nghiệp SME tại Việt Nam.
Chỉ trả lời dựa trên các điều luật được cung cấp. Nếu căn cứ chưa đủ, hãy nói rõ giới hạn.
Luôn viết tiếng Việt rõ ràng, ngắn gọn, có dẫn nguồn Điều X trong câu trả lời.
"""

QUERY_REWRITE_PROMPT = """Bạn là bộ phận tối ưu truy vấn cho hệ thống truy hồi văn bản pháp luật Việt Nam.
Viết lại câu hỏi sau thành một truy vấn tìm kiếm ngắn gọn, giữ nguyên ý pháp lý chính, bổ sung từ khóa pháp luật quan trọng nếu có.
Không trả lời câu hỏi. Chỉ trả về truy vấn đã viết lại.

Câu hỏi: {question}
Truy vấn tối ưu:"""

HYPOTHETICAL_ANSWER_PROMPT = """Bạn là trợ lý pháp lý. Hãy viết một đoạn trả lời ngắn, súc tích, có các thuật ngữ pháp lý có khả năng xuất hiện trong văn bản luật liên quan.
Không cần trích nguồn, không cần chắc chắn đúng hoàn toàn. Mục tiêu là tạo đoạn văn giàu ngữ nghĩa để embedding và truy hồi.

Câu hỏi: {question}
Đoạn trả lời ngắn:"""


def format_article_context(articles: list[LegalArticle]) -> str:
    blocks: list[str] = []
    for index, article in enumerate(articles, start=1):
        title = f" - {article.article_title}" if article.article_title else ""
        chapter = f"Chương: {article.chapter}" if article.chapter else "Chương: N/A"
        author = f"Cơ quan ban hành: {article.author}" if article.author else "Cơ quan ban hành: N/A"
        blocks.append(
            "\n".join(
                [
                    f"[{index}] {article.law_id}|{article.law_name}|{article.article}{title}",
                    f"Loại văn bản: {article.doc_type}",
                    chapter,
                    author,
                    article.content.strip(),
                ]
            )
        )
    return "\n\n".join(blocks)


def build_query_rewrite_prompt(question: str) -> str:
    return QUERY_REWRITE_PROMPT.format(question=question)


def build_hypothetical_answer_prompt(question: str) -> str:
    return HYPOTHETICAL_ANSWER_PROMPT.format(question=question)


def build_grounded_answer_prompt(question: str, articles: list[LegalArticle]) -> str:
    context = format_article_context(articles)
    return f"""{SYSTEM_PROMPT}

Câu hỏi:
{question}

Căn cứ pháp lý đã truy hồi:
{context if context else "Không có căn cứ pháp lý phù hợp."}

Yêu cầu trả lời:
- Nếu có căn cứ, trả lời trực tiếp và nêu rõ Điều X, tên văn bản liên quan.
- Không bịa thêm điều luật ngoài danh sách căn cứ.
- Kết thúc bằng cảnh báo ngắn: đây là thông tin tham khảo, nên hỏi chuyên gia khi vụ việc có rủi ro cao.
"""
