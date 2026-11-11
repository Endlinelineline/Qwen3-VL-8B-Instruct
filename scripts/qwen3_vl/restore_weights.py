"""Reassemble Git LFS parts into verified official original weight files."""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def restore(manifest, parts_dir, target):
    target.mkdir(parents=True, exist_ok=True)
    for item in manifest.get('support_files', []):
        name = item['name']
        if Path(name).name != name:
            raise ValueError('非法配置文件名')
        source = parts_dir / 'support_files' / name
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != item['sha256']:
            raise ValueError(f'配置文件校验失败: {name}')
        dest = target / name
        if dest.exists():
            if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
                raise FileExistsError(f'配置文件已存在但内容不同，未覆盖: {dest}')
        else:
            shutil.copyfile(source, dest)
    for entry in manifest["files"]:
        name = entry["name"]
        if Path(name).name != name:
            raise ValueError("非法权重文件名")
        destination = target / name
        tmp = target / (name + ".restoring")
        if destination.exists():
            digest = hashlib.sha256()
            with destination.open('rb') as existing:
                for block in iter(lambda: existing.read(8 * 1024 * 1024), b''):
                    digest.update(block)
            if digest.hexdigest() == entry['sha256']:
                print(f"已存在且校验通过: {name}")
                continue
            raise FileExistsError(f"目标文件已存在但校验不符，未覆盖: {destination}")
        h = hashlib.sha256()
        size = 0
        try:
            with tmp.open('wb') as out:
                for part in entry['parts']:
                    if Path(part).name != part:
                        raise ValueError("非法分片文件名")
                    with (parts_dir / part).open('rb') as source:
                        for block in iter(lambda: source.read(8 * 1024 * 1024), b''):
                            h.update(block)
                            size += len(block)
                            out.write(block)
            if size != entry['size'] or h.hexdigest() != entry['sha256']:
                raise ValueError(f"校验失败: {name}。检查 Git LFS 文件是否下载完整")
            os.replace(tmp, destination)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        print(f"已恢复并校验: {destination}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parts-dir', type=Path, default=ROOT / 'models/weight_parts')
    parser.add_argument('--output', type=Path, default=ROOT / 'models/pretrained/Qwen3-VL-8B-Instruct')
    args = parser.parse_args()
    with (args.parts_dir / 'manifest.json').open(encoding='utf-8') as f:
        manifest = json.load(f)
    restore(manifest, args.parts_dir, args.output)


if __name__ == '__main__':
    main()
