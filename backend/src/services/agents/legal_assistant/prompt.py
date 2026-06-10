from __future__ import annotations

from src.schemas.legal import LegalArticle

SYSTEM_PROMPT = """Ban la tro ly phap ly AI cho doanh nghiep SME tai Viet Nam.
Chi tra loi dua tren cac dieu luat duoc cung cap. Neu can cu chua du, hay noi ro gioi han.
Luon viet tieng Viet ro rang, ngan gon, co dan nguon Dieu X trong cau tra loi.
"""


def format_article_context(articles: list[LegalArticle]) -> str:
    blocks: list[str] = []
    for index, article in enumerate(articles, start=1):
        title = f" - {article.article_title}" if article.article_title else ""
        blocks.append(
            "\n".join(
                [
                    f"[{index}] {article.law_id}|{article.law_name}|{article.article}{title}",
                    article.content.strip(),
                ]
            )
        )
    return "\n\n".join(blocks)


def build_grounded_answer_prompt(question: str, articles: list[LegalArticle]) -> str:
    context = format_article_context(articles)
    return f"""{SYSTEM_PROMPT}

Cau hoi:
{question}

Can cu phap ly da truy hoi:
{context if context else "Khong co can cu phap ly phu hop."}

Yeu cau tra loi:
- Neu co can cu, tra loi truc tiep va neu ro Dieu X, ten van ban lien quan.
- Khong bia them dieu luat ngoai danh sach can cu.
- Ket thuc bang canh bao ngan: day la thong tin tham khao, nen hoi chuyen gia khi vu viec co rui ro cao.
"""
