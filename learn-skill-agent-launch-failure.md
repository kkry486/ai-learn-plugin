# 项目问题清单

> 扫描日期：2026-06-10
> 扫描范围：全项目文件及相关配置
> 扫描方式：Claude Code 手动审查

---

## 目录

1. [🔴 Agent 启动 API 参数冲突](#1--agent-启动-api-参数冲突)
2. [🔴 敏感信息已提交到仓库](#2--敏感信息已提交到仓库)
3. [🟡 缺少依赖管理文件](#3--缺少依赖管理文件)
4. [🟡 CLAUDE.md 与实际项目不匹配](#4--claudemd-与实际项目不匹配)
5. [🟡 store.py 参数解析逻辑脆弱](#5--storepy-参数解析逻辑脆弱)
6. [🔵 CTF 学习路线图双副本不同步风险](#6--ctf-学习路线图双副本不同步风险)

---

## 1 🔴 Agent 启动 API 参数冲突

### 基本信息

| 项目 | 内容 |
|------|------|
| **相关命令** | `/learn 什么是api` |
| **触发方式** | 用户输入 `/learn <topic>` 激活 ai-learn Agent |
| **影响范围** | `/learn` 技能的自动化流程（五步学习闭环），以及任何启动子 Agent 的操作 |

### 报错信息

```
API Error: 400 thinking options type cannot be disabled when reasoning_effort is set
```

### 错误上下文

该错误发生在调用 `Agent` 工具启动 `ai-learn` 子 Agent 时。Agent 的 `description` 为 `学习API概念-五步闭环`，`subagent_type` 为 `ai-learn`。

```
agentId: aaaf2b885050612a5
usage: subagent_tokens: 0, tool_uses: 3, duration_ms: 12892
```

### 问题描述

当用户输入 `/learn 什么是api` 后，系统正确解析了技能调用并尝试启动 `ai-learn` Agent 来执行五步学习闭环。然而，Agent 子进程在初始化阶段即返回 HTTP 400 错误，导致 Agent 未能成功启动。

**影响结果：**
- Agent 自动化流程中断
- 五步学习闭环未能由 Agent 自动执行
- 技能退而求其次：由主对话手动完成了全部学习流程（替代执行）

### 原因分析

#### 根因

API 调用参数中存在**配置冲突**：

```
thinking options type cannot be disabled when reasoning_effort is set
```

#### 冲突参数

| 参数 | 作用 |
|------|------|
| `reasoning_effort` | 控制模型的推理深度（如 `low`、`medium`、`high`） |
| `thinking` | 控制模型的思考模式（启用/禁用思考过程输出） |

**这两个设置在 DeepSeek 的 Anthropic 兼容 API 上互斥**——指定了 `reasoning_effort` 就不能同时禁用 `thinking`，反之亦反。

#### 精确的冲突链路

```
┌─ C:\Users\31328\.claude\settings.json
│  └── "effortLevel": "high"                    ← 导致 API 调用带上 reasoning_effort
│
├─ .claude\agents\learn-agent.md
│  └── model: inherit                           ← 继承父会话的模型配置
│
├─ 环境变量
│  └── ANTHROPIC_MODEL: DeepSeek-V4-flash
│  └── ANTHROPIC_BASE_URL: https://api.deepseek.com/anthropic
│
└─ Agent 工具调用时
   ├─ 发送 reasoning_effort（来自 effortLevel: "high"）
   └─ 发送 thinking: { type: "disabled" }（Agent 框架默认行为）
   └─ → DeepSeek API 返回 400：两个参数冲突
```

**具体链路：**
1. **全局设置** `C:\Users\31328\.claude\settings.json` 中设了 `"effortLevel": "high"` → 所有 API 调用带上 `reasoning_effort: "high"`
2. `ai-learn` Agent 声明 `model: inherit` → 子 Agent 继承父会话的模型和配置
3. Agent 工具启动子 Agent 时，框架同时发送 `thinking` 参数（类型为 `disabled`）
4. 标准 Anthropic API 上这两个参数可以共存，但 **DeepSeek 兼容 API 严格校验了参数互斥性** → HTTP 400

### 相关配置文件

| 文件 | 路径 | 关键内容 |
|------|------|---------|
| 全局设置 | `C:\Users\31328\.claude\settings.json` | `effortLevel: "high"` → 产生 `reasoning_effort` |
| Agent 定义 | `.claude\agents\learn-agent.md` | `model: inherit` → 继承父会话配置 |
| 命令定义 | `.claude\commands\learn.md` | 定义 `/learn` 的触发逻辑 |
| 技能定义 | `.claude\skills\learn\SKILL.md` | 定义五步学习流程 |

### 临时解决方案

Agent 启动失败后，主对话手动接管了学习流程：
1. ✅ 读取五套模板文件
2. ✅ 手动完成概念拆解、费曼讲解、自测、知识关联、总结

局限：缺少联网搜索辅助，完整度不如 Agent 自动化流程。

### 建议修复方向

- **方案 A（推荐）：** 将 `effortLevel: "high"` 改为 `"normal"`，消除 `reasoning_effort` 参数
- **方案 B：** Agent 定义中指定一个不产生冲突的模型，而非用 `inherit`
- **方案 C：** 框架层面适配 DeepSeek API，避免同时发送冲突参数

### 复现步骤

1. 确认 `C:\Users\31328\.claude\settings.json` 中 `effortLevel` 为 `"high"`
2. 在任意会话中输入 `/learn 任意主题`
3. 观察 Agent 启动是否返回 400

---

## 2 🔴 敏感信息已提交到仓库

### 位置

[ctf-learning/wargame passwords.txt](ctf-learning/wargame%20passwords.txt)

### 问题描述

文件中包含 4 条**明文密码**（OverTheWire Bandit 游戏的通关密码）：

```
1. ZjLjTmM6FvvyRnrb2rfNWOZOTa6ip5If
2. 263JGJPfgU6LtdEvgfWU1XP5yac29mFx
3. MNk8KNH3Usiio41PRUEoDFPqfxLPlSmx
4. 2WmrDFRmJIq3IPxneAaMGhap0pFhF3NJ
```

且项目根目录**没有 `.gitignore`** 文件。

### 风险

- 如果日后初始化 git 并提交，这些密码会永久留在 git 历史中
- 即使后续删除文件，历史记录仍可找回
- 缺乏 `.gitignore` 也意味着 `__pycache__/`、`.env` 等不应提交的文件可能被误提交

### 建议

1. 创建 `.gitignore`，包含至少：
   ```
   __pycache__/
   *.pyc
   .env
   *.txt
   ```
2. 密码改用环境变量或 `.env` 管理
3. 如果已经有过提交，需要考虑清理 git 历史

---

## 3 🟡 缺少依赖管理文件

### 位置

项目根目录

### 问题描述

`knowledge_store/store.py` 依赖 `chromadb`，`commands/learn.md` 中让用户手动执行：

```bash
pip install chromadb sqlite3
```

但项目存在以下缺失：

| 文件 | 是否存在 | 影响 |
|------|:--------:|------|
| `requirements.txt` | ❌ | 无法复现依赖版本 |
| `pyproject.toml` | ❌ | 无法做标准包管理 |
| `.gitignore` | ❌ | 无排除规则 |

### 风险

- `chromadb` 大版本升级可能导致 API 不兼容，没有锁文件约束版本
- 新环境搭建依赖"人肉记住要装什么"
- `sqlite3` 是 Python 标准库，`pip install sqlite3` 会报错（正确做法是不需要装）

### 建议

```txt
# requirements.txt
chromadb>=0.4.0
```

---

## 4 🟡 CLAUDE.md 与实际项目不匹配

### 位置

`CLAUDE.md`

### 问题描述

CLAUDE.md 的内容**通篇是前端设计规范**：

- OKLCH 色彩空间
- CSS 自定义属性设计令牌
- BEM 命名规范
- 字体配对策略
- UI 组件 loading/empty/error 状态

但该项目实际是 **CTF 学习路线 + AI 辅助学习知识库**，**零前端代码**。

### 风险

- 每次 Claude 启动都会加载这些规范，消耗上下文但毫无助益
- 新接手项目的人会被误导，以为这是个前端项目
- 如果有人按这个规范提交前端代码，反而违背项目实际方向

### 建议

重写 CLAUDE.md 反映项目的实际内容：
- CTF 学习路线维护规范
- AI 辅助学习技能的配置说明
- 知识库（store.py）的使用指南
- 文档和问题报告的提交规范

---

## 5 🟡 store.py 参数解析逻辑脆弱

### 位置

`knowledge_store/store.py` 第 292-306 行

### 问题代码

```python
def _parse_args(argv: list[str]) -> dict[str, str]:
    result = {}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--"):
            key = argv[i]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                result[key] = argv[i + 1]
                i += 2
            else:
                result[key] = ""
                i += 1
        else:
            i += 1
    return result
```

### 问题明细

| # | 问题 | 示例 | 后果 |
|---|------|------|------|
| 1 | 不支持带空格的值 | `--topic "SQL 注入"` → 只拿到 `SQL` | 搜索/保存主题名被截断 |
| 2 | 无法区分空值和下一个参数 | `--topic --keywords` → topic 被赋值为 `""` | 静默丢失参数 |
| 3 | `save` 中 notes_file 回退逻辑有歧义 | 文件路径不存在时，把路径字符串当内容用 | 存入脏数据 |

### 建议

- 用 `argparse` 标准库替换手写解析器
- 或至少处理引号包裹的值

---

## 6 🔵 CTF 学习路线图双副本不同步风险

### 位置

`ctf-learning/` 目录

### 问题描述

该目录下有两个内容重复的文件：

| 文件 | 大小 | 生成方式 |
|------|------|----------|
| `CTF_WEB_学习路线图.md` | Markdown 源文件 | 手工编写 |
| `CTF_WEB_学习路线图.html` | HTML 渲染版 | 推测由工具转换生成 |

### 风险

- 修改时只改了一个文件，两版本会不同步
- 没有构建脚本或说明标注哪个是源文件、HTML 如何生成
- HTML 文件体积较大，不适合版本管理

### 建议

- 确定 `.md` 为源文件，`.html` 为构建产物
- 将 `.html` 加入 `.gitignore`
- 或保留 HTML 但添加 `README.md` 说明两者关系

---

## 严重度分布

| # | 问题 | 严重度 | 类型 |
|---|------|--------|------|
| 1 | Agent 启动 API 参数冲突 | 🔴 **高** | Bug / 配置冲突 |
| 2 | 明文密码 + 无 .gitignore | 🔴 **高** | 安全风险 |
| 3 | 缺少依赖管理文件 | 🟡 中 | 工程规范 |
| 4 | CLAUDE.md 与项目不匹配 | 🟡 中 | 文档误导 |
| 5 | store.py 参数解析脆弱 | 🟡 中 | 潜在 Bug |
| 6 | HTML/MD 双副本不同步风险 | 🔵 低 | 维护成本 |

---

*文档维护：发现新问题时追加到本清单，修复后标记为「已修复」并注明修复日期。*
