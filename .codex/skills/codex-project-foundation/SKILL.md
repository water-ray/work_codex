---
name: codex-project-foundation
description: 维护 Codex 专用基础项目框架。用于初始化新项目、迁移旧规则平台、添加子项目、整理 AGENTS.md、规划 docs/scripts/Bin/temp 目录、接入项目内 .codex/skills，以及清理旧规则配置。
---

# Codex Project Foundation

## 定位

- 本仓库是用于派生新项目的基础 AI 规则与 Codex skill 框架。
- 派生项目可以自由改写根目录 `README.md`，让它服务于具体项目说明、使用方式和对外入口。
- 开发规范、命名规则、目录边界、验证流程和重复工作流应写入 `AGENTS.md` 或 `.codex/skills/`，不要只写在 `README.md`。

## 工作流

1. 先读取 `README.md`、`AGENTS.md`、`docs/`、`scripts/`、`.vscode/tasks.json` 和 `.codex/skills/`，确认当前项目边界。
2. 将必须始终生效的约束写入根目录 `AGENTS.md`，不要放进普通 skill。
3. 将可按场景触发的开发规范和工作流写成 `.codex/skills/<skill-name>/SKILL.md`。
4. 更新根目录 `README.md` 和 `docs/` 中的入口说明；派生项目的 `README.md` 可按项目需要重写，但其中涉及规范的内容必须与 `AGENTS.md` 和 skill 对齐。
5. 删除被替换平台的配置、说明和索引忽略文件；不要保留历史兼容分支，除非用户明确要求。
6. 用最小验证确认 Markdown、JSON、Python 脚本和 skill frontmatter 可读。

## 基础目录

- `AGENTS.md`：Codex 始终加载的项目规则，存放跨任务必须遵守的约束。
- `.codex/skills/`：项目内 skill 源。需要全局触发时，可复制到 `$CODEX_HOME/skills/`。
- `docs/`：项目说明、设计文档、使用文档和规范说明。
- `scripts/`：自动化脚本，默认使用 Python，并按用途分一级目录。
- `.vscode/`：编辑器任务和工作区辅助配置。
- `Bin/`：最终构建、编译、打包产物。
- `temp/`：临时文件、截图、日志、测试输出和任务缓存。

## 新项目初始化

- 复制 `AGENTS.md`、`.codex/skills/`、`docs/`、`scripts/`、`.vscode/tasks.json`、`.gitignore` 到新项目。
- 按新项目真实技术栈补充源码、配置和测试目录，不把业务代码放入通用辅助目录。
- 为新项目创建或更新一个项目 skill，记录目录布局、常用命令、验证方式、运行边界和关键文件入口。
- 如果新项目有稳定功能域，按功能创建功能 skill；不要把所有功能规则堆进一个总规则文件。
- 派生项目的 `README.md` 可自由改写；命名规范、目录约束、验证流程和开发边界写入 `AGENTS.md`、`docs/` 或对应 skill。

## 子项目接入

- 先确认子项目是否有独立构建、运行、测试和发布流程。
- 有独立流程时，创建 `docs/<子项目>/` 和必要的 `scripts/<用途>/`。
- 子项目规则稳定后，创建 `.codex/skills/<子项目>-project/SKILL.md`；名称使用小写字母、数字和连字符。
- 子项目的命名、目录、命令、验证和发布边界写入项目 skill；功能规则写入独立功能 skill，不混入根项目规则。

## 清理要求

- 迁移旧规则平台时，同步删除旧目录、旧忽略文件、旧 README 入口和旧任务说明。
- 更新所有用户可见名称，避免新框架中残留旧平台表述。
- 只有用户明确要求兼容时，才保留旧平台文件，并在文档中写明移除计划。
