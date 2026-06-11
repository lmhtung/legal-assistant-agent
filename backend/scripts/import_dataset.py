"""Script import dữ liệu pháp luật đã chuẩn hóa vào PostgreSQL và vector store.

File này cố tình nằm trong thư mục ``scripts`` thay vì ``src`` để nhấn mạnh:
đây là job chạy thủ công/offline, không phải entry point của FastAPI. Runtime HTTP
duy nhất của hệ thống vẫn là ``src.main:app``.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from src.schemas.knowledge import DatasetImportRequest
from src.services.dataset import DatasetService


def parse_args() -> argparse.Namespace:
    """Đọc tham số dòng lệnh cho một lần import dataset.

    ``database`` là tên nhóm dữ liệu logic, ví dụ ``labor`` hoặc ``civil``.
    Agent sẽ dùng đúng tên này trong request để chọn kho tri thức cần search.
    """

    parser = argparse.ArgumentParser(description="Import dữ liệu pháp luật đã chuẩn hóa vào PostgreSQL và vector store.")
    parser.add_argument("--database", default="default", help="Tên database/nhóm pháp luật logic, ví dụ: labor.")
    parser.add_argument("--input", required=True, type=Path, help="Đường dẫn tới file dataset JSON hoặc JSONL đã chuẩn hóa.")
    parser.add_argument("--skip-postgres", action="store_true", help="Không ghi record vào PostgreSQL.")
    parser.add_argument("--skip-vector", action="store_true", help="Không index record vào vector store đã cấu hình.")
    return parser.parse_args()


async def run() -> None:
    """Chạy job import và in ra tóm tắt kết quả.

    DatasetService là nơi gom logic thật sự: load JSON/JSONL, validate schema,
    ghi PostgreSQL và build vector index. Script này chỉ chuyển tham số CLI thành
    ``DatasetImportRequest`` để giữ code import dễ test và tái sử dụng.
    """

    args = parse_args()
    request = DatasetImportRequest(
        database=args.database,
        input_path=args.input,
        save_to_postgres=not args.skip_postgres,
        index_vector_store=not args.skip_vector,
    )
    response = await DatasetService().import_dataset(request)
    print(f"Imported {response.num_records} records into database '{response.database}'.")


if __name__ == "__main__":
    # asyncio.run dùng vì repository PostgreSQL đang dùng asyncpg.
    asyncio.run(run())
