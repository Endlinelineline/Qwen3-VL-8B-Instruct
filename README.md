# Qwen3-VL-8B-Instruct Excel 推理

本项目从 Excel 逐行读取文本问题与可选本地图片，使用官方 `Qwen/Qwen3-VL-8B-Instruct` 和 Hugging Face Transformers 在本地运行，并在 `.result/` 实时保存每条记录。模型只在启动时加载一次。适用于 macOS，Windows 也可使用 CPU；本项目的目标部署机是另一台 Mac。

指定 GitHub 仓库创建时为空。

## Apple Silicon Mac 离线快捷部署

本机的 `macos_offline/` 包含针对 Apple Silicon、Python 3.11 的 wheel 离线依赖；大型 wheel 和 Python 安装包不上传 Git，必须随项目文件夹一起复制。依赖固定为 PyTorch 2.7.1、torchvision 0.22.1、Transformers 4.57.3 等；此组合尚未在目标 Mac 上实际测试。原生 arm64 Python 3.11 需预先安装；如没有，可打开 `macos_offline/python_installer/python-3.11.9-macos11.pkg` 并按安装器提示安装（这是 Python 3.11 的较旧版本，可优先使用已安装的较新 Python 3.11）。

将整个项目复制到 Mac 后，打开终端并进入项目根目录（下面以桌面路径为例），执行：

```bash
cd ~/Desktop/qwen3_vl_project
bash scripts/qwen3_vl/macos_offline_run.sh
```

脚本在项目内创建 `.venv`，从本地 wheelhouse 校验哈希并安装依赖，再读取 `.data/模型推理问题记录v8.xlsx`，输出到 `.result/`。后续执行同一条 `bash` 命令即可。可在脚本后添加参数指定不同输入，例如 `bash scripts/qwen3_vl/macos_offline_run.sh --input .data/other.xlsx`。脚本不自动安装 Python 或覆盖已有结果。如果以前从别的电脑复制了 `.venv`，请先将其改名，再运行脚本。

该离线包不适用于 Intel Mac；需要 Apple Silicon 原生终端。模型对内存和系统版本有要求，目标机器的实际兼容性需现场验证。

## 环境和安装

- 建议 Apple Silicon Mac，Python 3.10–3.12；Apple MPS 使用 float16。官方 BF16 权重约 17.5 GB，加载、KV 缓存、图片和系统还需额外内存；请在目标 Mac 上检查统一内存及空闲磁盘，16 GB 统一内存通常不足以舒适运行原始精度模型。当前未获取目标 Mac 的具体配置，不能保证可运行。
- Intel Mac 自动使用 CPU 和 float32，速度较慢且内存需求更高；这不是量化模型。Windows 无 MPS 时也使用 CPU。若内存不足，应另外评估量化模型，并注明模型来源与精度。
- 官方模型：[Qwen/Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)；[Transformers Qwen3-VL 文档](https://huggingface.co/docs/transformers/v4.57.3/model_doc/qwen3_vl)。这里固定 Transformers 4.57.3，尚未在目标 Mac 上验证版本组合。
- `vendor/transformers-4.57.3-py3-none-any.whl` 保存了 Transformers 官方发行包，其中包括 Qwen3-VL 的模型实现代码和许可证。该包为跨平台 Python wheel，但并不包含 PyTorch 等其他依赖；安装 `requirements-qwen3-vl.txt` 仍需下载适用于目标 Mac 的依赖包。

```bash
git clone https://github.com/Endlinelineline/Qwen3-VL-8B-Instruct.git
cd Qwen3-VL-8B-Instruct
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-qwen3-vl.txt
python -m scripts.qwen3_vl.create_example
```

模型有两种准备方法，二选一：

1. 从仓库的 Git LFS 镜像还原：先安装 [Git LFS](https://git-lfs.com/)，运行 `git lfs install` 和 `git lfs pull`，然后运行 `python -m scripts.qwen3_vl.restore_weights`。脚本恢复官方原始文件名并验证 SHA-256；分片与原始文件会同时占用磁盘，请预留至少 40 GB 及运行所需空间。
2. 从 Qwen 官方仓库下载：运行 `python -m scripts.qwen3_vl.download_model`，可用 `--output` 下载到其他目录。

原始完整模型位于 `models/pretrained/Qwen3-VL-8B-Instruct/`，这一运行目录由 Git 忽略。GitHub 镜像以 Git LFS 分片存储权重，不改变本地运行所用的原始文件。权重约 17.5 GB，下载取决于网络及 GitHub LFS 的账号配额。

## 输入与运行

将你的 `模型推理问题记录v8.xlsx` 放在 `.data/`。此文件不随 Git 上传，因此换到 Mac 时需要单独复制过去。使用工作表 `推理记录` 为当前活动表，保留九列表头：`问题 prompt`、`所用模型`、`开始时间`、`结束时间`、`推理耗时（秒）`、`输入 token 数量`、`输出 token 数量`、`生成答案`、`TTFT（ms）`。开始运行时，程序先把完整输入表复制到 `.result/`，然后仅在对应原行填写结果；要求输入表的结果列为空。若需要图文输入，可增加 `图片路径` 列。

```bash
python -m scripts.qwen3_vl.run_excel --input '.data/模型推理问题记录v8.xlsx' --max-new-tokens 256
```

在 `.data/example_input.xlsx` 的第一张工作表中，首行必须包含 `prompt`、`model`；也可分别写成 `问题prompt`、`所用模型`。`image_path`（或 `图片路径`）可选。模型列使用 `Qwen3-VL-8B-Instruct` 或 `Qwen/Qwen3-VL-8B-Instruct`。每行代表一次请求。纯文本时图片列留空；图文时填写相对于输入 Excel 所在目录的图片路径，或图片绝对路径。示例第二行需要自行放置 `.data/example.jpg`；如只测试文本，请删除第二行。

```bash
python -m scripts.qwen3_vl.run_excel --input .data/example_input.xlsx --max-new-tokens 256
# 外部模型目录：
python -m scripts.qwen3_vl.run_excel --input .data/example_input.xlsx --model-path /path/to/Qwen3-VL-8B-Instruct
# 单条文本、图文冒烟测试；结果同样写入 Excel：
python -m scripts.qwen3_vl.run_excel --text "你好，请介绍一下你自己。" --max-new-tokens 64
python -m scripts.qwen3_vl.run_excel --text "请描述图片。" --image .data/example.jpg --max-new-tokens 64
python -m unittest discover -s tests -v
```

可用 `QWEN3_VL_MODEL_PATH` 覆盖默认模型路径，`--model-path` 优先；`--device` 可选 `auto`、`mps`、`cpu`、`cuda`。为了分别测试纯文本和图片，请在输入表中保留对应行；模型和图片均须位于本地。`--output` 可以指定新的结果文件，但不会覆盖已有文件。

## 输出与计时口径

默认输出 `.result/qwen3_vl_<时间>_<运行标识>.xlsx`。九列表模板的输出保留输入表结构；只含 prompt 和 model 等简表或 `--text` 则使用旧版的独立结果表（含状态及错误信息列）。时间为带时区的 UTC ISO 8601 字符串，耗时使用单调时钟秒数。

每次请求开始前写入开始时间；处理器完成后立即写入输入 token 数；生成首个输出 token 并同步设备时，立即将从开始时间到该时刻的延迟以毫秒写入同一行 `TTFT_ms`；模型生成结束并同步设备后立即写入结束时间、耗时和输出 token 数；随后保存回答。这里 TTFT 是第一个生成 token 的时间，若首 token 是结束标记也计入，而非首个可见文字的时间。每一阶段用临时文件与原子替换写入，不是一直打开 Excel 实时流式刷新；在 Excel 程序中可能需要重新打开文件查看。模型加载不在计时中；开始时间位于处理器处理 prompt 之前，结束时间在模型生成完成同步后、答案文本解码之前。为实时落盘，计时区间包含中间 Excel 保存的开销，也包含输入处理和设备传输，不能视作纯 GPU 内核时间；TTFT 写盘开销包含在完整耗时中，但不包含在已测得的 TTFT 值中。输出 token 数包括生成的特殊结束 token；输入 token 含聊天模板和图片 token。不同运行的时间须在相同软硬件和测量方式下比较。

九列表模板若某行失败，错误打印在终端，未产生的结果保持空值；简表结果会在状态和错误信息列记录失败。Excel 单元格长度有限（32767 字符），长 prompt、回答可能被 Excel 截断，不适合用于保存超长文本。推理脚本不上传用户数据；`.data/`、`.result/`、模型运行目录、日志和环境均不提交 Git。

## 常见问题

- 内存不足或 MPS 不可用：查看 `--device cpu` 和可用内存；CPU float32 将明显增加内存和耗时。不要将量化结果与原始精度混为一谈。
- 下载中断：重新运行下载命令；确认磁盘、网络及 Hugging Face 访问权限。
- Excel 打开时保存失败：关闭 Excel 中同名输出文件后重新运行，选择新的输出文件。
- 图片路径错误：路径相对于输入 Excel 文件所在目录，而不是当前 shell 目录。
