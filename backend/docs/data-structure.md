# Data Structure

Dataset là các record pháp luật đã xử lý sẵn. Backend không xử lý raw PDF/OCR trong luồng chính.

## Record Chuẩn

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
  "extra": [
    "Nghị định|44/2013/NĐ-CP|Quy định chi tiết thi hành một số điều của Bộ luật lao động về hợp đồng lao động|Điều 2"
  ]
}
```

## Field `extra`

`extra` là tập/danh sách các điều luật liên quan đến record hiện tại.

Format từng phần tử:

```text
doc_type|law_id|law_name|article
```

Ví dụ:

```text
Nghị định|44/2013/NĐ-CP|Quy định chi tiết thi hành một số điều của Bộ luật lao động về hợp đồng lao động|Điều 2
```

Khi retrieval tìm được `Điều 1`, agent sẽ:

1. thêm `Điều 1` vào `relevant_articles`;
2. đọc `extra` của `Điều 1`;
3. chuẩn hóa mỗi item thành `law_id|law_name|article`;
4. thêm các điều liên quan vào `relevant_articles` và `relevant_docs`.

Nhờ vậy phần nguồn liên quan được kiểm soát bằng data, không phụ thuộc LLM.

## Vector Text

Text dùng để embedding:

```text
{doc_type} {law_id} {law_name}
{article} {article_title}
{content}
```

Không đưa `extra` vào embedding vì `extra` là quan hệ pháp lý, không phải nội dung chính của điều luật.

## PostgreSQL

Bảng: `legal_knowledge_records`.

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
extra JSONB       -- JSON array các related refs
vector_text TEXT
updated_at TIMESTAMPTZ
```
