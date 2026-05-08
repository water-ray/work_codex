---
name: repo-git-workflow
description: 使用仓库内 scripts/git/repo_tasks.py 和 .vscode/tasks.json 执行 Git/GitHub 仓库任务。用于查看仓库设置、绑定远程仓库、拉取远程分支、切换或创建分支、提交当前改动、推送分支、还原提交节点。
---

# Repo Git Workflow

## 入口

- 脚本：`scripts/git/repo_tasks.py`
- VS Code 任务：`.vscode/tasks.json`

## 执行原则

- VS Code 任务不使用 `promptString`；所有必要输入统一在任务终端中完成。
- 远程源是当前本地仓库级设置；“仓库：置远程源 🔗”会新增或更新 Git remote，并写入 `codex.repoTasks.remote` 作为仓库默认远程源。
- 拉取和推送必须先有仓库默认远程源；未设置时提示先执行“仓库：置远程源 🔗”。
- 切换或创建分支时，有远程源先更新并列出远程分支列表，无远程源则列出本地分支列表；输入编号选择分支，输入文本作为分支名。切换前先以“切换分支为XXX前的自动提交”提交当前改动；远程源已设置且远程分支存在时优先切换或同步远程分支，未设置远程源或远程分支不存在时仅创建或切换本地分支。
- 拉取远程分支会先以“拉取远程分支REMOTE/BRANCH前的自动提交”提交本地改动；同名分支优先合并，合并失败或分支不同才询问是否覆盖拉取。
- 推送分支时先更新并列出远程分支列表；输入编号选择远程分支，输入文本作为目标分支，直接回车使用当前分支。远程分支不存在则自动创建，远程分支存在则普通推送，失败时显示本地/远程提交说明差异，再询问是否覆盖远程分支。
- 还原节点会倒序分页列出最近提交点；选择节点后必须再次确认，才执行 `git reset --hard <commit>`。
- 强推、覆盖拉取和节点还原只通过脚本内交互确认执行；不要绕过确认直接运行 `git push --force`、`git reset --hard` 或破坏性同步。
- 提交任务会读取上次提交信息、本次 Git 改动和路径语义映射，生成中文默认提交说明；用户直接回车使用默认说明，手动输入则使用输入内容。
- 新增重要目录、任务脚本、配置文件或 skill 类型时，同步维护 `scripts/git/repo_tasks.py` 中的 `semantic_area_for_path` 路径语义映射，保证默认提交说明能正确反映项目框架。

## 常用命令

查看当前分支、远程和作者信息：

```powershell
py -3 scripts/git/repo_tasks.py status
```

状态输出使用 `[本地分支]`、`[远程分支]`、`[fetch]`、`[push]`、`[作者信息]` 标签。作者信息缺失且已配置远程源时，脚本会检查 `gh` 登录账号；存在多个账号时需要选择账号后再自动补全缺失的 `user.name` 或 `user.email`。

新增或更新远程源：

```powershell
py -3 scripts/git/repo_tasks.py set-remote
```

拉取远程分支：

```powershell
py -3 scripts/git/repo_tasks.py pull-remote
```

切换或创建分支：

```powershell
py -3 scripts/git/repo_tasks.py switch
```

切换任务有远程源时显示当前默认远程源下的远程分支列表；没有远程源时显示本地分支列表。输入整数时按编号选择分支；输入其他文本时把文本作为分支名称，并沿用当前切换/创建逻辑。

提交当前全部改动：

```powershell
py -3 scripts/git/repo_tasks.py commit
```

提交任务会在终端显示：

- 上次提交 hash、时间和提交说明。
- 本次 `git status --short` 改动列表。
- 可用的 `git diff --stat` 改动统计。
- 根据路径语义生成的默认中文提交说明。

当前路径语义包括：

- `scripts/git/repo_tasks.py`：Git 仓库任务脚本。
- `.vscode/tasks.json`：VS Code 仓库任务配置。
- `.codex/skills/repo-git-workflow/SKILL.md`：Git 工作流 skill。
- `.codex/skills/codex-project-foundation/`：项目基础框架 skill。
- `.codex/skills/codex-skill-generator/`：Codex skill 生成规则。
- `.codex/skills/`：Codex skill 文档。
- `AGENTS.md`：Codex 项目规则。
- `README.md`、`docs/`：项目文档。
- `.gitignore`：Git 忽略规则。
- `scripts/`：项目脚本。

推送分支：

```powershell
py -3 scripts/git/repo_tasks.py push
```

推送分支任务会先显示当前默认远程源下的远程分支列表，编号从 `1` 开始。输入整数时按编号选择远程分支；输入其他文本时把文本作为目标远程分支名；直接回车使用当前本地分支名。

还原节点：

```powershell
py -3 scripts/git/repo_tasks.py restore-node
```

还原节点任务显示最近 10 个提交点，编号为 `1-10`；输入 `0` 显示 `11-20`，继续输入 `0` 可继续翻页。提交说明中的换行会显示为 `\n`。直接回车取消任务。选择节点后，脚本会显示目标节点、当前未提交改动和风险说明，输入 `Y` 或 `yes` 才执行 `git reset --hard`。

以上命令均可用可选参数跳过终端输入，例如 `--branch <branch>`、`--message "<message>"`、`--name <remote>`、`--url <url>`。

## VS Code 任务

当用户明确说运行“任务”时，优先使用 `.vscode/tasks.json` 中的任务标签：

- `仓库：分支-[查看] 🔎`
- `仓库：置远程源 🔗`
- `仓库：远程-[拉取] ⬇️`
- `仓库：本地-[切换] 🌿`
- `仓库：本地-[提交] 📝`
- `仓库：远程-[推送] 🚀`
- `仓库：本地-[还原] ↩️`

## 输出处理

- 脚本输出包含时间戳、开始时间、结束时间和总耗时。
- 提交任务输出上次提交、本次改动和默认提交说明。
- 推送冲突时输出本地分支与远程分支的提交说明差异。
- 推送分支任务输出远程分支编号列表，便于选择已有远程分支。
- 切换任务输出远程或本地分支编号列表，便于选择已有分支。
- 还原节点任务输出分页提交列表，提交说明换行显示为 `\n`。
- 如果当前目录不是 Git 仓库，先说明无法执行仓库任务，不要尝试初始化仓库，除非用户明确要求。
