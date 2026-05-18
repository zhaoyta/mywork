## Context

本项目针对技术岗位笔试作业，目标是交付一个最小可运行的"智能文档问答 Agent"原型。输入为一份扫描版中文 PDF（`GBT 1568-2008 键 技术条件.pdf`），该文件无文本层，包含正文条款和表格。系统需完成 PDF 解析 → 知识库构建 → 检索问答 → 答案自检 → 测试评估的完整闭环。

技术约束：
- 面试截止 2 个自然日，需快速可交付
- 尽量使用主流开源工具，降低环境依赖风险
- API Key 不得提交到仓库
- Python 环境使用 **uv** 管理（替代 pip/venv），pip 安装时通过 `-i https://pypi.tuna.tsinghua.edu.cn/simple` 使用清华源加速

## Goals / Non-Goals

**Goals:**
- 完整 RAG 管道：OCR → 分块 → 向量化 → 检索 → 生成 → 自检
- 返回答案时附带来源页码和原文片段
- 自检模块区分"有据回答"、"低置信警告"、"拒答"三种状态
- 自动化评估脚本，覆盖正文、表格、无答案、模糊、OCR 错误场景
- 一键启动，README 说明完整复现步骤

**Non-Goals:**
- 多文档管理、用户权限、生产级高可用
- 流式输出 / 前端 UI（提供 CLI 和简单 API 即可）
- 多模态理解（图片内容、图表）

## Decisions

### D1: OCR 方案选 PaddleOCR（备选 Tesseract）

**选择**：PaddleOCR（`paddleocr` Python 包）作为主要 OCR 引擎。

**理由**：对中文识别精度优于 Tesseract；支持表格结构识别（`structure_v2`）；有预训练模型，无需自训练。

**备选方案**：Tesseract + pytesseract——轻量但中文表格识别弱；云端 OCR API（Azure/百度）——精度高但引入网络依赖和费用。

**降级策略**：若 PaddleOCR 安装失败，自动降级到 PyMuPDF 的内置文本提取（适用于有文本层的 PDF）。

---

### D2: 向量存储选 ChromaDB（内嵌模式）

**选择**：ChromaDB 以本地持久化模式运行，不需要独立服务进程。

**理由**：零基础设施依赖，一行代码初始化；支持元数据过滤（页码、块类型）；评估阶段可直接读取向量数据库做分析。

**备选方案**：FAISS——更快但无元数据过滤；Weaviate/Qdrant——功能强但需启动 Docker。

---

### D3: 嵌入模型选 `text-embedding-3-small`（OpenAI），备选本地 `bge-small-zh`

**选择**：优先使用 OpenAI Embedding API；若无 Key 则自动切换到 HuggingFace `BAAI/bge-small-zh-v1.5`（本地推理）。

**理由**：OpenAI 嵌入质量稳定，延迟低；bge-small-zh 对中文语义理解好，可完全离线运行。

---

### D4: RAG 框架选 LangChain

**理由**：生态完善，方便切换不同 LLM/Embedding/VectorStore；内置 RetrievalQA、来源引用、自定义 prompt 支持。

**风险**：版本迭代快，API 有 breaking change。锁定版本在 `pyproject.toml`（uv 管理）。

---

### D5: 分块策略——递归字符分块 + 表格独立分块

- 正文：`RecursiveCharacterTextSplitter`，chunk_size=500，overlap=100
- 表格：每张表格作为独立 chunk，元数据标注 `type=table`，保留原始行列结构
- 元数据字段：`page`、`type`（text/table）、`source`

---

### D6: 答案自检——基于 LLM 的后处理步骤

**流程**：生成答案后，将"问题 + 答案 + 检索片段"发给 LLM，要求其以 JSON 输出：
```json
{"verdict": "supported|uncertain|unsupported", "reason": "...", "action": "answer|warn|reject"}
```

**阈值**：`unsupported` 时拒答，`uncertain` 时保留答案但附加警告标签。

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| PaddleOCR 安装复杂（CUDA/环境依赖） | 提供 CPU-only 安装命令；文档说明降级到 Tesseract 的步骤 |
| OCR 识别错误导致检索失败 | 评估脚本包含 OCR 错误注入测试；记录原始 OCR 输出供人工核查 |
| LLM 幻觉（无法完全消除） | 自检模块降低幻觉风险；来源引用让用户可验证 |
| API Key 费用超支 | 限制单次检索 top-k=5，自检调用 token 上限；提供离线嵌入备选 |
| 表格跨页、合并单元格解析不完整 | 标注已知局限性；评估报告中列明表格测试通过率 |

## Migration Plan

1. 克隆仓库，安装 uv（`pip install uv -i https://pypi.tuna.tsinghua.edu.cn/simple`）
2. 创建虚拟环境并安装依赖：`uv venv && uv pip install -e ".[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple`
3. 配置 `.env`（`OPENAI_API_KEY` 等）
4. 运行 `uv run python scripts/ingest.py` 解析 PDF 并构建知识库
5. 运行 `uv run python scripts/qa.py --question "..."` 进行问答
6. 运行 `uv run python tests/evaluate.py` 执行评估套件

**回滚**：本项目为原型，无生产部署，无需回滚策略。

## Open Questions

- PaddleOCR 表格识别在该 PDF 上的实际精度需运行后确认
- 若 OpenAI API 不可用，评估是否切换到其他兼容 API（DeepSeek、智谱等）
