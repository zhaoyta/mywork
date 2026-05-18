## 1. 项目初始化与环境配置

- [x] 1.1 初始化 Git 仓库，创建 `src/`、`scripts/`、`tests/results/`、`data/` 目录结构
- [x] 1.2 初始化 `pyproject.toml`（`uv init`），声明 paddleocr、pymupdf、langchain、chromadb、openai 等依赖，配置清华源：`[[tool.uv.index]] url = "https://pypi.tuna.tsinghua.edu.cn/simple"`
- [x] 1.3 运行 `uv venv && uv pip install -e ".[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple` 验证环境可正常安装
- [x] 1.4 创建 `.env.example` 模板文件（含 `OPENAI_API_KEY`、`EMBED_MODEL`、`LLM_MODEL` 等变量）
- [x] 1.5 创建 `config.yaml`，管理 chunk_size、overlap、top_k、self_check_timeout 等可调参数
- [x] 1.6 编写 `README.md`，包含 uv 安装方式、清华源说明、快速启动命令、已知问题说明

## 2. PDF 解析模块（`src/pdf_parser.py`）

- [x] 2.1 实现 `detect_pdf_type(path) -> str` 函数：通过 PyMuPDF 提取文本，判断是否为扫描件（返回 `"scanned"` 或 `"text"`）
- [x] 2.2 实现 `ocr_page(image) -> str` 函数：调用 PaddleOCR 对单页图像进行 OCR，失败时降级到 Tesseract
- [x] 2.3 实现 `extract_tables(page_image) -> list[dict]` 函数：使用 PaddleOCR 结构识别提取表格，转换为 Markdown 格式，低置信度时记录 `table_parse_warning`
- [x] 2.4 实现 `parse_pdf(path) -> list[dict]` 主函数：遍历所有页，提取文本块和表格块，识别条款编号（`clause_id`），返回带完整元数据的块列表
- [x] 2.5 为每个块确保包含 `page`、`type`（text/table）、`source`、`clause_id` 四个元数据字段

## 3. 知识库构建模块（`src/knowledge_base.py`）

- [x] 3.1 实现 `split_chunks(blocks) -> list[Document]`：对 `type=text` 块执行递归字符分块（chunk_size=500, overlap=100），`type=table` 块直接保留不切分
- [x] 3.2 实现 `get_embedder()` 工厂函数：优先返回 OpenAI Embedding，`OPENAI_API_KEY` 不可用时自动切换到 `bge-small-zh-v1.5` 本地模型
- [x] 3.3 实现 `build_knowledge_base(chunks, persist_dir)` 函数：将 chunks 向量化并写入 ChromaDB，持久化到 `data/chroma_db/`
- [x] 3.4 实现 `load_knowledge_base(persist_dir)` 函数：加载已有知识库，打印块数量统计
- [x] 3.5 编写 `scripts/ingest.py`：解析命令行参数（`--pdf`、`--force`），调用 parser + knowledge_base，完成后打印统计行（total/text/table/pages）

## 4. RAG 问答模块（`src/rag.py` + `src/agent.py`）

- [x] 4.1 实现 `retrieve(question, kb, top_k) -> list[Document]` 函数：对问题向量化后查询 ChromaDB，返回带相似度分数的片段列表
- [x] 4.2 实现 `build_prompt(question, retrieved_docs) -> str` 函数：将检索片段拼入 prompt 模板，明确指示 LLM 仅基于提供的文档回答
- [x] 4.3 实现 `generate_answer(prompt) -> str` 函数：调用 LLM 生成答案，检索为空时直接返回固定拒答语
- [x] 4.4 实现 `format_sources(docs) -> list[dict]` 函数：将检索片段格式化为含 `page`、`type`、`snippet`（前50字）的列表
- [x] 4.5 实现 `src/agent.py:ask(question) -> dict` 函数：串联检索→生成→自检→格式化，返回完整结构化响应
- [x] 4.6 编写 `scripts/qa.py`：接收 `--question` 参数，调用 `ask()`，在标准输出打印格式化结果（答案、来源、自检状态）

## 5. 答案自检模块（`src/self_check.py`）

- [x] 5.1 实现 `self_check(question, answer, sources) -> dict` 函数：构造自检 prompt，调用 LLM 返回 JSON 格式自检结果
- [x] 5.2 解析 LLM 返回的 JSON，提取 `verdict`、`reason`、`action` 三个字段，无效 JSON 时降级为 `uncertain`
- [x] 5.3 实现超时处理：自检调用超过 10 秒时，捕获异常并返回 `{"verdict": "uncertain", "reason": "self_check_failed", "action": "warn"}`
- [x] 5.4 在 `agent.ask()` 中根据 `action` 字段决定最终输出：`reject` 时替换答案为拒答文本，`warn` 时附加警告标签

## 6. 评估与测试（`tests/`）

- [x] 6.1 编写 `tests/test_cases.json`：包含至少 10 个测试问题，覆盖 `factual`、`table`、`no_answer`、`ambiguous`、`ocr_error` 五类，每题含 `question`、`category`、`expected_keywords`（或 `expect_reject: true`）字段
- [x] 6.2 实现 `tests/evaluate.py` 主脚本：批量调用 `ask()`，对每题判断答案是否包含预期关键词，记录来源页码命中情况
- [x] 6.3 计算并输出汇总指标：答案命中率（Hit@k）、拒答准确率、来源页码正确率、各类别通过率
- [x] 6.4 将评估详情写入 `tests/results/eval_report.json`，包含时间戳和每题的完整问答记录
- [x] 6.5 实现 `--baseline` 模式：与历史基线比较，任一类别下降超过 10% 时以非零退出码退出并打印退化警告
- [x] 6.6 编写 `tests/test_unit.py`：对 `detect_pdf_type`、`split_chunks`、`self_check` 降级逻辑编写单元测试，使用 pytest 运行

## 7. 文档与交付物

- [x] 7.1 完善 `README.md`：补充 PDF 解析结果示例、5 个典型问答示例截图说明、测试运行命令
- [x] 7.2 在 README 中说明 AI 工具使用情况：使用了哪些工具、如何校验输出、如何修正错误
- [x] 7.3 在 README 中说明已完成和未完成的功能，以及未完成的原因
- [x] 7.4 确认仓库中无 API Key、账号密码或其他敏感信息（检查 `.gitignore` 覆盖 `.env`）
- [ ] 7.5 录制或截取演示材料：完整启动流程、PDF 解析结果、至少 5 个问答（含表格问题和无答案问题）、来源引用和自检结果、评估脚本运行结果
