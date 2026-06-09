---
description: 启动 AI 辅助学习工作流。输入你想学习的任何主题，AI 将引导你通过五步闭环（概念地图→费曼解释→自测检验→关联内化→巩固总结）真正掌握它。
allowed-tools: Read, Write, Bash(ai-learn-plugin/knowledge_store/*), WebSearch, AskUserQuestion, Glob
---

启动 AI 辅助学习系统，激活 ai-learn Agent。

用户想学习的主题是：$ARGUMENTS

如果用户没有提供主题，请友好地询问用户想学习什么内容。
如果用户提供了主题，直接调用 ai-learn Agent 开始五步学习工作流。

在执行工作流之前，首先检查 knowledge_store 目录是否有 store.py，如果没有，
告知用户需要先安装依赖：`pip install chromadb sqlite3`
然后继续执行工作流（第一次使用知识库为空，步骤4跳过关联检索即可）。
