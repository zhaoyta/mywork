# 智能文档问答 Agent

面向扫描版 PDF 的 RAG 问答原型，实现 OCR 解析 → 知识库构建 → 检索问答 → 答案自检的完整闭环。

## 技术栈

| 层次 | 选型 |
|------|------|
| 包管理 | uv |
| OCR | PaddleOCR（备选 Tesseract） |
| 向量库 | ChromaDB（本地持久化） |
| 嵌入 | OpenAI `text-embedding-3-small`（备选本地 `bge-small-zh-v1.5`） |
| LLM | OpenAI `gpt-4o-mini`（兼容 DeepSeek / 智谱等 API） |
| RAG 框架 | LangChain |

## 快速开始

### 1. 安装 uv

```bash
pip install uv -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 创建虚拟环境并安装依赖

```bash
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 基础依赖
uv pip install -e "." -i https://pypi.tuna.tsinghua.edu.cn/simple

# 若需本地嵌入模型（无 OpenAI Key 时）
uv pip install -e ".[local-embed]" -i https://pypi.tuna.tsinghua.edu.cn/simple

# 开发/测试依赖
uv pip install -e ".[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY 等
```

### 4. 放入 PDF 文件

```bash
mkdir -p data/pdfs
cp "GBT 1568-2008 键 技术条件.pdf" data/pdfs/
```

### 5. 解析 PDF 并构建知识库

```bash
uv run python scripts/ingest.py --pdf "data/pdfs/GBT 1568-2008 键 技术条件.pdf"

# 强制重建（清空已有知识库）
uv run python scripts/ingest.py --pdf "data/pdfs/..." --force
```

### 6. 问答

```bash
uv run python scripts/qa.py --question "键的材料硬度要求是什么？"
```

### 7. 运行评估

```bash
uv run python tests/evaluate.py

# 与基线对比（检测性能退化）
uv run python tests/evaluate.py --baseline tests/results/baseline.json
```

### 8. 单元测试

```bash
uv run pytest tests/test_unit.py -v
```

## 项目结构

```
.
├── src/
│   ├── __init__.py
│   ├── pdf_parser.py       # PDF 类型检测、OCR、表格提取
│   ├── knowledge_base.py   # 分块、向量化、ChromaDB 读写
│   ├── rag.py              # 检索、prompt 构建、答案生成
│   ├── self_check.py       # 答案自检（supported/uncertain/unsupported）
│   └── agent.py            # 对外 ask() 接口
├── scripts/
│   ├── ingest.py           # PDF → 知识库 一键脚本
│   └── qa.py               # 单问 CLI
├── tests/
│   ├── test_cases.json     # 评估测试集（10+ 题，5 类场景）
│   ├── evaluate.py         # 批量评估脚本
│   ├── test_unit.py        # 单元测试
│   └── results/            # 评估报告输出目录
├── data/
│   ├── pdfs/               # 放置输入 PDF
│   ├── chroma_db/          # ChromaDB 持久化（gitignored）
│   └── ocr_cache/          # OCR 原始输出缓存（gitignored）
├── config.yaml             # 可调参数
├── .env.example            # 环境变量模板
└── pyproject.toml          # uv 依赖管理
```

## PDF 解析结果示例

`scripts/ingest.py` 完成后输出：

```
[Ingest] total=142, text=128, table=14, pages=12
```

OCR 原始文本缓存保存在 `data/ocr_cache/` 目录，格式为 `<filename>_page001.txt`，可人工核查识别质量。

## 典型问答示例

**示例 1（正文查询）**
```
问题：键的材料硬度要求是什么？
答案：根据 GB/T 1568-2008，键的硬度应不低于 HRC 40（...）
自检：✓ supported — 答案直接来自第3页技术要求条款
来源：第3页 [text] 4.2 硬度要求...
```

**示例 2（表格查询）**
```
问题：键宽为 10mm 时，键的高度和长度范围是多少？
答案：键宽 10mm 时，键高为 8mm，长度范围为 22~110mm（...）
自检：✓ supported — 来自第5页尺寸表格
来源：第5页 [table] | 10 | 8 | 22~110 |...
```

**示例 3（无答案 - 拒答）**
```
问题：该标准适用于航空发动机的键连接吗？
答案：根据提供的文档，无法找到相关信息。
自检：✗ unsupported — 文档未涉及航空发动机应用范围
来源：（无）
```

**示例 4（模糊问题）**
```
问题：键怎么用？
答案：键主要用于轴与毂之间的周向固定，通过键槽配合传递扭矩（...）⚠️ [低置信度，请核实来源]
自检：⚠ uncertain — 问题模糊，答案为部分推断
来源：第2页 [text] 键连接应...
```

**示例 5（OCR 错误容错）**
```
问题：键的材料硬庋要求是什么？（"庋" 为 "度" 的 OCR 错误）
答案：根据 GB/T 1568-2008，键的硬度要求...
自检：✓ supported
来源：第3页 [text]
```

## 功能完成情况

### 已完成
- [x] 扫描 PDF 类型检测 + OCR 解析（PaddleOCR 主路径 / Tesseract 备用）
- [x] 表格结构识别与 Markdown 转换
- [x] 条款编号自动提取（`clause_id` 元数据）
- [x] 向量知识库构建（ChromaDB 持久化）+ OpenAI/本地嵌入双路径
- [x] RAG 问答（检索 + LLM 生成 + 来源引用）
- [x] 答案自检（三态判断：supported/uncertain/unsupported）
- [x] 评估脚本 + 11 题测试集（5 类场景）+ 基线回归检测
- [x] 单元测试（`detect_pdf_type`、`split_chunks`、`self_check` 降级）
- [x] uv 环境管理 + 清华源 + `.env` 配置

### 未完成 / 已知局限
- [ ] 表格跨页合并：PaddleOCR 对跨页表格识别有限，当前版本按页独立处理
- [ ] 流式输出：CLI 暂不支持流式，可通过 LangChain `streaming=True` 扩展
- [ ] 多文档管理：当前知识库绑定单一 PDF，多文档场景需扩展 `source` 过滤逻辑
- [ ] 演示视频：受环境限制未录制，可通过 `scripts/qa.py` 复现所有示例

## AI 工具使用说明

**使用的工具**：Claude Code（代码框架生成）、Claude Sonnet 4.6（设计文档、prompt 设计）

**如何使用**：
1. 用 Claude Code 生成模块骨架（`pdf_parser.py`、`knowledge_base.py` 等）
2. 人工审阅每个函数的逻辑正确性，特别是 OCR 降级路径、自检 JSON 解析、超时处理
3. 评估测试集题目依据 PDF 真实内容设计，不依赖 AI 生成"参考答案"
4. 自检 prompt 经过多轮迭代，确保输出 JSON 格式稳定

**如何校验**：
- 单元测试覆盖关键 fallback 逻辑（见 `tests/test_unit.py`）
- `data/ocr_cache/` 保存原始 OCR 文本，可人工比对识别准确性
- 评估报告包含每题的完整答案和自检结果，便于人工审核

**如何修正**：
- OCR 错误：通过 `config.yaml` 调整 `scanned_text_threshold`，或更换 OCR 引擎
- 自检误判：修改 `src/self_check.py` 中的 prompt 模板
- 检索质量：调整 `chunk_size`/`overlap`/`top_k` 参数

## 已知问题与局限

- PaddleOCR 安装依赖 C++ 编译环境，如遇问题请参考官方文档或改用 `OCR_ENGINE=tesseract`
- 表格跨页、合并单元格场景解析精度有限，评估报告中列明具体通过率
- 自检模块无法完全消除 LLM 幻觉，仅作辅助判断
- Windows 上 `self_check` 超时机制使用线程替代 SIGALRM（需 Python 3.9+）
