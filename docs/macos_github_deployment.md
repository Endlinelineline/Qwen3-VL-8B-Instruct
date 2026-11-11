# 在 Mac 上从 GitHub 部署并运行 Qwen3-VL

## 一、项目能完成什么

程序从 Excel 按行读取问题和模型名称，在本机加载 Qwen3-VL-8B-Instruct，逐行生成回答。对模板中的每一条问题，程序在同一行填写开始时间、结束时间、推理耗时（秒）、输入 token 数量、输出 token 数量、生成答案和首 token 延迟 TTFT（毫秒）。每个阶段分别保存，输出文件保留输入表的工作表、表头和行顺序。单次启动只加载一次模型。

GitHub 仓库：<https://github.com/Endlinelineline/Qwen3-VL-8B-Instruct>

## 二、准备条件

建议使用 Apple Silicon（M 系列芯片）Mac，准备 Python 3.11、Git 和 Git LFS。模型原始权重约 17.5 GB，GitHub 的权重分片和还原后的模型会同时占空间；使用 GitHub 分片还原时建议预留至少 40 GB 磁盘，再留出安装和运行空间。Git LFS 下载可能受仓库流量或配额限制。

模型加载还需要额外统一内存：16 GB 统一内存通常不足以舒适运行完整模型。此项目和以下依赖组合尚未在目标 Mac 实测，能否运行取决于芯片、macOS、可用内存及软件兼容性。MPS 不可用时程序会使用内存需求更高、速度更慢的 CPU float32。

安装软件：

1. 安装原生 Apple Silicon Python 3.11，安装后终端应能执行 `python3.11 --version`。项目本机离线包还附带 Python.org 的 3.11.9 安装器；这是较旧版本，优先使用已安装的较新 Python 3.11。Python 官方下载：<https://www.python.org/downloads/macos/>。
2. 安装 Git；终端执行 `git --version` 验证。Mac 如提示安装 Apple 命令行开发工具，请按提示完成。
3. 如果要从 GitHub 拉取模型分片，安装 Git LFS：<https://git-lfs.com/>，然后执行 `git lfs install`。如果直接复制已有完整模型权重到 Mac，可省略分片还原。

## 三、从 GitHub 下载项目

打开 Mac 的“终端”，执行：

```bash
cd ~/Desktop
git lfs install
git clone https://github.com/Endlinelineline/Qwen3-VL-8B-Instruct.git
cd Qwen3-VL-8B-Instruct
git lfs pull
```

克隆和 `git lfs pull` 需要联网，会下载大型权重分片，可能耗时较长。若因 Git LFS 限额或网络失败，请先解决后重试；不要把没有下载完整的指针文件当作权重。

## 四、准备完整权重

选择一种方式：

**方式 A：还原 GitHub 分片。** Python 环境准备好后，在项目根目录运行：

```bash
python -m scripts.qwen3_vl.restore_weights
```

脚本会合并分片、恢复官方文件名并校验 SHA-256。模型目录为 `models/pretrained/Qwen3-VL-8B-Instruct/`。

**方式 B：复制本机已有完整模型。** 将 Windows 项目中 `models/pretrained/Qwen3-VL-8B-Instruct/` 整个文件夹复制到 Mac 项目的同一路径，保留全部权重、配置和处理器文件。此方式无需重新合并或下载完整权重。如尚未 clone 且选择此方式，可先设置 `GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/Endlinelineline/Qwen3-VL-8B-Instruct.git` 避免 clone 时下载分片；无需执行 `git lfs pull`。

也可完成依赖安装后运行 `python -m scripts.qwen3_vl.download_model` 从模型官方来源下载。默认模型目录相同。

## 五、安装运行环境

### 方法 1：Mac 联网安装

在 Mac 的项目根目录运行：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-qwen3-vl.txt -c macos_offline/constraints.txt
```

约束文件将 PyTorch 和 torchvision 分别固定为 2.7.1 和 0.22.1。安装需联网，首次耗时取决于网络。之后可按第四节所选方式准备权重。

### 方法 2：使用 Windows 已下载的离线依赖

仓库包含通过 Git LFS 存放的离线 wheel、Python 安装包，以及用户同意公开的输入 Excel；运行结果不包含在仓库中。下载 ZIP 时必须在仓库中启用 LFS 文件打包，或通过 Git LFS 拉取。还可从 Windows 项目复制以下内容到 Mac 项目相同位置：

- `macos_offline/wheelhouse/`：Apple Silicon、Python 3.11 所用依赖；
- `macos_offline/python_installer/`：可选的官方 Python 安装包；
- `models/pretrained/Qwen3-VL-8B-Instruct/`：已下载的完整模型；
- `.data/模型推理问题记录v8.xlsx`：用户自己的输入表。

先在 Mac 安装原生 Python 3.11，再在项目根目录执行：

```bash
bash scripts/qwen3_vl/macos_offline_run.sh
```

脚本会先按需合并并校验模型分片，然后在本地创建 `.venv`，从 wheelhouse 校验哈希并安装依赖，最后直接运行 Excel 推理。不要从 Windows 复制 `.venv`；如果已有不兼容的 `.venv`，先将其改名。离线包只针对 Apple Silicon 和 Python 3.11，Intel Mac 请采用在线安装并另行确认模型可运行性。

## 六、准备输入并运行

将 `模型推理问题记录v8.xlsx` 复制到 Mac 项目根目录的 `.data/`。此输入文件已按用户要求公开放入仓库，下载者均可查看。保留原表头：

| 列 | 内容 |
|---|---|
| A | 问题 prompt |
| B | 所用模型，填写 `Qwen3-VL-8B-Instruct` |
| C | 开始时间 |
| D | 结束时间 |
| E | 推理耗时（秒） |
| F | 输入 token 数量 |
| G | 输出 token 数量 |
| H | 生成答案 |
| I | TTFT（ms） |

运行前每条待处理行的 C–I 列应为空。在线安装方法下，从项目根目录运行：

```bash
source .venv/bin/activate
python -m scripts.qwen3_vl.run_excel --input '.data/模型推理问题记录v8.xlsx' --max-new-tokens 256
```

离线脚本默认已经执行该命令，无须再运行一次。每次启动会产生一个新的 `.result/qwen3_vl_时间_标识.xlsx`，开始时它是输入表的完整副本；随后逐行写入测量值和答案，不会修改输入文件。运行时请关闭正在写入的输出文件；查看最新结果可能需要重新打开 Excel。终端会打印结果路径和失败行信息。

## 七、计时和常见问题

- 开始时间在处理 prompt 之前，结束时间在生成完成、设备同步之后且文本解码之前；时间戳是带时区的 UTC 字符串。首 token 延迟从开始到首个输出 token，单位毫秒。输入 token 包含聊天模板及可能的图片 token，输出 token 包含特殊结束 token。
- 实时写盘带来额外开销，因此耗时和 TTFT 包含部分处理与保存开销，不是单纯的 GPU 内核时间。模型加载不计入推理耗时。
- 结果列已有内容会被程序拒绝；请使用结果列为空的原始表。若模型目录不存在或文件不全，请检查第四节的权重准备；文件路径含空格时请使用引号。
- 内存不足或系统不支持 MPS 时，原始精度模型可能无法加载。请先确认 Mac 的“关于本机”中的芯片和内存；不要把量化模型的测量结果当作原始模型的同精度结果。
- 离线脚本报缺少 wheelhouse 时，说明离线依赖文件没有正确下载；请检查 ZIP 是否包含实际 LFS 文件、通过 Git LFS 下载，或改用方法 1 联网安装。
