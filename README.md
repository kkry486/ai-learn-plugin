# AI Learn Plugin — Claude Code 插件

**AI 辅助学习系统**，基于费曼学习法 + 递进式自测的五步学习闭环。

## 一句话简介

输入一个想学的主题，AI 引导你完成：**概念地图 → 费曼解释 → 自测检验 → 关联内化 → 巩固总结**。不止"看过"，而是"真正掌握"。

## 安装

```bash
# 方式一：通过 Plugin Marketplace（推荐）
/plugin marketplace add kkry486/ai-learn-plugin
/plugin install ai-learn

# 方式二：本地开发模式
# 将本仓库 clone 到本地，然后：
/plugin install /path/to/ai-learn-plugin
```

## 依赖

```bash
pip install chromadb
```

Chroma 是**可选的**——不安装时，知识库搜索回退到 SQLite 关键词匹配。

## 使用

```
/learn C++ 移动语义
```

然后跟着 AI 引导走。每步都有确认点，你可以随时修正方向。

## 工作流

```
输入主题
    ↓
步骤1：概念地图（联网搜索 + 拆解为依赖树）
    ↓ [AskUserQuestion: 继续/重来/修改意见]
步骤2：费曼解释（用类比、从 WHY 开始）
    ↓ [逐概念确认]
步骤3：递进式自测（理解→应用→边界三层问题）
    ↓ [标注薄弱点]
步骤4：关联内化（检索知识库中相关主题，对比分析）
    ↓
步骤5：巩固总结（核心公式 + 关键词 + 类比）
    ↓
知识持久化（SQLite + Chroma 向量库）
```

## 项目结构

```
ai-learn-plugin/
├── plugin.json                  # 插件清单
├── .claude/
│   ├── agents/
│   │   └── learn-agent.md       # Agent 核心定义
│   ├── commands/
│   │   └── learn.md             # /learn 命令入口
│   └── skills/
│       └── learn/
│           ├── SKILL.md         # 技能入口
│           └── templates/       # 五步提示模板
├── knowledge_store/
│   ├── store.py                 # SQLite + Chroma 存储引擎
│   └── __init__.py
└── README.md
```

## 知识存储

- **SQLite** (~/.ai-learn/knowledge/learning.db)：结构化学习记录
- **Chroma** (~/.ai-learn/knowledge/chroma/)：向量嵌入，支持跨主题语义检索

## 特性

- ✅ 五步学习闭环，不止被动阅读
- ✅ 每步有交互确认，人类始终在循环中
- ✅ 三层递进自测（理解/应用/边界），暴露真实漏洞
- ✅ 知识自动持久化，学新主题时自动关联已有知识
- ✅ 联网搜索保障知识准确性和时效性
- ✅ 完全离线可用（Chromadb 可选）

## 路线图

- [ ] v0.2：支持本地文件作为知识源（PDF、Markdown）
- [ ] v0.3：间隔复习提醒（Spaced Repetition）
- [ ] v0.4：知识图谱可视化导出
- [ ] v0.5：Web UI（独立于 Claude Code）

## 协议

MIT
