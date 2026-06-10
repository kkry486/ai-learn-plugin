# AI Learn 插件 — 代码审查报告

> 审查日期：2026-06-10
> 审查范围：`.claude/skills/learn/`、`.claude/agents/learn-agent.md`、`.claude/commands/learn.md`、`knowledge_store/`
> 审查方式：静态代码分析 + 架构评估

---

## 总体评分

| 维度 | 评分 | 简要说明 |
|:----|:----:|:---------|
| 架构设计 | ★★★★☆ | 五步闭环思路清晰，模板分离设计优秀，但层间耦合有隐患 |
| 代码质量 | ★★★☆☆ | 有设计感，但参数传递、异常处理等细节疏忽较多 |
| 可靠性 | ★★★☆☆ | 异常处理不完整，边界情况覆盖不足 |
| 安全性 | ★★★★☆ | 本地工具可接受，但存在 SQL 注入隐患 |
| 可维护性 | ★★★★☆ | 结构清晰，模板分离好，便于扩展 |
| 跨平台 | ★★☆☆☆ | 大量 Linux 假设，Windows 下完全不可用 |

**总体评级：★★★☆☆ — "可用，但需修复"**

设计质量远高于实现质量。教学流程设计（五步闭环 + 模板分离）是亮点，但具体代码实现存在多处中高风险缺陷。

---

## 一、⚠️ 高风险问题（必须修复）

### H1. Windows 不兼容 — `/tmp/` 硬编码

**文件**：[learn-agent.md](.claude/agents/learn-agent.md) 第 101 行

```yaml
python knowledge_store/store.py save \
  --notes-file /tmp/learn-notes.md \
```

**问题**：Windows 系统中不存在 `/tmp/` 目录，该路径写入必定失败。

**影响**：所有 Windows 用户无法完成"保存到知识库"这一关键步骤。

**建议修复**：使用平台无关的临时文件路径，例如 Python 的 `tempfile.gettempdir()`，或在 Bash 命令中通过 `%TEMP%` 环境变量获取。

---

### H2. `argparse` 参数名与获取名不匹配 — 字段静默丢失

**文件**：[store.py](knowledge_store/store.py) 第 223-253 行

```python
# 定义时使用连字符
p_save.add_argument("--weak-points")
p_save.add_argument("--concept-map")

# 访问时使用连字符 —— 但 argparse 会转成下划线！
weak_points = getattr(args, "weak-points", "")   # ← 永远返回 ""
concept_map = getattr(args, "concept-map", "")    # ← 永远返回 ""
```

**说明**：Python 的 `argparse` 会自动将命令行参数名中的 `-` 替换为 `_`，所以 `--weak-points` 实际存储在 `args.weak_points` 中，而非 `args["weak-points"]`。

**影响**：`weak_points` 和 `concept_map` 两个字段**永远存入空字符串**。用户在 CLI 中传递的 `--weak-points` 和 `--concept-map` 参数被静默丢弃，无报错、无提示。

**建议修复**：将 `getattr` 中的 `"weak-points"` 改为 `"weak_points"`，或定义参数时直接使用 `--weak-points` 并在代码中用 `args.weak_points` 访问（argparse 自动转换）。

---

### H3. `--notes-file` 读取失败的 fallback 行为导致数据损坏

**文件**：[store.py](knowledge_store/store.py) 第 242-246 行

```python
notes = ""
if args.notes_file and Path(args.notes_file).exists():
    notes = Path(args.notes_file).read_text(encoding="utf-8")
elif args.notes_file:
    notes = args.notes_file       # ← 文件不存在时，把路径字符串当作笔记内容！
```

**场景**：当 `--notes-file` 指定的文件不存在时（例如 Windows 下找不到 `/tmp/learn-notes.md`），代码会**将文件路径字符串本身作为笔记内容存入数据库**。

**影响**：知识库中会写入类似 `"/tmp/learn-notes.md"` 这样的脏数据。用户看到的是路径字符串而不是学习笔记，且数据被覆盖后无法恢复。

**建议修复**：当文件不存在时，应打印错误并退出/跳过保存，而不是静默 fallback。

---

### H4. Bash 权限路径与实际项目路径不匹配

**文件**：[learn.md](.claude/commands/learn.md) 第 3 行

```yaml
allowed-tools: Read, Write, Bash(ai-learn-plugin/knowledge_store/*), ...
```

**说明**：Authorized Bash 路径为 `ai-learn-plugin/knowledge_store/*`，但项目中 `store.py` 实际位于 `knowledge_store/store.py`。

**影响**：Agent 执行 `python knowledge_store/store.py ...` 时，Bash 沙箱判定路径不在允许范围内，**命令被拒绝执行**。

**建议修复**：将权限路径修正为 `knowledge_store/*`。

---

### H5. Chroma 空集合查询崩溃

**文件**：[store.py](knowledge_store/store.py) 第 130-133 行

```python
results = collection.query(
    query_texts=[query],
    n_results=min(limit, collection.count()),
)
```

**问题**：首次使用知识库为空时，`collection.count()` 返回 0，`min(limit, 0)` 结果为 0，传入 `n_results=0`。

**影响**：某些 Chroma 版本传入 `n_results=0` 会抛出异常。虽然代码有 `except Exception` 兜底降级到关键词搜索，但异常信息被完全吞噬，排查困难。

**建议修复**：当 `collection.count() == 0` 时，直接返回空结果，不调用 query。

---

## 二、🟡 中风险问题（建议修复）

### M1. 数据库连接未妥善关闭

**文件**：[store.py](knowledge_store/store.py) 多处

**问题**：`get_db()` 每次调用都创建新连接，但连接关闭依赖调用方自觉：

- `search_semantic()` 中 Chroma 查询成功后遍历取 SQLite 记录，如果遍历中间抛出异常，连接不会关闭。
- `save_learning_record()` 在 Chroma 写入前 `conn.close()` 了，但 `_save_to_chroma` 如果抛异常，上层调用者不知道连接已关。
- 没有使用 `with` 上下文管理器或 `try/finally` 确保连接关闭。

**影响**：长期运行可能导致连接泄露，数据库文件被锁定。

**建议修复**：使用 `contextlib.contextmanager` 封装 `get_db()`，或统一在 `finally` 块中关闭。

---

### M2. `init_db()` 过度调用

**文件**：[store.py](knowledge_store/store.py) 第 33-59 行

**问题**：几乎所有对外函数都先调 `init_db()`：

```python
def save_learning_record(...):
    init_db()      # ← 创建表
    ...
    conn = get_db()  # ← 再开连接
    ...

def search_by_keyword(...):
    init_db()      # ← 每次都 CREATE TABLE IF NOT EXISTS
    ...
```

**影响**：每次读写操作都执行一次 `CREATE TABLE IF NOT EXISTS` 和索引创建语句，虽然 SQLite 不会重复创建，但带来了不必要的文件系统调用和 I/O 开销。

**建议修复**：项目启动或首次导入时只初始化一次，例如放在 `__init__.py` 或使用 lazy init 标记位。

---

### M3. SQL `LIKE` 通配符无规避

**文件**：[store.py](knowledge_store/store.py) 第 106-108 行

```python
WHERE topic LIKE ? OR keywords LIKE ?
```

**问题**：用户输入中的 `%` 和 `_` 在 SQL LIKE 中是通配符。虽然使用了参数化查询避免了 SQL 注入，但搜索行为可能不符合预期：

- 搜索 `"100%"` → 匹配所有以"100"开头的主题
- 搜索 `"test_plugin"` → `_` 匹配任意单个字符

**影响**：搜索结果不准确，用户体验下降。

**建议修复**：对查询字符串中的 `%` 和 `_` 进行转义（`\%`、`\_`），或使用 `ESCAPE` 子句。

---

### M4. Chroma 异常全部静默降级

**文件**：[store.py](knowledge_store/store.py) 第 117-118、127-128、191-193 行

```python
except Exception:
    return search_by_keyword(query, limit)
except Exception:
    collection = client.create_collection("learning_embeddings")
```

**问题**：所有 Chroma 相关异常被宽泛捕获并静默降级：

- Chroma 版本不兼容 → 静默降级到关键词搜索
- Chroma 存储文件损坏 → 静默降级
- 权限不足 → 静默降级

**影响**：异常被隐藏，用户和 Agent 都不知道向量搜索未生效。可能导致步骤4的关联检索质量低于预期。

**建议修复**：区分 `ImportError`（库未安装 → 正常降级）和其他异常（→ 打印 warning 再降级）。

---

### M5. 缺少日志记录

**文件**：[store.py](knowledge_store/store.py) 全文 277 行

**问题**：整个存储引擎没有任何日志输出：

- 数据库初始化成功/失败 → 无记录
- Chroma 异常 → 无记录
- 笔记保存成功 → 无记录
- 查询执行 → 无记录

**建议修复**：使用标准库 `logging` 模块，关键操作输出 INFO 级别日志，异常输出 WARNING/ERROR。

---

### M6. 同一主题多次学习产生重复记录

**文件**：[store.py](knowledge_store/store.py) 第 62-88 行

**问题**：`save_learning_record()` 始终 INSERT，不会检查同一主题是否已存在。`get_topic_notes()` 虽然用 `LIMIT 1` 返回最新一条，但：
- 步骤4的关联检索会返回多条同主题记录
- 知识库中出现多条内容不同的同主题记录，哪条是最新版本不明确

**建议修复**：增加 `ON CONFLICT` 更新机制，或先查询再决定 INSERT 还是 UPDATE。

---

## 三、🟢 低风险 / 优化建议

### L1. `pathlib` 使用不一致

**文件**：[store.py](knowledge_store/store.py)

定义了 `DB_PATH = STORAGE_DIR / "learning.db"` 但后续到处使用 `str(DB_PATH)` 传参给 `sqlite3.connect`。而 `sqlite3.connect` 从 Python 3.4+ 就支持 `pathlib.Path` 对象，无需转字符串。

### L2. 缺少最低 Python 版本声明

- `list[dict]` 类型注解 → Python 3.9+
- `datetime.now(timezone.utc)` → Python 3.x 均可，但建议 `datetime.now(datetime.UTC)`（3.11+）

### L3. Agent 模型策略未实现

[learn-agent.md](.claude/agents/learn-agent.md) 末尾提到步骤3（自测评判）"建议使用较强模型"，但 Agent 定义头部固定 `model: sonnet`，不具备按步骤动态切换模型的能力。

### L4. 笔记文件无清理机制

每次保存笔记生成 `notes_YYYYMMDDHHMMSS.md` 临时文件在 `~/.ai-learn/knowledge/` 下，但这些文件从未被清理，长期运行会积累大量临时文件。

### L5. 类型注解不全

多数函数缺少返回类型注解（`list[dict]` 已标注，但 `save_learning_record`、`_save_to_chroma` 等缺少）；`-> list[dict]` 中的 dict key 类型也未指明。

---

## 四、架构级建议

| 建议 | 说明 | 优先级 |
|:----|:------|:------|
| **全局数据库连接池** | `get_db()` 每次新建连接，高并发下效率低。可改为全局单例或 `with` 上下文管理 | 低 |
| **知识库版本管理** | 同一主题多次学习应能追溯历史变化，而非仅保留多条无关联记录 | 低 |
| **日志系统** | 引入标准 `logging`，关键操作留痕便于排查 | 中 |
| **笔记导出** | 支持 markdown/json 格式导出学习记录 | 低 |
| **模板版本化** | 五步模板可考虑版本控制，兼容旧笔记的渲染 | 低 |

---

## 五、修复优先级建议

| 优先级 | 问题编号 | 预估工时 |
|:------:|:---------|:--------:|
| P0（阻塞性） | H1、H4 | 15 min |
| P0（数据损坏） | H2、H3 | 15 min |
| P1（崩溃风险） | H5 | 10 min |
| P1（可靠性） | M1、M2、M4 | 20 min |
| P2（体验） | M3、M6 | 15 min |
| P3（完善） | M5、L1-L5 | 30 min |

**总计**：约 1.5 小时可修复全部 P0-P2 问题。

---

## 六、亮点回顾

审查虽以问题为主，但项目确有值得肯定的设计：

- **教学流程**：五步闭环（概念地图 → 费曼解释 → 自测 → 关联 → 总结）设计科学，符合认知科学规律
- **模板分离**：将提示词与 Agent 逻辑解耦，便于迭代和复用
- **Chroma 集成**：引入向量语义搜索作为步骤4关联的基础，设计有前瞻性
- **降级策略**：Chroma 不可用时自动降级到关键词搜索，保证了基础功能可用
- **CLI 接口**：通过 argparse 提供 CLI 接口供 Agent 调用，解耦清晰

---

*报告生成时间：2026-06-10 | 审查者：Claude Code（Agent 工程审查）*
