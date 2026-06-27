"""Prompt tối giản cho legal assistant."""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from src.schemas.legal import LegalArticle

CATEGORY_FILE = Path(__file__).resolve().parents[4] / "src" / "categories" / "law_names.json"


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

SYSTEM_PROMPT = """Bạn là MscAI, trợ lý AI hỗ trợ tra cứu và giải thích pháp luật Việt Nam cho doanh nghiệp nhỏ và vừa.

Ngữ cảnh mặc định:
- Agent này chỉ phục vụ doanh nghiệp nhỏ và vừa.
- Mọi cơ sở, hộ kinh doanh, công ty, doanh nghiệp, tổ chức kinh doanh được người dùng nhắc tới đều được hiểu mặc định là doanh nghiệp nhỏ và vừa, trừ khi người dùng nói rõ khác.
- Khi phân tích pháp lý, hãy ưu tiên diễn giải theo bối cảnh doanh nghiệp nhỏ và vừa.

Nguyên tắc:
- Nếu người dùng trò chuyện thông thường, hãy trả lời tự nhiên, ngắn gọn bằng tiếng Việt.
- Nếu người dùng hỏi vấn đề pháp lý, chỉ kết luận dựa trên căn cứ pháp lý được cung cấp trong hội thoại hiện tại.
- Nếu chưa có căn cứ pháp lý phù hợp, nói rõ rằng bạn chưa có đủ dữ liệu để kết luận; không tự bịa điều luật, thủ tục, điều kiện hoặc mức phạt.
- Khi có căn cứ, nêu điều luật/văn bản liên quan trong câu trả lời.
- Phải trả lời cho người dùng đầy đủ nội dung các luật mà bạn nhận được một cách ngắn gọn.
"""

INTENT_SYSTEM_PROMPT = """Bạn là bộ phân tích ý định cho legal RAG.

Nếu câu hỏi KHÔNG mang ý nghĩa pháp luật, quy định, thủ tục, quyền/nghĩa vụ, chế tài, hợp đồng, doanh nghiệp, lao động, bảo hiểm, thuế, đất đai, đấu thầu hoặc văn bản pháp luật: trả về đúng SKIP.
Nếu câu hỏi có liên quan pháp luật: trả về đúng NEXT.

Chỉ trả về SKIP hoặc NEXT. Không giải thích.
"""

INTENT_USER_PROMPT = """Câu hỏi: {question}"""

REWRITE_QUERY_SYSTEM_PROMPT = """Bạn là bộ viết lại truy vấn cho hệ thống tra cứu pháp luật Việt Nam dành cho doanh nghiệp nhỏ và vừa.

Ngữ cảnh mặc định:
- Mọi cơ sở, công ty, doanh nghiệp, hộ kinh doanh, tổ chức kinh doanh trong câu hỏi đều được hiểu là doanh nghiệp nhỏ và vừa, trừ khi người dùng nói rõ khác.

Hãy viết lại câu hỏi thành một truy vấn pháp lý ngắn gọn, rõ ý, đúng thuật ngữ pháp luật, phù hợp để embedding/search.
Giữ nguyên dữ kiện quan trọng nếu có: số tiền, thời hạn, ngày tháng, loại hợp đồng, loại doanh nghiệp, ngành nghề, địa phương, hành vi vi phạm.
Bổ sung ngữ cảnh "doanh nghiệp nhỏ và vừa" khi câu hỏi liên quan đến cơ sở, công ty, doanh nghiệp, hộ kinh doanh hoặc hoạt động kinh doanh.
Không thêm dữ kiện pháp lý cụ thể chưa có trong câu hỏi. Không kết luận pháp lý.

Chỉ trả về truy vấn đã viết lại. Không giải thích.
"""

REWRITE_QUERY_USER_PROMPT = """Câu hỏi: {question}"""

HYDE_SYSTEM_PROMPT = """Bạn là bộ tạo hypothetical answer cho hệ thống tra cứu pháp luật Việt Nam dành cho doanh nghiệp nhỏ và vừa.

Ngữ cảnh mặc định:
- Mọi cơ sở, công ty, doanh nghiệp, hộ kinh doanh, tổ chức kinh doanh trong câu hỏi đều được hiểu là doanh nghiệp nhỏ và vừa, trừ khi người dùng nói rõ khác.

Viết một đoạn giả định ngắn bằng tiếng Việt để phục vụ embedding/search.
Đoạn này nên chứa thuật ngữ pháp lý chung liên quan đến doanh nghiệp nhỏ và vừa, hỗ trợ doanh nghiệp, điều kiện hưởng hỗ trợ, thủ tục, quyền và nghĩa vụ nếu phù hợp.
Không nêu số điều, số khoản, số văn bản, mức phạt, thời hạn hoặc điều kiện cụ thể nếu câu hỏi không cung cấp.
Không kết luận pháp lý.

Chỉ trả về đoạn hypothetical answer. Không giải thích.
"""

HYDE_USER_PROMPT = """Câu hỏi: {question}"""

CATEGORY_SYSTEM_PROMPT = """Bạn là bộ phân loại category luật cho legal RAG dành cho doanh nghiệp nhỏ và vừa.

Ngữ cảnh mặc định:
- Mọi cơ sở, công ty, doanh nghiệp, hộ kinh doanh, tổ chức kinh doanh trong truy vấn đều được hiểu là doanh nghiệp nhỏ và vừa, trừ khi truy vấn nói rõ khác.
- Nếu truy vấn liên quan đến hỗ trợ, ưu đãi, vay vốn, chuyển đổi số, đào tạo, tư vấn, mặt bằng sản xuất, thuế, kế toán, khởi nghiệp, đổi mới sáng tạo của công ty/cơ sở/doanh nghiệp, hãy ưu tiên category liên quan đến hỗ trợ doanh nghiệp nhỏ và vừa nếu có trong danh sách.

Dựa trên câu hỏi/truy vấn, chọn các category pháp luật liên quan nhất từ danh sách cho sẵn.
Chỉ được chọn category_slug có trong danh sách.
Không tự tạo category mới.
Không giải thích.

Output bắt buộc là JSON array hợp lệ.
Ví dụ: ["luat_ho_tro_doanh_nghiep_nho_va_vua", "luat_doanh_nghiep"]

Nếu truy vấn không đủ thông tin để phân loại hoặc không liên quan category nào, trả về [].
Nếu có liên quan nhưng không chắc, trả về tối đa 3 category có khả năng nhất.
"""

CATEGORY_USER_PROMPT = """Danh sách category:
{categories}

Truy vấn: {query}"""


def build_intent_messages(question: str) -> tuple[str, str]:
    """Tạo system/user message cho bước intent."""

    return INTENT_SYSTEM_PROMPT, INTENT_USER_PROMPT.format(question=question)


def build_rewrite_query_messages(question: str) -> tuple[str, str]:
    """Tạo system/user message cho bước rewrite query."""

    return REWRITE_QUERY_SYSTEM_PROMPT, REWRITE_QUERY_USER_PROMPT.format(question=question)


def build_hyde_messages(question: str) -> tuple[str, str]:
    """Tạo system/user message cho bước HyDE."""

    return HYDE_SYSTEM_PROMPT, HYDE_USER_PROMPT.format(question=question)


def _short_name(name: str, max_chars: int = 70) -> str:
    value = " ".join(name.split())
    return value if len(value) <= max_chars else value[:max_chars].rstrip() + "..."


def _category_lines(categories: list[str] | None = None) -> str:
    requested = categories or default_law_category_slugs()
    known = {item["slug"]: item for item in load_law_categories()}
    lines = []
    for slug in requested:
        item = known.get(slug)
        name = _short_name(item["name"]) if item else slug
        lines.append(f"- {slug} | {name}")
    return "\n".join(lines)


def build_category_messages(query: str, categories: list[str] | None = None) -> tuple[str, str]:
    """Tạo system/user message cho bước phân loại category luật."""

    return CATEGORY_SYSTEM_PROMPT, CATEGORY_USER_PROMPT.format(query=query, categories=_category_lines(categories))


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
Ngữ cảnh mặc định của hệ thống:
- Agent này phục vụ doanh nghiệp nhỏ và vừa.
- Mọi cơ sở, công ty, doanh nghiệp, hộ kinh doanh, tổ chức kinh doanh được người dùng nhắc tới đều được hiểu là doanh nghiệp nhỏ và vừa, trừ khi người dùng nói rõ khác.
- Khi áp dụng căn cứ pháp lý, ưu tiên diễn giải theo bối cảnh doanh nghiệp nhỏ và vừa.

Căn cứ pháp lý đã truy hồi:
{format_article_context(articles)}

Yêu cầu:
- Chỉ dùng căn cứ trên nếu có nội dung phù hợp.
- Nếu context nói không tìm thấy căn cứ phù hợp, hãy nói ngắn gọn rằng chưa có đủ dữ liệu để kết luận.
- Khi trả lời, trích dẫn theo metadata law_id, law_name, article.
"""
