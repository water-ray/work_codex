---
name: codex-skill-generator
description: 为 Codex 项目生成或更新项目 skill、子项目 skill、功能 skill 和任务 skill。用于添加新项目、新子项目、新功能、稳定工作流、专用验证流程，或把零散规则沉淀为可迁移的 .codex/skills 文档。
---

# Codex Skill Generator

## 选择类型

- 项目 skill：描述一个项目或子项目的结构、入口、命令、验证方式和长期约束。
- 功能 skill：描述一个稳定功能域的业务规则、关键文件、修改步骤、测试方式和失败路径。
- 任务 skill：描述可重复执行的仓库任务、发布任务、数据处理任务或工具脚本入口。

## 规范职责

- Skill 文档用于限制可重复执行的开发规范，包括命名、目录、关键入口、修改边界、验证命令、失败路径和任务输出位置。
- 派生项目的根目录 `README.md` 可以自由改写；如果 README 提到开发规范，必须与 `AGENTS.md` 和对应 skill 保持一致。
- 新增项目或子项目时，必须创建或更新项目 skill；新增稳定功能、复杂工作流或专用验证流程时，必须创建或更新功能 skill 或任务 skill。
- 一次性临时需求不写入 skill；只有会复用、会迁移或需要约束后续开发行为的规则才沉淀为 skill。

## 命名规则

- Skill 名称只使用小写字母、数字和连字符，不使用空格、下划线、中文名、大小写混排或重复别名。
- 项目 skill 使用 `<project-slug>-project`。
- 子项目 skill 使用 `<project-slug>-<subproject-slug>-project`。
- 功能 skill 使用 `<project-slug>-<feature-slug>`。
- 任务或工作流 skill 使用 `<scope-slug>-<workflow-slug>`，名称应直接表达触发场景。
- `name`、目录名、`agents/openai.yaml` 中的 `$<skill-name>` 必须一致。

## 生成流程

1. 读取项目上下文：`README.md`、`AGENTS.md`、`docs/`、`scripts/`、`.vscode/tasks.json`、已有 `.codex/skills/`。
2. 判断规则应放入 `AGENTS.md` 还是 skill：始终生效的硬约束放 `AGENTS.md`，按场景触发的流程放 skill。
3. 按命名规则选择 skill 名称，并确认是否需要项目、子项目、功能或任务类型。
4. 在 `.codex/skills/<skill-name>/SKILL.md` 创建或更新内容。
5. Frontmatter 只保留 `name` 和 `description`；`description` 必须说明能力和触发场景。
6. 正文只写 Codex 执行任务需要遵守的规范和知识，避免 README、变更记录、安装说明等旁支文档。
7. 内容接近 500 行或包含大段细节时，把细节放入同目录 `references/`，并在 `SKILL.md` 说明何时读取。
8. 如存在固定模板、脚本或示例资产，放入 `assets/` 或 `scripts/`；不要把生成产物放进 skill 目录。
9. 更新或生成 `agents/openai.yaml`，确保界面描述与 `SKILL.md` 一致。
10. 运行 skill 校验脚本；如果不可用，至少人工检查 YAML frontmatter、名称和路径。

## 模板

- 创建项目 skill 时，读取 `references/project-skill-template.md`。
- 创建功能 skill 时，读取 `references/feature-skill-template.md`。
- 任务 skill 可参考功能 skill 模板，但正文优先写命令入口、参数、风险确认和输出位置。

## 内容边界

- 不把项目长期规则复制到多个 skill；共性规则保留在 `AGENTS.md`。
- 不把临时需求写进 skill；只有可复用、可迁移、会反复触发或需要约束后续开发的流程才沉淀为 skill。
- 不把派生项目的 README 当作开发规范来源；README 可以引用 skill，但规范正文应落在 `AGENTS.md`、`docs/` 或对应 skill。
- 不保留旧名称、旧入口或兼容别名；替换规则时同步更新文档和引用。
- Skill 内的示例要短，优先给文件入口、命令和决策点。

## 验证

优先运行：

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" ".codex\skills\<skill-name>"
```

如果修改了 `agents/openai.yaml`，确认 `default_prompt` 显式包含 `$<skill-name>`。
