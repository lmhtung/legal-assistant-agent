# Data Structure

Tài liệu này mô tả cấu trúc dataset tri thức pháp luật mà backend sử dụng.

## Record Chuẩn

Mỗi record tương ứng một điều/khoản/mục pháp luật đã được xử lý sẵn.

```json
{
  "id": "44_2013_ND_CP_Dieu_1",
  "law_id": "44/2013/NĐ-CP",
  "law_name": "Quy định chi tiết thi hành một số điều của Bộ luật lao động về hợp đồng lao động",
  "doc_type": "Nghị định",
  "chapter": "Chương I NHỮNG QUY ĐỊNH CHUNG",
  "article": "Điều 1",
  "article_title": "Phạm vi điều chỉnh",
  "content": "Nghị định này quy định chi tiết thi hành một số điều của Bộ luật lao động về hợp đồng lao động.",
  "author": "Chính phủ",
  "extra": {}
}
```

## Ý Nghĩa Field

| Field | Bắt buộc | Mô tả |
|---|---:|---|
| `id` | Có | ID ổn định của record, dùng làm primary key PostgreSQL và vector id. |
| `law_id` | Có | Mã văn bản pháp luật, ví dụ `44/2013/NĐ-CP`. |
| `law_name` | Có | Tên/trích yếu văn bản. |
| `doc_type` | Có | Loại văn bản, ví dụ `Luật`, `Nghị định`, `Thông tư`. |
| `chapter` | Không | Chương/phần/mục lớn nếu có. |
| `article` | Có | Điều/khoản/mục chính, ví dụ `Điều 1`. |
| `article_title` | Không | Tiêu đề điều. |
| `content` | Có | Nội dung pháp luật đã làm sạch. |
| `author` | Không | Cơ quan ban hành, ví dụ `Quốc hội`, `Chính phủ`. |
| `extra` | Không | Metadata mở rộng. |

## Vector Text

Backend không embed JSON thô. Nó build text chuẩn:

```text
{doc_type} {law_id} {law_name}
{article} {article_title}
{content}
```

Ví dụ:

```text
Nghị định 44/2013/NĐ-CP Quy định chi tiết thi hành một số điều của Bộ luật lao động về hợp đồng lao động
Điều 1 Phạm vi điều chỉnh
Nghị định này quy định chi tiết thi hành một số điều của Bộ luật lao động về hợp đồng lao động.
```

## Lưu Trữ PostgreSQL

Bảng mặc định: `legal_knowledge_records`.

Các cột chính:

```text
id TEXT PRIMARY KEY
law_id TEXT
law_name TEXT
doc_type TEXT
chapter TEXT
article TEXT
article_title TEXT
content TEXT
author TEXT
extra JSONB
vector_text TEXT
updated_at TIMESTAMPTZ
```

## Output Cuộc Thi

Từ record, backend sinh reference theo format:

```text
relevant_docs: law_id|law_name
relevant_articles: law_id|law_name|article
```

Ví dụ:

```json
{
  "relevant_docs": [
    "44/2013/NĐ-CP|Quy định chi tiết thi hành một số điều của Bộ luật lao động về hợp đồng lao động"
  ],
  "relevant_articles": [
    "44/2013/NĐ-CP|Quy định chi tiết thi hành một số điều của Bộ luật lao động về hợp đồng lao động|Điều 1"
  ]
}
```
