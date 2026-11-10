"""Download the original Qwen BF16 checkpoint to the ignored local folder."""
import argparse
from pathlib import Path
from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[2]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "models/pretrained/Qwen3-VL-8B-Instruct")
    parser.add_argument("--revision", default="1dd1e02d981403da25ed73d43430e4ef598cb94b")
    args = parser.parse_args()
    snapshot_download(repo_id="Qwen/Qwen3-VL-8B-Instruct", revision=args.revision,
                      local_dir=args.output.expanduser().resolve())
    print("模型文件:", args.output.expanduser().resolve())
