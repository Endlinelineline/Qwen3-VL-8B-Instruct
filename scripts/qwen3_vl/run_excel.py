"""Run each Excel row, persisting measurement stages immediately."""
import argparse
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook, load_workbook

ROOT = Path(__file__).resolve().parents[2]
MODEL_NAME = "Qwen3-VL-8B-Instruct"
HEADERS = ["prompt", "model", "image_path", "开始时间戳_UTC", "结束时间戳_UTC",
           "推理耗时_秒", "输入token数量", "输出token数量", "生成答案", "状态", "错误信息", "TTFT_ms"]


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def cell_text(value):
    # Force Excel text cells to be literal even for untrusted prompt/model output.
    value = str(value)
    return "'" + value if value.startswith(("=", "+", "-", "@")) else value


def read_requests(path):
    book = load_workbook(path, read_only=True, data_only=False)
    try:
        rows = book.active.iter_rows(values_only=True)
        header = next(rows, None)
        if not header:
            raise ValueError("输入 Excel 为空")
        names = [str(x).strip() if x is not None else "" for x in header]
        if len(set(x for x in names if x)) != len([x for x in names if x]):
            raise ValueError("输入 Excel 的列名不能重复")
        if not {"prompt", "model"}.issubset(names):
            raise ValueError("首行必须包含 prompt 和 model 列；image_path 可选")
        for row_number, row in enumerate(rows, 2):
            data = dict(zip(names, row))
            if all(v is None for v in row):
                continue
            prompt, model = data.get("prompt"), data.get("model")
            if not isinstance(prompt, str) or not prompt.strip() or prompt.startswith("="):
                raise ValueError(f"第 {row_number} 行 prompt 必须为非空纯文本")
            if model not in (MODEL_NAME, "Qwen/" + MODEL_NAME):
                raise ValueError(f"第 {row_number} 行 model 必须是 {MODEL_NAME}")
            image = data.get("image_path")
            image_path = None
            if image:
                image_path = Path(str(image)).expanduser()
                if not image_path.is_absolute():
                    image_path = path.parent / image_path
                image_path = image_path.resolve()
                if not image_path.is_file():
                    raise ValueError(f"第 {row_number} 行图片不存在: {image_path}")
            yield prompt, str(model), image_path
    finally:
        book.close()


def save_atomic(book, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".qwen_", suffix=".xlsx", dir=destination.parent)
    os.close(fd)
    try:
        book.save(tmp)
        os.replace(tmp, destination)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def run_requests(requests, runner, destination, max_new_tokens=256):
    if destination.exists():
        raise FileExistsError(f"输出文件已存在，避免覆盖: {destination}")
    book = Workbook()
    sheet = book.active
    sheet.title = "inference_results"
    sheet.append(HEADERS)
    sheet.freeze_panes = "A2"
    save_atomic(book, destination)
    failures = 0
    for prompt, model, image_path in requests:
        sheet.append([cell_text(prompt), cell_text(model), cell_text(image_path) if image_path else None])
        row = sheet.max_row
        started = time.perf_counter()
        sheet.cell(row, 4, utc_now())
        sheet.cell(row, 10, "running")
        save_atomic(book, destination)  # 开始时间立即写入 Excel

        def on_input_tokens(count):
            sheet.cell(row, 7, count)
            save_atomic(book, destination)  # 输入 token 数量立即写入 Excel

        def on_first_token():
            first_token_time = time.perf_counter()
            sheet.cell(row, 12, round((first_token_time - started) * 1000, 3))
            save_atomic(book, destination)  # 首个输出 token 到达时立即写入 TTFT（毫秒）

        def on_generated(count):
            finished = time.perf_counter()
            sheet.cell(row, 5, utc_now())
            sheet.cell(row, 6, round(finished - started, 6))
            sheet.cell(row, 8, count)
            sheet.cell(row, 10, "generated")
            save_atomic(book, destination)  # 结束时间、耗时和输出 token 立即写入 Excel

        try:
            answer = runner.infer(prompt, image_path, max_new_tokens, on_input_tokens, on_first_token, on_generated)
            sheet.cell(row, 9, cell_text(answer))
            sheet.cell(row, 10, "success")
        except Exception as exc:
            failures += 1
            sheet.cell(row, 10, "failed")
            sheet.cell(row, 11, cell_text(f"{type(exc).__name__}: {exc}"))
        save_atomic(book, destination)
    book.close()
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Excel 驱动 Qwen3-VL 文本/图像推理")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path)
    source.add_argument("--text", help="单条命令行文本（输出仍为 Excel）")
    parser.add_argument("--image", type=Path, help="--text 使用的本地图像")
    parser.add_argument("--model-path", type=Path, default=Path(os.environ.get("QWEN3_VL_MODEL_PATH", ROOT / "models/pretrained/Qwen3-VL-8B-Instruct")))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--device", choices=["auto", "mps", "cpu", "cuda"], default="auto")
    args = parser.parse_args(argv)
    if args.max_new_tokens <= 0:
        parser.error("--max-new-tokens 必须大于 0")
    if args.image and not args.text:
        parser.error("--image 只可与 --text 一起使用；Excel 图像请填写 image_path")
    input_path = args.input.expanduser().resolve() if args.input else None
    if input_path:
        requests = list(read_requests(input_path))
    else:
        if not args.text.strip():
            parser.error("--text 不能为空")
        image_path = args.image.expanduser().resolve() if args.image else None
        if image_path and not image_path.is_file():
            parser.error(f"图片不存在: {image_path}")
        requests = [(args.text, MODEL_NAME, image_path)]
    if not requests:
        parser.error("输入 Excel 没有数据行")
    model_path = args.model_path.expanduser().resolve()
    if not model_path.is_dir():
        parser.error(f"模型目录不存在: {model_path}；请先运行下载脚本")
    destination = args.output or ROOT / ".result" / f"qwen3_vl_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.xlsx"
    destination = destination.expanduser().resolve()
    if input_path is not None and destination == input_path:
        parser.error("输出不能与输入文件相同")
    from models.qwen3_vl.inference import QwenRunner
    runner = QwenRunner(model_path, args.device)
    failures = run_requests(requests, runner, destination, args.max_new_tokens)
    print(f"结果: {destination}；失败 {failures} 条")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
