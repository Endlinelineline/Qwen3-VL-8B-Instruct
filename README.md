# Qwen3-VL-8B-Instruct Excel 推理

本项目从 Excel 逐行读取文本问题与可选本地图片，使用官方 `Qwen/Qwen3-VL-8B-Instruct` 和 Hugging Face Transformers 在本地运行，并在 `.result/` 实时保存每条记录。模型只在启动时加载一次。适用于 macOS，Windows 也可使用 CPU；本项目的目标部署机是另一台 Mac。

指定 GitHub 仓库创建时为空。

## 环境和安装

- 建议 Apple Silicon Mac，Python 3.10–3.12；Apple MPS 使用 float16。官方 BF16 权重约 17.5 GB，加载、KV 缓存、图片和系统还需额外内存；请在目标 Mac 上检查统一内存及空闲磁盘，16 GB 统一内存通常不足以舒适运行原始精度模型。当前未获取目标 Mac 的具体配置，不能保证可运行。
- Intel Mac 自动使用 CPU 和 float32，速度较慢且内存需求更高；这不是量化模型。Windows 无 MPS 时也使用 CPU。若内存不足，应另外评估量化模型，并注明模型来源与精度。
- 官方模型：[Qwen/Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)；[Transformers Qwen3-VL 文档](https://huggingface.co/docs/transformers/v4.57.3/model_doc/qwen3_vl)。这里固定 Transformers 4.57.3，尚未在目标 Mac 上验证版本组合。

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

1. Git LFS 镜像上传完成后才可还原：先安装 [Git LFS](https://git-lfs.com/)，运行 `git lfs install` 和 `git lfs pull`，然后运行 `python -m scripts.qwen3_vl.restore_weights`。脚本恢复官方原始文件名并验证 SHA-256；分片与原始文件会同时占用磁盘，请预留至少 40 GB 及运行所需空间。
2. 从 Qwen 官方仓库下载：运行 `python -m scripts.qwen3_vl.download_model`，可用 `--output` 下载到其他目录。

原始完整模型位于 `models/pretrained/Qwen3-VL-8B-Instruct/`，这一运行目录由 Git 忽略。GitHub 镜像上传完成后将以 Git LFS 分片存储权重，不改变本地运行所用的原始文件。权重约 17.5 GB，取决于网络及 GitHub LFS 的账号配额。

## 输入与运行

在 `.data/example_input.xlsx` 的第一张工作表中，首行必须是 `prompt`、`model`；`image_path` 可选。模型列使用 `Qwen3-VL-8B-Instruct` 或 `Qwen/Qwen3-VL-8B-Instruct`。每行代表一次请求。纯文本时 `image_path` 留空；图文时填写相对于输入 Excel 所在目录的图片路径，或图片绝对路径。示例第二行需要自行放置 `.data/example.jpg`；如只测试文本，请删除第二行。

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

默认输出 `.result/qwen3_vl_<时间>_<运行标识>.xlsx`。每行对应一个输入请求，字段：`prompt`、`model`、`image_path`、`开始时间戳_UTC`、`结束时间戳_UTC`、`推理耗时_秒`、`输入token数量`、`输出token数量`、`生成答案`、`状态`、`错误信息`、`TTFT_ms`。时间为带时区的 UTC ISO 8601 字符串，耗时使用单调时钟秒数。

每次请求开始前写入开始时间；处理器完成后立即写入输入 token 数；生成首个输出 token 并同步设备时，立即将从开始时间到该时刻的延迟以毫秒写入同一行 `TTFT_ms`；模型生成结束并同步设备后立即写入结束时间、耗时和输出 token 数；随后保存回答。这里 TTFT 是第一个生成 token 的时间，若首 token 是结束标记也计入，而非首个可见文字的时间。每一阶段用临时文件与原子替换写入，不是一直打开 Excel 实时流式刷新；在 Excel 程序中可能需要重新打开文件查看。模型加载不在计时中；开始时间位于处理器处理 prompt 之前，结束时间在模型生成完成同步后、答案文本解码之前。为实时落盘，计时区间包含中间 Excel 保存的开销，也包含输入处理和设备传输，不能视作纯 GPU 内核时间；TTFT 写盘开销包含在完整耗时中，但不包含在已测得的 TTFT 值中。输出 token 数包括生成的特殊结束 token；输入 token 含聊天模板和图片 token。不同运行的时间须在相同软硬件和测量方式下比较。

失败行标记为 `failed`，错误信息写入结果；未生成的结束时间、耗时和 token 字段保持空值。进程意外中断时 `running`／`generated` 行可用于识别未完成请求。Excel 单元格长度有限（32767 字符），长 prompt、回答可能被 Excel 截断，不适合用于保存超长文本。推理脚本不上传用户数据；`.data/`、`.result/`、模型运行目录、日志和环境均不提交 Git。

## 常见问题

- 内存不足或 MPS 不可用：查看 `--device cpu` 和可用内存；CPU float32 将明显增加内存和耗时。不要将量化结果与原始精度混为一谈。
- 下载中断：重新运行下载命令；确认磁盘、网络及 Hugging Face 访问权限。
- Excel 打开时保存失败：关闭 Excel 中同名输出文件后重新运行，选择新的输出文件。
- 图片路径错误：路径相对于输入 Excel 文件所在目录，而不是当前 shell 目录。
