# AI Learn — Claude Code 学习插件

> 输入一个主题，AI 引导你真正掌握它。不止"看过"，而是"学会"。

## 快速开始

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/kkry486/ai-learn-plugin.git

# 2. 复制到你的 Claude Code 项目
cp -r ai-learn-plugin/.claude/*  你的项目路径/.claude/
cp -r ai-learn-plugin/knowledge_store  你的项目路径/

# 3. 安装依赖（可选，跳过则知识关联回退到关键词匹配）
pip install chromadb
```

### 使用

在 Claude Code 里输入：

```
/learn C++ 移动语义
```

AI 会引导你走完五步：**概念地图 → 费曼解释 → 自测检验 → 关联内化 → 巩固总结**。每一步都有确认点，不满意随时修改。

AI 会引导你走完五步：**概念地图 → 费曼解释 → 自测检验 → 关联内化 → 巩固总结**。每一步都有确认点，不满意随时修改。

## 工作流

```
/learn 你想学的主题
        ↓
步骤1  概念地图 —— AI 联网搜索，拆解为 5-8 个子概念的依赖树
        ↓   [你确认：继续 / 重来 / 提修改意见]
步骤2  费曼解释 —— 从 WHY 开始，用日常类比，逐概念讲解
        ↓   [逐概念确认：继续 / 重讲 / 提问]
步骤3  自测检验 —— 三层递进题目（理解 → 应用 → 边界）
        ↓   [逐个回答，AI 点评，标注薄弱点]
步骤4  关联内化 —— 检索你学过的知识，和新概念对比
        ↓
步骤5  巩固总结 —— 生成精华笔记，存到知识库
        ↓
知识已保存，下次学相关主题时自动关联。
```

## 常见问题

**Q: 和直接问 Claude "解释一下 XX" 有什么区别？**

直接问是被动接收信息。这个插件强制你经历"输出检验"——费曼解释逼迫你用自己的话理解，三层自测暴露你以为懂了但实际没懂的地方。

**Q: 学习记录存哪里？**

`~/.ai-learn/knowledge/` 目录下：
- SQLite 数据库存结构化记录（主题、薄弱点、关键词）
- Chroma 向量库存语义嵌入（学新主题时自动检索关联）

**Q: 不装 chromadb 能用吗？**

能。只是跨主题关联时会用 SQLite 关键词匹配代替向量语义搜索，效果差别不大。

**Q: 怎么查看以前学过的东西？**

直接问 Claude："我之前学过哪些主题？" 或 "回顾一下我之前学的 XX"。

## 项目结构

```
├── plugin.json                    # 插件清单
├── marketplace.json               # 插件市场索引
├── .claude/
│   ├── agents/learn-agent.md      # Agent 核心（五步工作流规则）
│   ├── commands/learn.md          # /learn 命令入口
│   └── skills/learn/
│       ├── SKILL.md               # 技能定义
│       └── templates/             # 五个步骤的提示模板
├── knowledge_store/
│   └── store.py                   # SQLite + Chroma 存储引擎
└── README.md
```

## 路线图

- [ ] v0.2：支持 PDF / Markdown 本地文件作为知识源
- [ ] v0.3：间隔复习提醒（Spaced Repetition）
- [ ] v0.4：知识图谱可视化导出
- [ ] v0.5：独立 Web UI

## 协议

MIT
