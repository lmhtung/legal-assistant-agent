"""Prompt tối giản cho legal assistant."""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from src.schemas.legal import LegalArticle

CATEGORY_FILE = Path(__file__).resolve().parents[4] / "src" /"categories" / "law_names.json"


def slugify_law_name(name: str) -> str:
    """Chuyển tên luật tiếng Việt thành category slug ổn định."""

    value = unicodedata.normalize("NFD", name.lower())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = value.replace("đ", "d")
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "default"


def describe_law_category(name: str) -> str:
    """Tạo mô tả ngắn khoảng 15 từ cho từng category luật."""

    return f"Nhóm quy định về {name.lower()}, gồm phạm vi áp dụng, thủ tục, quyền và nghĩa vụ."


@lru_cache(maxsize=1)
def load_law_categories() -> list[dict[str, str]]:
    """Đọc law_names.json và tạo category slug + mô tả cho prompt phân loại."""

    try:
        names = json.loads(CATEGORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        names = []
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for name in names:
        if not isinstance(name, str) or not name.strip():
            continue
        slug = slugify_law_name(name)
        if slug in seen:
            continue
        seen.add(slug)
        output.append({"slug": slug, "name": name.strip(), "description": describe_law_category(name.strip())})
    return output


def default_law_category_slugs() -> list[str]:
    """Danh sách category mặc định sinh từ backend/categories/law_names.json."""

    return [item["slug"] for item in load_law_categories()]

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
Mỗi dòng gồm: category_slug | tên luật | mô tả ngắn. Chỉ trả về category_slug.
Trả về JSON array, ví dụ: ["luat_dau_thau", "luat_ho_tro_doanh_nghiep_nho_va_vua"].
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


def build_category_prompt(query: str, categories: list[str] | None = None) -> str:
    requested = categories or default_law_category_slugs()
    known = {item["slug"]: item for item in load_law_categories()}
    lines: list[str] = []
    for slug in requested:
        item = known.get(slug)
        if item:
            lines.append(f"- {item['slug']} | {item['name']} | {item['description']}")
        else:
            lines.append(f"- {slug} | {slug} | Nhóm quy định pháp luật liên quan trực tiếp đến chủ đề {slug}.")
    values = "\n".join(lines)
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
