# work_codex

用于新项目部署的 Codex 项目规则与 skill 基础框架。

## 仓库目标

- 提供可直接复用的 Codex 项目规则入口。
- 提供项目内 `.codex/skills/` 源目录，方便迁移到新设备、新项目或子项目。
- 提供适合新项目初始化的基础忽略配置和 Git/GitHub 仓库任务。
- 统一新项目的目录布局、执行边界和 skill 沉淀方式。

## 当前内容

- `AGENTS.md`：Codex 始终生效的项目规则。
- `.codex/skills/codex-project-foundation/`：项目基础框架维护 skill。
- `.codex/skills/codex-skill-generator/`：项目 skill、功能 skill 和任务 skill 生成 skill。
- `.codex/skills/repo-git-workflow/`：Git/GitHub 提交、推送、拉取和远程配置工作流 skill。
- `.vscode/tasks.json`：内置 VS Code 仓库任务定义。
- `scripts/git/repo_tasks.py`：仓库任务统一 Python 入口脚本。
- `.gitignore`：常见缓存、构建产物和临时目录忽略规则。

## 推荐项目结构

```text
.
├─ AGENTS.md
├─ .codex/
│  └─ skills/
├─ .vscode/
├─ docs/
├─ scripts/
├─ Bin/
└─ temp/
```

说明：

- `AGENTS.md`：存放必须始终生效的 Codex 项目规则。
- `.codex/skills/`：存放可迁移的项目 skill、功能 skill 和任务 skill。
- `scripts/`：统一存放 Python 脚本，按用途再分一级目录。
- `.vscode/`：存放编辑器任务与工作区辅助配置。
- `docs/`：统一存放项目说明、设计和使用文档。
- `Bin/`：统一存放构建、编译和打包后的最终产物。
- `temp/`：统一存放测试运行、脚本执行等过程中产生的临时文件。

## 使用方式

1. 将本仓库作为新项目的基础模板使用。
2. 保留 `AGENTS.md` 和 `.codex/skills/`，按项目需要继续补充项目 skill 或功能 skill。
3. 如果需要让 skill 在新设备上全局触发，把 `.codex/skills/<skill-name>/` 同步到 `$CODEX_HOME/skills/`；项目内仍保留源文件。
4. 保留 `.gitignore`，再按项目技术栈增量扩展。
5. 在根目录补充项目自己的源码、配置和测试目录。

## 内置仓库任务

仓库内提供一组基于 Python 的 VS Code 任务，定义在 `.vscode/tasks.json`，统一入口脚本为 `scripts/git/repo_tasks.py`。

可用任务：

- `仓库：查看当前分支`：显示当前分支、上游分支、远程仓库、当前使用的远程和作者信息；缺失配置时给出命令示例。
- `仓库：切换/创建分支`：输入分支名和远程源；本地存在则切换，本地不存在但远程存在则跟踪远程分支并拉取，两者都不存在则创建新本地分支。
- `仓库：提交当前改动`：输入提交说明后，自动暂存并提交当前全部改动。
- `仓库：推送当前分支`：输入远程源后推送当前分支；遇到非 fast-forward 冲突时，可在终端输入 `Y` 或 `yes` 执行强推。
- `仓库：推送指定分支`：输入远程源和目标分支，将当前内容推送到指定远程分支；遇到冲突时同样支持二次确认强推。
- `仓库：拉取远程分支`：输入远程源和远程分支名；先自动提交本地改动，再检查远程分支，同名分支优先合并，合并失败或分支不同则确认后覆盖拉取。
- `仓库：设置远程仓库源`：新增或更新远程源名称与仓库地址的绑定关系。

任务特性：

- 统一使用 Python 脚本实现，便于后续扩展和维护。
- 任务输出自带时间戳、开始时间、结束时间和总耗时。
- 推送与拉取等长耗时操作支持实时输出，便于观察执行进度。
- 最近使用的远程源和目标分支会按任务分别缓存到 `temp/git_tasks/<任务命令>.json`，任务之间不共用配置。

注意事项：

- 强推前必须确认本地和远程分支状态，避免覆盖他人提交。
- 本仓库当前不执行覆盖式拉取；需要破坏性同步时应新增独立任务并写清风险确认。

## 文档入口

- `docs/README.md`
- `docs/codex/README.md`
- `scripts/README.md`
