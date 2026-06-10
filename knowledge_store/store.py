"""AI Learn 知识库存储引擎

基于 SQLite + Chroma 实现：
- SQLite:  结构化数据（主题名、学习日期、薄弱点、关键词、笔记文本）
- Chroma:  向量嵌入（用于跨主题语义检索关联）
- 存储路径: ~/.ai-learn/knowledge/
"""

import sqlite3
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path


STORAGE_DIR = Path.home() / ".ai-learn" / "knowledge"
DB_PATH = STORAGE_DIR / "learning.db"
CHROMA_PATH = STORAGE_DIR / "chroma"


def ensure_dirs():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)


def get_db():
    ensure_dirs()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS learning_records (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            topic       TEXT    NOT NULL,
            notes       TEXT    NOT NULL,
            keywords    TEXT    NOT NULL DEFAULT '',
            weak_points TEXT    NOT NULL DEFAULT '',
            concept_map TEXT    NOT NULL DEFAULT '',
            created_at  TEXT    NOT NULL,
            updated_at  TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS concepts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id   INTEGER NOT NULL,
            name        TEXT    NOT NULL,
            difficulty  TEXT    NOT NULL DEFAULT '中等',
            mastery     TEXT    NOT NULL DEFAULT '未测试',
            FOREIGN KEY (record_id) REFERENCES learning_records(id)
        );
        CREATE INDEX IF NOT EXISTS idx_records_topic ON learning_records(topic);
        CREATE INDEX IF NOT EXISTS idx_records_created ON learning_records(created_at);
        CREATE INDEX IF NOT EXISTS idx_concepts_record ON concepts(record_id);
    """)
    conn.commit()
    conn.close()


def save_learning_record(
    topic: str,
    notes: str,
    keywords: str = "",
    weak_points: str = "",
    concept_map: str = "",
):
    """保存一条学习记录"""
    init_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()

    conn.execute(
        """INSERT INTO learning_records
           (topic, notes, keywords, weak_points, concept_map, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (topic, notes, keywords, weak_points, concept_map, now, now),
    )
    conn.commit()
    record_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # 存储到 Chroma 向量库
    if _chroma_available():
        _save_to_chroma(record_id, topic, notes, keywords)

    conn.close()
    return record_id


def save_notes_to_file(notes: str) -> Path:
    """将笔记写入临时文件，供 Agent 使用"""
    ensure_dirs()
    filepath = STORAGE_DIR / f"notes_{datetime.now().strftime('%Y%m%d%H%M%S')}.md"
    filepath.write_text(notes, encoding="utf-8")
    return filepath


def search_by_keyword(query: str, limit: int = 5) -> list[dict]:
    """关键词搜索已学主题"""
    init_db()
    conn = get_db()
    rows = conn.execute(
        """SELECT topic, keywords, weak_points, created_at
           FROM learning_records
           WHERE topic LIKE ? OR keywords LIKE ?
           ORDER BY created_at DESC
           LIMIT ?""",
        (f"%{query}%", f"%{query}%", limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_semantic(query: str, limit: int = 5) -> list[dict]:
    """语义搜索已学主题（基于向量相似度）"""
    if not _chroma_available():
        return search_by_keyword(query, limit)

    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    try:
        collection = client.get_collection("learning_embeddings")
    except Exception:
        return search_by_keyword(query, limit)

    results = collection.query(
        query_texts=[query],
        n_results=min(limit, collection.count()),
    )

    if not results["ids"] or not results["ids"][0]:
        return search_by_keyword(query, limit)

    init_db()
    conn = get_db()
    records = []
    for doc_id in results["ids"][0]:
        row = conn.execute(
            "SELECT topic, keywords, weak_points, created_at FROM learning_records WHERE id = ?",
            (int(doc_id),),
        ).fetchone()
        if row:
            d = dict(row)
            idx = results["ids"][0].index(doc_id)
            if results["distances"] and idx < len(results["distances"][0]):
                d["distance"] = results["distances"][0][idx]
            records.append(d)
    conn.close()
    return records


def list_all_topics() -> list[dict]:
    """列出所有已学主题"""
    init_db()
    conn = get_db()
    rows = conn.execute(
        "SELECT topic, keywords, created_at FROM learning_records ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_topic_notes(topic: str) -> dict | None:
    """获取某个主题的学习笔记"""
    init_db()
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM learning_records WHERE topic = ? ORDER BY created_at DESC LIMIT 1",
        (topic,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _chroma_available() -> bool:
    try:
        import chromadb
        return True
    except ImportError:
        return False


def _save_to_chroma(record_id: int, topic: str, notes: str, keywords: str):
    """将学习内容存入 Chroma 向量库"""
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        return

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    try:
        collection = client.get_collection("learning_embeddings")
    except Exception:
        collection = client.create_collection("learning_embeddings")

    text_to_embed = f"{topic}\n{keywords}\n{notes[:2000]}"  # 截断避免太长

    collection.upsert(
        ids=[str(record_id)],
        documents=[text_to_embed],
        metadatas=[{
            "topic": topic,
            "keywords": keywords,
        }],
    )


# ═══════════════════════════════════════════════════
#  CLI 入口（供 Agent 通过 Bash 调用）
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="AI Learn 知识库存储引擎")
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    p_save = subparsers.add_parser("save")
    p_save.add_argument("--topic", required=True)
    p_save.add_argument("--notes-file", default="")
    p_save.add_argument("--keywords", default="")
    p_save.add_argument("--weak-points", default="")
    p_save.add_argument("--concept-map", default="")

    p_search = subparsers.add_parser("search")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--limit", type=int, default=5)

    subparsers.add_parser("list")
    p_get = subparsers.add_parser("get")
    p_get.add_argument("--topic", required=True)
    subparsers.add_parser("init")

    args = parser.parse_args()

    if args.cmd == "save":
        notes = ""
        if args.notes_file and Path(args.notes_file).exists():
            notes = Path(args.notes_file).read_text(encoding="utf-8")
        elif args.notes_file:
            notes = args.notes_file

        rid = save_learning_record(
            topic=args.topic,
            notes=notes,
            keywords=args.keywords,
            weak_points=getattr(args, "weak-points", ""),
            concept_map=getattr(args, "concept-map", ""),
        )
        print(json.dumps({"status": "ok", "record_id": rid}))

    elif args.cmd == "search":
        results = search_semantic(args.query, args.limit)
        print(json.dumps(results, ensure_ascii=False, indent=2))

    elif args.cmd == "list":
        results = list_all_topics()
        print(json.dumps(results, ensure_ascii=False, indent=2))

    elif args.cmd == "get":
        record = get_topic_notes(args.topic)
        if record:
            print(json.dumps(record, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"status": "not_found", "topic": args.topic}))

    elif args.cmd == "init":
        init_db()
        print(json.dumps({"status": "ok", "db_path": str(DB_PATH)}))


if __name__ == "__main__":
    main()
