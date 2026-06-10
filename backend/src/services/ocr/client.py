import subprocess
from pathlib import Path
from src.config import settings


class MinerUClient:
    def __init__(self, output_dir: str | None = None):
        self.output_dir = Path(output_dir or settings.mineru.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def parse_to_markdown(self, input_path: str) -> Path:
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file: {input_path}")

        out_dir = self.output_dir / input_path.stem
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            "mineru",
            "-p",
            str(input_path),
            "-o",
            str(out_dir),
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"MinerU failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

        markdown_files = list(out_dir.rglob("*.md"))
        if not markdown_files:
            raise RuntimeError(f"Không tìm thấy markdown output trong {out_dir}")

        return markdown_files[0]