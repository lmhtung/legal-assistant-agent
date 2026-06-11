# Data Structure

Đây là hợp đồng dữ liệu mà hệ thống data bên ngoài cần cung cấp cho vector store. Backend agent không import, không sửa và không quản lý dataset.

## Record Chuẩn

```json
{
  "id": "44_2013_ND_CP_Dieu_1",
  "law_id": "44/2013/NĐ-CP",
  "law_name": "Quy định chi tiết thi hành một số điều của Bộ luật lao động về hợp đồng lao động",
  "doc_type": "Nghị định",
  "database": "labor",
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

## Text Nên Được Embedding

Vector index bên ngoài nên embedding text theo format:

```text
{doc_type} {law_id} {law_name}
{article} {article_title}
{content}
```

Không nên đưa `extra` vào embedding vì `extra` là quan hệ pháp lý để mở rộng nguồn sau retrieval, không phải nội dung chính của điều luật.

## Field `extra`

`extra` là tập/danh sách các điều luật liên quan đến record hiện tại.

Format từng phần tử:

```text
doc_type|law_id|law_name|article
```

Khi retrieval tìm được `Điều 1`, agent sẽ:

1. thêm `Điều 1` vào `relevant_articles`;
2. đọc `extra` của `Điều 1`;
3. chuẩn hóa mỗi item thành `law_id|law_name|article`;
4. thêm các điều liên quan vào `relevant_articles` và `relevant_docs`.

Nhờ vậy phần nguồn liên quan được kiểm soát bằng data, không phụ thuộc LLM.

## Metadata Vector Store Cần Có

Để agent dựng lại `LegalArticle`, mỗi hit từ vector store cần có metadata tối thiểu:

```text
id
law_id
law_name
doc_type
database
chapter
article
article_title
content
author
extra
```
