"""Run each Excel row, persisting measurement stages immediately."""
import argparse
import os
import shutil
import sys
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
TEMPLATE_HEADERS = {
    "问题prompt": "prompt", "prompt": "prompt", "问题": "prompt",
    "所用模型": "model", "model": "model", "图片路径": "image_path", "image_path": "image_path",
    "开始时间": "start", "结束时间": "end", "推理耗时（秒）": "duration",
    "输入token数量": "input_tokens", "输出token数量": "output_tokens",
    "生成答案": "answer", "ttft（ms）": "ttft", "ttft(ms)": "ttft",
}
TEMPLATE_REQUIRED = {"prompt", "model", "start", "end", "duration", "input_tokens", "output_tokens", "answer", "ttft"}


def header_name(value):
    normalized = "".join(str(value).split()).casefold() if value is not None else ""
    return TEMPLATE_HEADERS.get(normalized, normalized)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def cell_text(value):
    return str(value)


def write_literal(sheet, row, column, value):
    # Preserve the exact input/output while preventing Excel formula execution.
    cell = sheet.cell(row, column)
    cell.value = cell_text(value)
    cell.data_type = "s"


def read_requests(path):
    book = load_workbook(path, read_only=True, data_only=False)
    try:
        rows = book.active.iter_rows(values_only=True)
        header = next(rows, None)
        if not header:
            raise ValueError("输入 Excel 为空")
        names = [header_name(x) for x in header]
        if len(set(x for x in names if x)) != len([x for x in names if x]):
            raise ValueError("输入 Excel 的列名不能重复")
        if not {"prompt", "model"}.issubset(names):
            raise ValueError("首行必须包含 prompt 和 model 列；image_path 可选")
        for row_number, row in enumerate(rows, 2):
            data = dict(zip(names, row))
            if all(v is None for v in row):
                continue
            prompt, model = data.get("prompt"), data.get("model")
            if not isinstance(prompt, str) or not prompt.strip():
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


def template_layout(path):
    book = load_workbook(path, read_only=True)
    try:
        sheet = book.active
        header = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), ())
        names = [header_name(value) for value in header]
        if len(set(n for n in names if n)) != len([n for n in names if n]):
            raise ValueError("输入 Excel 的列名不能重复")
        if not TEMPLATE_REQUIRED.issubset(names):
            return None
        columns = {name: index for index, name in enumerate(names, 1) if name}
        rows = []
        for row_number, values in enumerate(sheet.iter_rows(min_row=2, values_only=True), 2):
            if all(value is None for value in values):
                continue
            result_fields = TEMPLATE_REQUIRED - {"prompt", "model"}
            if any(values[columns[name] - 1] is not None for name in result_fields):
                raise ValueError(f"第 {row_number} 行已有结果，请使用结果列为空的输入表")
            rows.append(row_number)
        return sheet.title, columns, rows
    finally:
        book.close()


def copy_template(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, destination.open("xb") as dst:
        shutil.copyfileobj(src, dst)


def run_template_requests(requests, runner, destination, layout, max_new_tokens=256):
    sheet_name, columns, row_numbers = layout
    if len(requests) != len(row_numbers):
        raise ValueError("输入请求与工作表行数不一致")
    book = load_workbook(destination)
    sheet = book[sheet_name]
    failures = 0
    try:
        for row, (prompt, model, image_path) in zip(row_numbers, requests):
            started = time.perf_counter()
            sheet.cell(row, columns["start"], utc_now())
            save_atomic(book, destination)

            def on_input_tokens(count):
                sheet.cell(row, columns["input_tokens"], count)
                save_atomic(book, destination)

            def on_first_token():
                elapsed = (time.perf_counter() - started) * 1000
                sheet.cell(row, columns["ttft"], round(elapsed, 3))
                save_atomic(book, destination)

            def on_generated(count):
                elapsed = time.perf_counter() - started
                sheet.cell(row, columns["end"], utc_now())
                sheet.cell(row, columns["duration"], round(elapsed, 6))
                sheet.cell(row, columns["output_tokens"], count)
                save_atomic(book, destination)

            try:
                answer = runner.infer(prompt, image_path, max_new_tokens, on_input_tokens, on_first_token, on_generated)
                write_literal(sheet, row, columns["answer"], answer)
            except Exception as exc:
                failures += 1
                print(f"第 {row} 行推理失败: {type(exc).__name__}: {exc}", file=sys.stderr)
            save_atomic(book, destination)
    finally:
        book.close()
    return failures


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
        sheet.append([None] * len(HEADERS))
        row = sheet.max_row
        write_literal(sheet, row, 1, prompt)
        write_literal(sheet, row, 2, model)
        if image_path:
            write_literal(sheet, row, 3, image_path)
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
            write_literal(sheet, row, 9, answer)
            sheet.cell(row, 10, "success")
        except Exception as exc:
            failures += 1
            sheet.cell(row, 10, "failed")
            write_literal(sheet, row, 11, f"{type(exc).__name__}: {exc}")
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
        layout = template_layout(input_path)
    else:
        layout = None
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
    if layout is not None:
        copy_template(input_path, destination)
        print(f"已创建初始输出副本: {destination}", flush=True)
    from models.qwen3_vl.inference import QwenRunner
    runner = QwenRunner(model_path, args.device)
    if layout is None:
        failures = run_requests(requests, runner, destination, args.max_new_tokens)
    else:
        failures = run_template_requests(requests, runner, destination, layout, args.max_new_tokens)
    print(f"结果: {destination}；失败 {failures} 条")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
