# Outline RAG Sync Tool

## Introduction
This tool synchronizes documents between Outline and RAGFlow. It reads documents from Outline, checks for updates, and uploads them to RAGFlow if necessary. It also handles document deletions and metadata updates.

该工具可在 Outline 和 RAGFlow 之间同步文档。它从 Outline 读取文档，检查更新，并在必要时将其上传到 RAGFlow。它还能处理文档删除和元数据更新。

## Installation /  安装部署
1. Install dependencies / 安装依赖
```bash
pip install ragflow-sdk outline-wiki-api toml
```
由于`ragflow-sdk`的[python版本要求比较奇怪](https://www.weiran.ink/lang-py/pip-package-version-problem.html)，短期内（今天是2025年4月13日）建议只使用python 3.12.

2. Configure the tool / 配置工具
   - Create a `config.toml` file in the `data` directory based on the `config.toml.sample` template.
   - Fill in the necessary API keys, URLs, and other configurations.

3. Run the tool / 运行工具
   ```bash
   python sync_tool.py
   ```

## 工作逻辑
1. **读取配置文件** / Read the configuration file
2. **初始化实例** / Initialize instances of RAGFlow and OutlineWiki
3. **连接数据库** / Connect to the SQLite database
4. **获取文档** / Get documents from Outline and RAGFlow
5. **处理文档映射** / Process document mapping
   - Mark documents in Outline as "待更新" if they don't exist in RAGFlow or have been updated.
   - Mark documents as "已更新" after synchronization.
6. **处理删除的文档** / Process deleted documents
   - Delete documents in RAGFlow that are marked as "上游已删除" in the database.
7. **上传新文档** / Upload new documents
   - Upload documents from Outline to RAGFlow if they are marked as "待更新".
8. **更新元数据** / Update metadata
   - Update metadata fields for the uploaded documents based on the configuration.
9. **异步解析** / Asynchronous parsing
   - Optionally, initiate asynchronous parsing of the uploaded documents if configured.

## 配置项说明
- **ragflow_token**: API key for RAGFlow / RAGFlow的API密钥
- **ragflow_url**: Base URL for RAGFlow API / RAGFlow API的基础URL
- **outline_token**: API key for Outline / Outline的API密钥
- **outline_url**: Base URL for Outline API / Outline API的基础URL
- **db_path**: Path to the SQLite database / SQLite数据库的路径
- **target_data_set**: Target dataset ID in RAGFlow, find it in web page url / RAGFlow中的目标数据集ID，可以从知识库页面url中找到
- **minimum_content_length**: Minimum length of document content to be uploaded / 上传的文档内容的最小长度
- **delete_non_upstream**: Whether to delete documents in RAGFlow that are not in Outline / 是否删除RAGFlow中不在Outline中的文档
- **meta_map**: Mapping of metadata fields from Outline to RAGFlow / 从Outline到RAGFlow的元数据字段映射
- **auto_start_parse**: Whether to automatically start parsing documents after uploading / 上传文档后是否自动开始解析

## Other / 其他说明
- 确保在 `config.toml` 中正确配置了 API 密钥和 URL。
- 如果 SQLite 数据库中还不存在 “document_mapping ”表，工具将在其中创建该表。
- 该工具将根据最后更新的时间戳来处理文档的更新和删除。
- 该工具假定 Outline 和 RAGFlow API 已正确设置并可访问。
- 确保文档内容长度足够 RAGFlow 处理。
- 该工具将向控制台打印信息，显示文档同步和解析的进度。

- Ensure that the API keys and URLs are correctly configured in `config.toml`.
- The tool will create a `document_mapping` table in the SQLite database if it does not already exist.
- The tool will handle document updates and deletions based on the last updated timestamp.
- This tool assumes that the Outline and RAGFlow APIs are correctly set up and accessible.
- Ensure that the document content length is sufficient to be processed by RAGFlow.
- The tool will print messages to the console indicating the progress of document synchronization and parsing.
