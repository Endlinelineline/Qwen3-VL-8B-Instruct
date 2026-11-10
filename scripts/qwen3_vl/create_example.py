"""Create an example input workbook without overwriting user data."""
from pathlib import Path
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[2]
path = ROOT / "data" / "example_input.xlsx"
path.parent.mkdir(parents=True, exist_ok=True)
if path.exists():
    raise SystemExit(f"文件已存在，不覆盖: {path}")
book = Workbook()
sheet = book.active
sheet.title = "requests"
sheet.append(["prompt", "model", "image_path"])
sheet.append(["请用一句话解释什么是人工智能。", "Qwen3-VL-8B-Instruct", None])
sheet.append(["请描述图片中看到了什么。", "Qwen3-VL-8B-Instruct", "example.jpg"])
sheet.freeze_panes = "A2"
book.save(path)
print(f"已创建 {path}；如需图文测试，将本地图片保存为 data/example.jpg")
