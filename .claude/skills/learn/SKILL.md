---
name: learn
description: AI 辅助学习技能。当用户表示想学习某个概念、技术、主题，或输入 /learn 命令时激活。基于费曼学习法构建的完整五步学习闭环。
context: fork
---

# AI 辅助学习技能

## 触发条件

- 用户输入 `/learn [主题]`
- 用户说"我想学X"、"帮我理解X"、"教我X"（且 X 有一定复杂度，不是简单定义）

## 不触发的场景

- "X是什么"（简单解释，用普通对话）
- "帮我查一下X"（信息查询，不是学习）
- "总结一下这篇文章"（内容总结，不是学习）

## 工作流

1. 激活 `ai-learn` Agent
2. Agent 自动执行五步闭环（详见 Agent 定义）
3. 学习结果自动持久化到知识库

## 模板文件

- `templates/concept-map.md` → 步骤1
- `templates/feynman.md` → 步骤2
- `templates/self-test.md` → 步骤3
- `templates/association.md` → 步骤4
- `templates/summary.md` → 步骤5
