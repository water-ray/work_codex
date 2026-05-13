# 项目 Skill 模板

```markdown
---
name: <project-slug>-project
description: 维护 <项目名> 的 Codex 项目上下文。用于修改项目结构、添加模块、运行验证、更新文档、处理构建/测试/发布流程，以及需要理解该项目目录和长期约束的任务。
---

# <项目名> Project

## 入口

- 先读 `<关键 README 或文档>`。
- 关键源码目录：`<path>`。
- 关键脚本目录：`scripts/<用途>/`。
- 临时输出：`temp/`。
- 最终产物：`Bin/<项目>/`。

## 工作流

1. 确认用户请求属于结构、功能、脚本、文档、验证还是发布。
2. 读取对应入口文件和已有文档。
3. 按项目现有风格修改，保持范围最小。
4. 执行最小必要验证。
5. 同步更新 README、docs、任务或 skill 引用。

## 命名与规范

- 项目 slug：`<project-slug>`。
- 子项目 slug：`<subproject-slug>`，仅使用小写字母、数字和连字符。
- 新增子项目时，同步创建或更新 `<project-slug>-<subproject-slug>-project`。
- 新增稳定功能或复杂工作流时，同步创建或更新功能 skill 或任务 skill。
- 根目录 `README.md` 可按项目需要组织；开发规范以 `AGENTS.md` 和 `.codex/skills/` 为准。

## 命令

```powershell
<验证命令>
```

## 约束

- <项目特有约束>
- <兼容性或安全边界>
```
