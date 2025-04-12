import toml
import sqlite3
from datetime import datetime
from ragflow_sdk import RAGFlow
from ragflow_sdk.modules.document import Document
from ragflow_sdk.modules.dataset import DataSet as ragDataset
from outline_wiki_api.models.document import Document as otDocument
from outline_wiki_api import OutlineWiki


def get_outline_doc_meta(propName: str, doc: otDocument, outline_base_url: str):
    if propName == "id":
        return str(doc.id)
    if propName == "title":
        return doc.title
    if propName == "sub_url":
        return doc.url
    if propName == "site_url":
        return outline_base_url + doc.url
    if propName == "created_by":
        return doc.created_by.name
    if propName == "updated_by":
        return doc.updated_by.name
    if propName == "updated_at":
        return doc.updated_at.isoformat()
    raise ValueError(f"Invalid propName: {propName}")


def get_all_documents_from_ragflow_dataset(ds: ragDataset):
    docs = []
    page = 1
    while True:
        crtDocs = ds.list_documents(page=page)
        if len(crtDocs) == 0:
            break
        docs.extend(crtDocs)
        page += 1

    return docs


# 读取配置文件
config = toml.load("data/config.toml")

# Initialize RAGFlow instance / 初始化RAGFlow实例
theRAG = RAGFlow(
    api_key=config["ragflow"]["ragflow_token"],
    base_url=config["ragflow"]["ragflow_url"],
)

# Initialize OutlineWiki instance / 初始化OutlineWiki实例
theOutline = OutlineWiki(
    token=config["outline"]["outline_token"], url=config["outline"]["outline_url"]
)

# Initialize database connection / 初始化数据库连接
dbConn = sqlite3.connect(config["db"]["db_path"])
dbCursor = dbConn.cursor()

# Create database table (if not exists) / 创建数据库表（如果不存在）
dbCursor.execute(
    """
CREATE TABLE IF NOT EXISTS document_mapping (
    ragflow_doc_id TEXT,
    outline_doc_id TEXT,
    last_updated TEXT,
    status TEXT
)
"""
)
dbConn.commit()

# Get all documents from Outline / 获取Outline中的所有文档
collcts = theOutline.collections.list().data
outline_docs = {}
for collct in collcts:
    docs = theOutline.documents.list(collection_id=collct.id)
    for doc in docs.data:
        # Check if document content length meets the requirement / 检查文档内容长度是否符合要求
        if len(doc.text) < config["outline"]["minimum_content_length"]:
            continue  # Skip documents shorter than the configuration item / 跳过短于配置项的文档

        outline_docs[str(doc.id)] = {
            "title": doc.title,
            "url": doc.url,
            "text": doc.text,
            "updated_at": doc.updated_at,
        }

# Get all documents from RAGFlow / 获取RAGFlow中的所有文档
rag_datasets = theRAG.list_datasets(id=config["ragflow"]["target_data_set"])
rag_target_dataset = rag_datasets[0]
rag_docs_in_target_dataset = get_all_documents_from_ragflow_dataset(rag_target_dataset)
rag_docs_dict = {doc.id: doc for doc in rag_docs_in_target_dataset}

# Process document mapping / 处理文档映射
for outline_doc_id, outline_doc in outline_docs.items():
    str_outline_doc_id = str(
        outline_doc_id
    )  # Ensure outline_doc_id is a string / 确保 outline_doc_id 是字符串
    dbCursor.execute(
        "SELECT * FROM document_mapping WHERE outline_doc_id = ?",
        (str_outline_doc_id,),
    )
    row = dbCursor.fetchone()
    if row is None:
        # Only exists in outline: mark as "待更新" in the database / 只有outline中存在：在数据库中标记为“待更新”
        dbCursor.execute(
            "INSERT INTO document_mapping (outline_doc_id, status) VALUES (?, ?)",
            (str_outline_doc_id, "待更新"),
        )
    else:
        ragflow_doc_id, _, last_updated, status = row
        if status == "上游已删除":
            # Marked as "上游已删除" in the database, but exists in outline: update status to "待更新" / 数据库中标记为“上游已删除”，但outline中存在：更新状态为“待更新”
            dbCursor.execute(
                "UPDATE document_mapping SET status = ? WHERE outline_doc_id = ?",
                ("待更新", str_outline_doc_id),
            )
        else:
            # Exists in both database and outline: check update time / 数据库和outline中均存在：检查更新时间
            if last_updated is None or (
                outline_doc["updated_at"] > datetime.fromisoformat(last_updated)
            ):
                dbCursor.execute(
                    "UPDATE document_mapping SET status = ? WHERE outline_doc_id = ?",
                    ("待更新", str_outline_doc_id),
                )

# Get all document mappings from the database / 获取数据库中所有文档映射
dbCursor.execute("SELECT * FROM document_mapping")
dbRows = dbCursor.fetchall()

# Process documents marked as "上游已删除" / 处理“上游已删除”的文档
if config["ragflow"]["delete_non_upstream"]:
    delete_ids = [row[0] for row in dbRows if row[3] == "上游已删除"]
    if delete_ids:
        rag_target_dataset.delete_documents(ids=delete_ids)
        # Do not delete records in the database / 数据库中的记录不删除
        # cursor.execute("DELETE FROM document_mapping WHERE status = ?", ("上游已删除",))

# Process documents marked as "待更新" / 处理“待更新”的文档
for row in dbRows:
    ragflow_doc_id, outline_doc_id, last_updated, status = row
    doc_exist_in_ragflow = ragflow_doc_id in rag_docs_dict.keys()
    if (status == "待更新") or (
        not doc_exist_in_ragflow
    ):  # 待更新，或 ragflow 侧数据被删除 / To be updated, or data deleted on ragflow side
        outline_doc = outline_docs[outline_doc_id]

        if ragflow_doc_id and doc_exist_in_ragflow:
            # Delete the existing corresponding document in ragflow / 删除ragflow中的已有对应文档
            rag_target_dataset.delete_documents(
                ids=[str(ragflow_doc_id)]
            )  # Ensure ragflow_doc_id is a string / 确保 ragflow_doc_id 是字符串
        # Upload a new document based on the text member of the outline Document / 上传基于outline Document 的 text 成员的新文档
        file_content = outline_doc["text"].encode("utf-8")
        doclist = rag_target_dataset.upload_documents(
            [
                {
                    "display_name": outline_doc["title"]
                    + ".md",  # Custom display name / 自定义显示名称
                    "blob": file_content,  # Binary file content / 二进制文件内容
                }
            ]
        )
        new_ragflow_doc_id = doclist[0].id
        # Update the ragflow document ID and update timestamp in the database / 更新数据库中记录的 ragflow 侧的文档 ID 和更新数据时间字段
        dbCursor.execute(
            """
            UPDATE document_mapping
            SET ragflow_doc_id = ?, last_updated = ?, status = ?
            WHERE outline_doc_id = ?
        """,
            (
                str(new_ragflow_doc_id),
                outline_doc["updated_at"].isoformat(),
                "已更新",
                str(outline_doc_id),
            ),  # Ensure new_ragflow_doc_id and outline_doc_id are strings / 确保 new_ragflow_doc_id 和 outline_doc_id 是字符串
        )

        # Update metadata / 更新元数据
        docObjs = rag_target_dataset.list_documents(id=new_ragflow_doc_id)
        docObj: Document = docObjs[0]
        # Dynamically build metadata based on the number of configuration items under ["meta_map"] / 基于 ["meta_map"]配置项下有多少个配置项，动态构建元数据
        new_metadata = {}
        crtOutlineDocObj = theOutline.documents.info(doc_id=outline_doc_id)
        for propName in config["meta_map"]:
            new_metadata[config["meta_map"][propName]] = get_outline_doc_meta(
                propName, crtOutlineDocObj, config["outline"]["outline_url"]
            )
        docObj.update({"meta_fields": new_metadata})

        # New: If auto_start_parse is True in the configuration file, call async_parse_documents / 新增：如果配置文件中 auto_start_parse 为 True，则调用 async_parse_documents
        if config["ragflow"]["auto_start_parse"]:
            rag_target_dataset.async_parse_documents([new_ragflow_doc_id])
            print(f"Async parsing initiated for document ID: {new_ragflow_doc_id}")

dbConn.commit()
dbConn.close()
