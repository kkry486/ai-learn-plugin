"""AI Learn 知识库存储引擎

基于 SQLite + Chroma 实现：
- SQLite:  结构化数据（主题名、学习日期、薄弱点、关键词、笔记文本）
- Chroma:  向量嵌入（用于跨主题语义检索关联）
- 存储路径: ~/.ai-learn/knowledge/
"""

import sqlite3
import json
import argparse
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[ai-learn] %(levelname)s: %(message)s")
logger = logging.getLogger("ai-learn")

STORAGE_DIR = Path.home() / ".ai-learn" / "knowledge"
DB_PATH = STORAGE_DIR / "learning.db"
CHROMA_PATH = STORAGE_DIR / "chroma"

_db_initialized = False


def ensure_dirs():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_db():
    """上下文管理器，确保连接正确关闭"""
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """初始化数据库（仅首次调用执行）"""
    global _db_initialized
    if _db_initialized:
        return
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS learning_records (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                topic       TEXT    NOT NULL UNIQUE,
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
            CREATE INDEX IF NOT EXISTS idx_records_topic
                ON learning_records(topic);
            CREATE INDEX IF NOT EXISTS idx_records_created
                ON learning_records(created_at);
            CREATE INDEX IF NOT EXISTS idx_concepts_record
                ON concepts(record_id);
        """)
    _db_initialized = True
    logger.info("数据库初始化完成: %s", DB_PATH)


def save_learning_record(
    topic: str,
    notes: str,
    keywords: str = "",
    weak_points: str = "",
    concept_map: str = "",
) -> int:
    """保存学习记录。同主题重复学习时更新已有记录。"""
    init_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM learning_records WHERE topic = ?", (topic,)
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE learning_records
                   SET notes = ?, keywords = ?, weak_points = ?,
                       concept_map = ?, updated_at = ?
                   WHERE id = ?""",
                (notes, keywords, weak_points, concept_map, now, existing["id"]),
            )
            record_id = existing["id"]
            logger.info("更新已有记录: %s (id=%d)", topic, record_id)
        else:
            conn.execute(
                """INSERT INTO learning_records
                   (topic, notes, keywords, weak_points, concept_map, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (topic, notes, keywords, weak_points, concept_map, now, now),
            )
            record_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            logger.info("新增记录: %s (id=%d)", topic, record_id)

    if _chroma_available():
        _save_to_chroma(record_id, topic, notes, keywords)

    return record_id


def save_notes_to_file(notes: str) -> Path:
    """将笔记写入文件，返回文件路径"""
    ensure_dirs()
    filepath = STORAGE_DIR / f"notes_{datetime.now().strftime('%Y%m%d%H%M%S')}.md"
    filepath.write_text(notes, encoding="utf-8")
    return filepath


def _escape_like(value: str) -> str:
    """转义 SQL LIKE 中的通配符 % 和 _"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_by_keyword(query: str, limit: int = 5) -> list[dict]:
    """关键词搜索已学主题"""
    init_db()
    escaped = _escape_like(query)
    with get_db() as conn:
        rows = conn.execute(
            """SELECT topic, keywords, weak_points, created_at
               FROM learning_records
               WHERE topic LIKE ? ESCAPE '\\'
                  OR keywords LIKE ? ESCAPE '\\'
               ORDER BY created_at DESC
               LIMIT ?""",
            (f"%{escaped}%", f"%{escaped}%", limit),
        ).fetchall()
    return [dict(r) for r in rows]


def search_semantic(query: str, limit: int = 5) -> list[dict]:
    """语义搜索已学主题（基于向量相似度，不可用时降级为关键词搜索）"""
    if not _chroma_available():
        return search_by_keyword(query, limit)

    import chromadb

    try:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    except Exception as e:
        logger.warning("Chroma 客户端创建失败，降级到关键词搜索: %s", e)
        return search_by_keyword(query, limit)

    try:
        collection = client.get_collection("learning_embeddings")
    except Exception as e:
        logger.warning("Chroma 集合不存在，降级到关键词搜索: %s", e)
        return search_by_keyword(query, limit)

    count = collection.count()
    if count == 0:
        logger.info("Chroma 集合为空，降级到关键词搜索")
        return search_by_keyword(query, limit)

    try:
        results = collection.query(
            query_texts=[query],
            n_results=min(limit, count),
        )
    except Exception as e:
        logger.warning("Chroma 查询失败，降级到关键词搜索: %s", e)
        return search_by_keyword(query, limit)

    if not results["ids"] or not results["ids"][0]:
        return []

    init_db()
    records = []
    with get_db() as conn:
        for doc_id in results["ids"][0]:
            row = conn.execute(
                "SELECT topic, keywords, weak_points, created_at "
                "FROM learning_records WHERE id = ?",
                (int(doc_id),),
            ).fetchone()
            if row:
                d = dict(row)
                idx = results["ids"][0].index(doc_id)
                if results["distances"] and idx < len(results["distances"][0]):
                    d["distance"] = results["distances"][0][idx]
                records.append(d)
    return records


def list_all_topics() -> list[dict]:
    """列出所有已学主题"""
    init_db()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT topic, keywords, created_at FROM learning_records "
            "ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_topic_notes(topic: str) -> dict | None:
    """获取某个主题的学习笔记"""
    init_db()
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM learning_records WHERE topic = ? "
            "ORDER BY updated_at DESC LIMIT 1",
            (topic,),
        ).fetchone()
    return dict(row) if row else None


def _chroma_available() -> bool:
    try:
        import chromadb  # noqa: F401
        return True
    except ImportError:
        logger.info("chromadb 未安装，使用关键词搜索")
        return False


def _save_to_chroma(record_id: int, topic: str, notes: str, keywords: str):
    """将学习内容存入 Chroma 向量库"""
    try:
        import chromadb
    except ImportError:
        return

    try:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    except Exception as e:
        logger.warning("Chroma 客户端创建失败，跳过向量存储: %s", e)
        return

    try:
        collection = client.get_collection("learning_embeddings")
    except Exception:
        try:
            collection = client.create_collection("learning_embeddings")
            logger.info("Chroma 集合已创建")
        except Exception as e:
            logger.warning("Chroma 集合创建失败，跳过向量存储: %s", e)
            return

    text_to_embed = f"{topic}\n{keywords}\n{notes[:2000]}"

    try:
        collection.upsert(
            ids=[str(record_id)],
            documents=[text_to_embed],
            metadatas=[{"topic": topic, "keywords": keywords}],
        )
        logger.info("Chroma 向量已存储: topic=%s", topic)
    except Exception as e:
        logger.warning("Chroma upsert 失败: %s", e)


# ═══════════════════════════════════════════════════
#  CLI 入口（供 Agent 通过 Bash 调用）
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="AI Learn 知识库存储引擎")
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    p_save = subparsers.add_parser("save")
    p_save.add_argument("--topic", required=True)
    p_save.add_argument("--notes", default="")
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
        # 优先使用 --notes 直接传文本；其次用 --notes-file 读文件
        notes = args.notes
        if not notes and args.notes_file:
            filepath = Path(args.notes_file)
            if filepath.exists():
                notes = filepath.read_text(encoding="utf-8")
            else:
                print(json.dumps({
                    "status": "error",
                    "message": f"文件不存在: {args.notes_file}"
                }))
                return

        if not notes:
            print(json.dumps({
                "status": "error",
                "message": "请提供 --notes 或 --notes-file"
            }))
            return

        rid = save_learning_record(
            topic=args.topic,
            notes=notes,
            keywords=args.keywords,
            weak_points=args.weak_points,   # argparse 自动将 --weak-points → weak_points
            concept_map=getattr(args, "concept_map"),   # argparse 自动将 --concept-map → concept_map
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
