## Why

企业客户常提供扫描版 PDF（合同、标准文件、产品手册等），现有系统缺乏对此类非结构化文档进行智能问答的能力。本次作业以 `GBT 1568-2008 键 技术条件.pdf` 为典型案例，构建一个最小可运行的"智能文档问答 Agent"原型，验证 RAG + 自检的完整闭环。

## What Changes

- 新增扫描 PDF 解析模块，支持 OCR 提取正文、条款编号与表格内容
- 新增向量知识库构建模块，将解析结果分块并写入可检索存储
- 新增检索增强问答模块（RAG），接收用户问题并返回带来源引用的答案
- 新增答案自检模块，判断答案是否有依据、是否存在幻觉风险、是否应拒答
- 新增评估与测试脚本，覆盖正文、表格、无答案、模糊问题、OCR 错误等场景
- 新增 CLI / API 交互入口，支持单轮与批量问答

## Capabilities

### New Capabilities

- `pdf-parsing`: 扫描 PDF OCR 解析与结构化提取（正文段落、条款编号、表格）
- `knowledge-base`: 文本分块、向量化与可检索知识库构建
- `rag-qa`: 基于检索的问答，含来源引用（页码/片段）
- `answer-self-check`: 答案自检——有据性判断、幻觉风险评估、拒答决策
- `evaluation`: 测试与评估脚本，支持自动化回归

### Modified Capabilities

（无现有 spec，无需修改）

## Impact

- **新增依赖**：`pymupdf` / `paddleocr` 或 `tesseract`（OCR）、`langchain` 或 `llama-index`（RAG 框架）、`faiss` / `chromadb`（向量存储）、`openai` 或兼容 API（LLM）
- **新增代码**：`src/` 目录下各模块，`tests/` 评估脚本，`scripts/` 启动脚本
- **配置**：`.env` 管理 API Key，`config.yaml` 管理模型与检索参数
- **交付物**：GitHub 仓库 + README + 演示截图/视频
