---
name: repo-git-workflow
description: 使用仓库内 scripts/git/repo_tasks.py 和 .vscode/tasks.json 执行 Git/GitHub 仓库任务。用于查看仓库设置、绑定远程仓库、拉取远程分支、切换或创建分支、提交当前改动、推送分支。
---

# Repo Git Workflow

## 入口

- 脚本：`scripts/git/repo_tasks.py`
- VS Code 任务：`.vscode/tasks.json`

## 执行原则

- VS Code 任务不使用 `promptString`；所有必要输入统一在任务终端中完成。
- 远程源是当前本地仓库级设置；“仓库：设置远程仓库源”会新增或更新 Git remote，并写入 `codex.repoTasks.remote` 作为仓库默认远程源。
- 拉取和推送必须先有仓库默认远程源；未设置时提示先执行“仓库：设置远程仓库源”。
- 切换或创建分支时，先以“切换分支为XXX前的自动提交”提交当前改动；远程源已设置且远程分支存在时优先切换或同步远程分支，未设置远程源或远程分支不存在时仅创建或切换本地分支。
- 拉取远程分支会先以“拉取远程分支REMOTE/BRANCH前的自动提交”提交本地改动；同名分支优先合并，合并失败或分支不同才询问是否覆盖拉取。
- 推送分支时默认目标远程分支为当前分支；远程分支不存在则自动创建，远程分支存在则普通推送，失败时显示本地/远程提交说明差异，再询问是否覆盖远程分支。
- 强推和覆盖拉取只通过脚本内交互确认执行；不要绕过确认直接运行 `git push --force` 或破坏性同步。
- 提交说明缺失时在终端向用户询问，不自动编造含义不明的提交信息。

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

提交当前全部改动：

```powershell
py -3 scripts/git/repo_tasks.py commit
```

推送分支：

```powershell
py -3 scripts/git/repo_tasks.py push
```

以上命令均可用可选参数跳过终端输入，例如 `--branch <branch>`、`--message "<message>"`、`--name <remote>`、`--url <url>`。

## VS Code 任务

当用户明确说运行“任务”时，优先使用 `.vscode/tasks.json` 中的任务标签：

- `仓库：查看当前分支`
- `仓库：设置远程仓库源`
- `仓库：拉取远程分支`
- `仓库：切换/创建分支`
- `仓库：提交当前改动`
- `仓库：推送分支`

## 输出处理

- 脚本输出包含时间戳、开始时间、结束时间和总耗时。
- 推送冲突时输出本地分支与远程分支的提交说明差异。
- 如果当前目录不是 Git 仓库，先说明无法执行仓库任务，不要尝试初始化仓库，除非用户明确要求。
