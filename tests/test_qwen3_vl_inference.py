import tempfile
import unittest
import hashlib
from pathlib import Path
from openpyxl import Workbook, load_workbook
from scripts.qwen3_vl.run_excel import HEADERS, MODEL_NAME, read_requests, run_requests
from scripts.qwen3_vl.restore_weights import restore


class FakeRunner:
    def __init__(self, target):
        self.target = target

    def infer(self, prompt, image_path, max_new_tokens, on_input_tokens, on_generated):
        before = load_workbook(self.target).active
        assert before.cell(2, 4).value and before.cell(2, 10).value == "running"
        on_input_tokens(12)
        middle = load_workbook(self.target).active
        assert middle.cell(2, 7).value == 12 and middle.cell(2, 5).value is None
        on_generated(4)
        after = load_workbook(self.target).active
        assert after.cell(2, 5).value and after.cell(2, 8).value == 4
        return "=test output"


class ExcelTests(unittest.TestCase):
    def test_incremental_saves_and_safe_text(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "out.xlsx"
            self.assertEqual(run_requests([("hello", MODEL_NAME, None)], FakeRunner(dest), dest), 0)
            sheet = load_workbook(dest).active
            self.assertEqual([c.value for c in sheet[1]], HEADERS)
            self.assertEqual(sheet.cell(2, 10).value, "success")
            self.assertEqual(sheet.cell(2, 9).value, "'=test output")
            self.assertGreaterEqual(sheet.cell(2, 6).value, 0)
            with self.assertRaises(FileExistsError):
                run_requests([], FakeRunner(dest), dest)

    def test_read_text_and_image(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            (folder / "example.png").write_bytes(b"image-placeholder")
            wb = Workbook()
            wb.active.append(["prompt", "model", "image_path"])
            wb.active.append(["describe", MODEL_NAME, "example.png"])
            path = folder / "input.xlsx"
            wb.save(path)
            request = list(read_requests(path))[0]
            self.assertEqual(request[2], (folder / "example.png").resolve())

    def test_invalid_model(self):
        with tempfile.TemporaryDirectory() as d:
            wb = Workbook()
            wb.active.append(["prompt", "model"])
            wb.active.append(["hello", "another-model"])
            path = Path(d) / "input.xlsx"
            wb.save(path)
            with self.assertRaises(ValueError):
                list(read_requests(path))

    def test_restore_weight_parts_and_check_hash(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            parts = root / 'parts'
            parts.mkdir()
            (parts / 'a.part').write_bytes(b'abc')
            (parts / 'b.part').write_bytes(b'def')
            manifest = {'files': [{'name': 'model.safetensors', 'size': 6,
                         'sha256': hashlib.sha256(b'abcdef').hexdigest(),
                         'parts': ['a.part', 'b.part']}]}
            restore(manifest, parts, root / 'target')
            self.assertEqual((root / 'target/model.safetensors').read_bytes(), b'abcdef')
            (parts / 'b.part').write_bytes(b'broken')
            with self.assertRaises(ValueError):
                restore(manifest, parts, root / 'bad')
            self.assertFalse((root / 'bad/model.safetensors').exists())


if __name__ == "__main__":
    unittest.main()
