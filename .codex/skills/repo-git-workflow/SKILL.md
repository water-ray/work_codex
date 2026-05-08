---
name: repo-git-workflow
description: 使用仓库内 scripts/git/repo_tasks.py 和 .vscode/tasks.json 执行 Git/GitHub 仓库任务。用于查看分支和远程、切换或创建分支、提交当前改动、推送当前或指定分支、拉取远程分支、设置远程仓库源。
---

# Repo Git Workflow

## 入口

- 脚本：`scripts/git/repo_tasks.py`
- VS Code 任务：`.vscode/tasks.json`
- 缓存：`temp/git_tasks/<任务命令>.json`

## 执行原则

- 执行提交或推送前，先查看当前分支、远程和改动摘要。
- 提交说明缺失时先向用户确认，不自动编造含义不明的提交信息。
- 推送远程源缺失时，脚本会按输入、当前任务缓存、当前上游、`origin` 的顺序解析；拉取远程分支必须显式输入远程源和分支名。
- 切换或创建分支时，先以“切换分支为XXX前的自动提交”提交当前改动；本地分支优先，本地不存在才按任务缓存、当前上游、`origin` 自动解析远程源并检查远程分支，远程存在则创建跟踪分支并执行 fast-forward 拉取，远程也不存在则只创建新本地分支。
- 强推只通过脚本内交互确认执行；推送冲突时先显示本地/远程提交说明差异，再询问是否覆盖远程分支；不要绕过确认直接运行 `git push --force`。
- 拉取远程分支会先自动提交本地改动；同名分支优先合并，合并失败或分支不同才询问是否覆盖拉取。

## 常用命令

查看当前分支、远程和作者信息：

```powershell
py -3 scripts/git/repo_tasks.py status
```

状态输出使用 `[本地分支]`、`[远程分支]`、`[fetch]`、`[push]`、`[作者信息]` 标签。作者信息缺失且已配置远程源时，脚本会检查 `gh` 登录账号；存在多个账号时需要选择账号后再自动补全缺失的 `user.name` 或 `user.email`。

切换或创建分支：

```powershell
py -3 scripts/git/repo_tasks.py switch --branch <branch>
```

指定检查远程源：

```powershell
py -3 scripts/git/repo_tasks.py switch --branch <branch> --remote <remote>
```

提交当前全部改动：

```powershell
py -3 scripts/git/repo_tasks.py commit --message "<message>"
```

推送当前分支：

```powershell
py -3 scripts/git/repo_tasks.py push-current --remote <remote>
```

将当前 HEAD 推送到指定远程分支：

```powershell
py -3 scripts/git/repo_tasks.py push-branch --remote <remote> --branch <branch>
```

拉取远程分支：

```powershell
py -3 scripts/git/repo_tasks.py pull-remote --remote <remote> --branch <branch>
```

新增或更新远程源：

```powershell
py -3 scripts/git/repo_tasks.py set-remote --name <remote> --url <url>
```

## VS Code 任务

当用户明确说运行“任务”时，优先使用 `.vscode/tasks.json` 中的任务标签：

- `仓库：查看当前分支`
- `仓库：切换/创建分支`
- `仓库：提交当前改动`
- `仓库：推送当前分支`
- `仓库：推送指定分支`
- `仓库：拉取远程分支`
- `仓库：设置远程仓库源`

## 输出处理

- 脚本输出包含时间戳、开始时间、结束时间和总耗时。
- 最近远程源和目标分支按命令分别写入 `temp/git_tasks/<任务命令>.json`，这些文件属于临时缓存，任务之间不共用配置。
- 如果当前目录不是 Git 仓库，先说明无法执行仓库任务，不要尝试初始化仓库，除非用户明确要求。
