# Codex 规则与 Skill 说明

本项目把规则分为两层：

- `AGENTS.md`：始终生效的项目级硬约束。
- `.codex/skills/`：按场景读取的可迁移工作流。

派生项目可以自由改写根目录 `README.md`。README 用于项目说明和使用入口；开发规范、命名规则、目录边界、验证流程和重复工作流以 `AGENTS.md` 和 `.codex/skills/` 为准。

## 已内置的 Skills

- `codex-project-foundation`：用于初始化和维护 Codex 基础项目框架。
- `codex-skill-generator`：用于生成项目 skill、功能 skill 和任务 skill。
- `repo-git-workflow`：用于执行 Git/GitHub 提交、推送、拉取和远程配置任务。

## 新项目迁移

1. 复制 `AGENTS.md`、`.codex/skills/`、`docs/`、`scripts/`、`.vscode/tasks.json` 和 `.gitignore`。
2. 按新项目技术栈添加源码、配置和测试目录。
3. 使用 `codex-skill-generator` 为新项目生成项目 skill。
4. 对稳定功能域继续生成独立功能 skill。
5. 按项目需要自由改写根目录 `README.md`，但不要把 README 作为开发规范唯一来源。
6. 如果需要跨项目或跨设备全局触发，把对应 skill 目录同步到 `$CODEX_HOME/skills/`。

## 添加子项目或功能

- 新增项目或子项目时，创建或更新项目 skill。
- 功能有稳定修改路径、专门业务规则或重复验证步骤时，创建或更新功能 skill。
- 任务有固定命令、参数、风险确认或输出位置时，创建或更新任务 skill。
- 一次性临时需求不写入 skill；只沉淀可复用流程。

## Skill 命名

- 名称只使用小写字母、数字和连字符。
- 项目 skill 使用 `<project-slug>-project`。
- 子项目 skill 使用 `<project-slug>-<subproject-slug>-project`。
- 功能 skill 使用 `<project-slug>-<feature-slug>`。
- 任务或工作流 skill 使用 `<scope-slug>-<workflow-slug>`。

## 验证

修改 skill 后优先运行：

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" ".codex\skills\<skill-name>"
```
