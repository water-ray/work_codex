from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any


USER_HOME = Path(os.environ.get("USERPROFILE", str(Path.home())))
WINDOWS_GIT_CANDIDATES = [
    r"C:\Program Files\Git\cmd\git.exe",
    r"C:\Program Files\Git\bin\git.exe",
    r"C:\Program Files (x86)\Git\cmd\git.exe",
    r"C:\Program Files (x86)\Git\bin\git.exe",
    str(USER_HOME / "AppData" / "Local" / "Programs" / "Git" / "cmd" / "git.exe"),
    str(USER_HOME / "scoop" / "apps" / "git" / "current" / "cmd" / "git.exe"),
]


class TaskError(RuntimeError):
    pass


@dataclass
class RepoContext:
    git_exe: str
    root: Path


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def current_time_text() -> str:
    return datetime.now().strftime("%H:%M:%S")


def current_datetime_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}秒"

    total_seconds = int(seconds)
    minutes, remain_seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours}小时{minutes}分{remain_seconds}秒"
    return f"{minutes}分{remain_seconds}秒"


def log(message: str = "", *, stream: Any = sys.stdout) -> None:
    if message == "":
        print("", file=stream, flush=True)
        return

    for line in str(message).splitlines():
        print(f"[{current_time_text()}] {line}", file=stream, flush=True)


def command_display_name(command: str) -> str:
    mapping = {
        "status": "仓库：查看当前分支",
        "switch": "仓库：切换/创建分支",
        "commit": "仓库：提交当前改动",
        "push": "仓库：推送分支",
        "pull-remote": "仓库：拉取远程分支",
        "set-remote": "仓库：设置远程仓库源",
    }
    return mapping.get(command, command)


def detect_git_executable() -> str:
    candidates: list[str] = []

    env_git = os.environ.get("GIT_EXE", "").strip()
    if env_git:
        candidates.append(env_git)

    which_git = shutil.which("git")
    if which_git:
        candidates.append(which_git)

    if os.name == "nt":
        candidates.extend(WINDOWS_GIT_CANDIDATES)

    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(Path(candidate))
        if normalized in seen:
            continue
        seen.add(normalized)
        if Path(candidate).exists():
            return candidate

    raise TaskError(
        "未找到 Git 可执行文件。\n"
        "请安装 Git，或设置环境变量 GIT_EXE 指向 git 可执行文件。"
    )


def run_process(
    command: list[str],
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    if check and result.returncode != 0:
        raise TaskError(format_process_error(command, result))

    return result


def run_streaming_process(
    command: list[str],
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )

    output_lines: list[str] = []

    try:
        assert process.stdout is not None
        for line in process.stdout:
            text = line.rstrip("\r\n")
            output_lines.append(text)
            if text:
                log(text)
            else:
                log()
    finally:
        if process.stdout is not None:
            process.stdout.close()

    return_code = process.wait()
    result = subprocess.CompletedProcess(
        command,
        return_code,
        stdout="\n".join(output_lines),
        stderr="",
    )

    if check and result.returncode != 0:
        raise TaskError(format_process_error(command, result))

    return result


def format_process_error(
    command: list[str], result: subprocess.CompletedProcess[str]
) -> str:
    parts = [
        f"命令执行失败（退出码 {result.returncode}）:",
        " ".join(command),
    ]

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if stdout:
        parts.extend(["", "[stdout]", stdout])
    if stderr:
        parts.extend(["", "[stderr]", stderr])

    return "\n".join(parts)


def build_repo_context() -> RepoContext:
    git_exe = detect_git_executable()
    root_result = run_process(
        [git_exe, "rev-parse", "--show-toplevel"],
        cwd=Path.cwd(),
        check=False,
    )
    if root_result.returncode != 0:
        raise TaskError("当前目录不是 Git 仓库，无法执行仓库任务。")

    root = Path(root_result.stdout.strip()).resolve()
    return RepoContext(git_exe=git_exe, root=root)


def git(ctx: RepoContext, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run_process(
        [ctx.git_exe, "-c", "core.quotepath=false", *args],
        cwd=ctx.root,
        check=check,
    )


def git_stream(ctx: RepoContext, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run_streaming_process(
        [ctx.git_exe, "-c", "core.quotepath=false", *args],
        cwd=ctx.root,
        check=check,
    )


def git_stdout(ctx: RepoContext, *args: str, check: bool = True) -> str:
    return git(ctx, *args, check=check).stdout.strip()


def prompt_text(
    label: str,
    default: str = "",
    *,
    required: bool = False,
    show_default: bool = True,
) -> str:
    prompt = f"[{current_time_text()}] {label}"
    if default and show_default:
        prompt += f"（默认：{default}）"
    prompt += ": "

    try:
        answer = input(prompt).strip()
    except EOFError as error:
        if default:
            return default
        raise TaskError(f"{label}不能为空。") from error

    value = answer or default
    if required and not value:
        raise TaskError(f"{label}不能为空。")
    return value


def current_branch(ctx: RepoContext) -> str | None:
    branch = git_stdout(ctx, "branch", "--show-current", check=False)
    return branch or None


def ensure_branch(ctx: RepoContext) -> str:
    branch = current_branch(ctx)
    if not branch:
        raise TaskError("当前不在可识别的本地分支上，可能处于 detached HEAD 状态。")
    return branch


def current_upstream(ctx: RepoContext) -> dict[str, str] | None:
    upstream = git_stdout(
        ctx,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{u}",
        check=False,
    )
    if not upstream:
        return None

    if "/" not in upstream:
        return {"full": upstream, "remote": upstream, "branch": ""}

    remote_name, branch_name = upstream.split("/", 1)
    return {"full": upstream, "remote": remote_name, "branch": branch_name}


def remote_map(ctx: RepoContext) -> dict[str, dict[str, str]]:
    remotes: dict[str, dict[str, str]] = {}
    output = git_stdout(ctx, "remote", "-v", check=False)
    pattern = re.compile(r"^(\S+)\s+(.+?)\s+\((fetch|push)\)$")

    for line in output.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue

        name, url, kind = match.groups()
        remotes.setdefault(name, {})[kind] = url

    return remotes


def git_config(ctx: RepoContext, key: str) -> str:
    return git_stdout(ctx, "config", "--get", key, check=False)


def set_git_config(ctx: RepoContext, key: str, value: str) -> None:
    git(ctx, "config", key, value)


def local_branch_exists(ctx: RepoContext, branch_name: str) -> bool:
    result = git(ctx, "show-ref", "--verify", f"refs/heads/{branch_name}", check=False)
    return result.returncode == 0


def ensure_valid_branch_name(ctx: RepoContext, branch_name: str) -> None:
    result = git(ctx, "check-ref-format", "--branch", branch_name, check=False)
    if result.returncode != 0:
        raise TaskError(f"分支名称不合法：{branch_name}")


def fetch_remote_branch(ctx: RepoContext, remote_name: str, branch_name: str) -> bool:
    remote_ref = f"refs/heads/{branch_name}"
    local_ref = f"refs/remotes/{remote_name}/{branch_name}"
    result = git(
        ctx,
        "fetch",
        remote_name,
        f"+{remote_ref}:{local_ref}",
        check=False,
    )
    if result.returncode == 0:
        return True

    combined = "\n".join(
        part.strip() for part in (result.stdout or "", result.stderr or "") if part.strip()
    ).lower()
    missing_markers = (
        "couldn't find remote ref",
        "could not find remote ref",
        "找不到远程引用",
    )
    if any(marker in combined for marker in missing_markers):
        return False

    raise TaskError(format_process_error([ctx.git_exe, "fetch", remote_name, remote_ref], result))


def ensure_remote_exists(ctx: RepoContext, remote_name: str) -> None:
    remotes = remote_map(ctx)
    if remote_name in remotes:
        return

    available = ", ".join(sorted(remotes)) if remotes else "无"
    raise TaskError(
        f"未找到远程源：{remote_name}\n"
        f"当前可用远程源：{available}\n"
        '可使用任务“仓库：设置远程仓库源”进行新增或更新。'
    )


def configured_repo_task_remote(ctx: RepoContext) -> str | None:
    remote_name = git_stdout(ctx, "config", "--local", "--get", "codex.repoTasks.remote", check=False)
    return remote_name or None


def set_configured_repo_task_remote(ctx: RepoContext, remote_name: str) -> None:
    git(ctx, "config", "--local", "codex.repoTasks.remote", remote_name)


def configured_remote_if_available(ctx: RepoContext) -> tuple[str, str] | None:
    remote_name = configured_repo_task_remote(ctx)
    if not remote_name:
        return None

    remotes = remote_map(ctx)
    if remote_name in remotes:
        return remote_name, "仓库默认远程源"

    log(f"已配置的仓库默认远程源不存在：{remote_name}", stream=sys.stderr)
    return None


def require_configured_remote(ctx: RepoContext) -> tuple[str, str]:
    remote = configured_remote_if_available(ctx)
    if remote:
        return remote

    raise TaskError('未设置远程源，请先执行任务“仓库：设置远程仓库源”。')


def is_non_fast_forward_push_error(result: subprocess.CompletedProcess[str]) -> bool:
    combined = "\n".join(
        part.strip() for part in (result.stdout or "", result.stderr or "") if part.strip()
    ).lower()
    markers = (
        "fetch first",
        "non-fast-forward",
        "[rejected]",
        "tip of your current branch is behind",
    )
    return any(marker in combined for marker in markers)


def print_branch_commit_diff(
    ctx: RepoContext,
    local_label: str,
    remote_name: str,
    remote_branch_name: str,
) -> None:
    upstream_ref = remote_tracking_ref(remote_name, remote_branch_name)
    print_section("提交差异")
    if not fetch_remote_branch(ctx, remote_name, remote_branch_name):
        log(f"[远程分支] {upstream_ref} 不存在。")
        return

    count_output = git_stdout(
        ctx,
        "rev-list",
        "--left-right",
        "--count",
        f"HEAD...{upstream_ref}",
        check=False,
    )
    local_count = "?"
    remote_count = "?"
    if count_output:
        parts = count_output.split()
        if len(parts) >= 2:
            local_count, remote_count = parts[0], parts[1]

    log(f"[本地分支 {local_label} (新 {local_count})] - [远程分支 {upstream_ref} (旧 {remote_count})]")
    diff_output = git_stdout(
        ctx,
        "log",
        "--left-right",
        "--cherry-pick",
        "--pretty=format:%m %h %s",
        f"HEAD...{upstream_ref}",
        check=False,
    )
    if not diff_output:
        log("无提交说明差异。")
        return

    for line in diff_output.splitlines():
        if line.startswith("<"):
            log(f"[本地新增] {line[2:]}")
        elif line.startswith(">"):
            log(f"[远程独有] {line[2:]}")
        else:
            log(line)


def print_push_commit_diff(
    ctx: RepoContext,
    local_branch_name: str,
    remote_name: str,
    remote_branch_name: str,
) -> None:
    print_branch_commit_diff(ctx, local_branch_name, remote_name, remote_branch_name)


def confirm_force_push(remote_name: str, branch_name: str) -> bool:
    print_section("推送冲突")
    log("检测到远程分支存在未合并提交，普通推送已被 Git 拒绝。")
    log("强制推送会用本地分支覆盖远程分支。")
    try:
        answer = input(
            f"[{current_time_text()}] 是否强制推送覆盖远程分支{remote_name}/{branch_name}? Y确认(默认取消): "
        ).strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def confirm_force_pull(reason: str) -> bool:
    print_section("覆盖拉取确认")
    log(reason)
    log("此操作会将本地分支重置为远程分支内容，未在目标分支上的提交不会保留在该分支历史中。")
    log("如果确认要覆盖拉取，请输入 Y 或 yes 继续。")
    log("输入其他内容或直接回车将取消。")
    try:
        answer = input(f"[{current_time_text()}] 是否执行覆盖拉取？[y/N]: ").strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def print_completed_process(result: subprocess.CompletedProcess[str]) -> None:
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if stdout:
        log(stdout)
    if stderr:
        log(stderr, stream=sys.stderr)


def run_push_with_optional_force(
    ctx: RepoContext,
    push_args: list[str],
    force_push_args: list[str],
    success_message: str,
    force_success_message: str,
    remote_name: str,
    local_branch_name: str,
    remote_branch_name: str,
) -> int:
    push_started = perf_counter()
    log("开始执行普通推送...")
    result = git_stream(ctx, *push_args, check=False)
    if result.returncode == 0:
        log(f"{success_message}，命令耗时 {format_duration(perf_counter() - push_started)}")
        return 0

    if not is_non_fast_forward_push_error(result):
        raise TaskError(
            f"普通推送失败，命令耗时 {format_duration(perf_counter() - push_started)}。"
            " 详细输出见上方日志。"
        )

    log(f"普通推送失败，命令耗时 {format_duration(perf_counter() - push_started)}")
    print_push_commit_diff(ctx, local_branch_name, remote_name, remote_branch_name)

    if not sys.stdin.isatty():
        raise TaskError("当前终端不可交互，无法确认是否强制推送。")

    if not confirm_force_push(remote_name, remote_branch_name):
        raise TaskError("已取消强制推送，远程未发生变更。")

    log()
    log("开始执行强制推送...")
    force_started = perf_counter()
    force_result = git_stream(ctx, *force_push_args, check=False)
    if force_result.returncode != 0:
        raise TaskError(
            f"强制推送失败，命令耗时 {format_duration(perf_counter() - force_started)}。"
            " 详细输出见上方日志。"
        )

    log(
        f"{force_success_message}，命令耗时 {format_duration(perf_counter() - force_started)}"
    )
    return 0


def print_section(title: str) -> None:
    log()
    log(f"== {title} ==")


def run_gh_json(*args: str) -> Any:
    gh_exe = shutil.which("gh")
    if not gh_exe:
        raise TaskError("未找到 GitHub CLI：gh")

    result = run_process([gh_exe, *args], check=False)
    if result.returncode != 0:
        raise TaskError(format_process_error([gh_exe, *args], result))

    try:
        return json.loads(result.stdout or "{}")
    except json.JSONDecodeError as error:
        raise TaskError(f"无法解析 gh 输出：{error}") from error


def run_gh(*args: str) -> subprocess.CompletedProcess[str]:
    gh_exe = shutil.which("gh")
    if not gh_exe:
        raise TaskError("未找到 GitHub CLI：gh")
    return run_process([gh_exe, *args], check=True)


def github_accounts() -> list[dict[str, Any]]:
    data = run_gh_json("auth", "status", "--hostname", "github.com", "--json", "hosts")
    host_accounts = data.get("hosts", {}).get("github.com", [])
    return [
        account
        for account in host_accounts
        if account.get("state") == "success" and account.get("login")
    ]


def choose_github_account(accounts: list[dict[str, Any]]) -> str | None:
    if not accounts:
        return None
    if len(accounts) == 1:
        return str(accounts[0]["login"])

    print_section("GitHub 账号")
    log("检测到多个已登录 GitHub 账号，请选择用于设置作者信息的账号：")
    for index, account in enumerate(accounts, start=1):
        active_text = "（当前）" if account.get("active") else ""
        log(f"{index}. {account['login']}{active_text}")

    if not sys.stdin.isatty():
        log("当前终端不可交互，无法选择 GitHub 账号。", stream=sys.stderr)
        return None

    try:
        answer = input(f"[{current_time_text()}] 请输入账号序号或账号名: ").strip()
    except EOFError:
        return None

    if not answer:
        return None
    if answer.isdigit():
        index = int(answer)
        if 1 <= index <= len(accounts):
            return str(accounts[index - 1]["login"])
        return None

    login_map = {str(account["login"]).lower(): str(account["login"]) for account in accounts}
    return login_map.get(answer.lower())


def github_user_profile(login: str) -> dict[str, Any]:
    run_gh("auth", "switch", "--hostname", "github.com", "--user", login)
    return run_gh_json("api", "user")


def github_author_email(profile: dict[str, Any]) -> str:
    email = str(profile.get("email") or "").strip()
    if email:
        return email

    login = str(profile.get("login") or "").strip()
    user_id = str(profile.get("id") or "").strip()
    if login and user_id:
        return f"{user_id}+{login}@users.noreply.github.com"
    if login:
        return f"{login}@users.noreply.github.com"
    return ""


def fill_missing_author_from_gh(
    ctx: RepoContext,
    author_name: str,
    author_email: str,
    has_remote: bool,
) -> tuple[str, str]:
    if author_name and author_email:
        return author_name, author_email
    if not has_remote:
        return author_name, author_email

    try:
        accounts = github_accounts()
    except TaskError as error:
        log(f"[作者信息] 无法检查 gh 登录状态：{error}", stream=sys.stderr)
        return author_name, author_email

    selected_login = choose_github_account(accounts)
    if not selected_login:
        log("[作者信息] 未选择 GitHub 账号，跳过自动设置。", stream=sys.stderr)
        return author_name, author_email

    try:
        profile = github_user_profile(selected_login)
    except TaskError as error:
        log(f"[作者信息] 无法读取 GitHub 账号信息：{error}", stream=sys.stderr)
        return author_name, author_email

    profile_login = str(profile.get("login") or selected_login).strip()
    profile_email = github_author_email(profile)

    if not author_name and profile_login:
        set_git_config(ctx, "user.name", profile_login)
        author_name = profile_login
        log(f"[作者信息] 已设置 user.name : {author_name}")
    if not author_email and profile_email:
        set_git_config(ctx, "user.email", profile_email)
        author_email = profile_email
        log(f"[作者信息] 已设置 user.email: {author_email}")

    return author_name, author_email


def remote_display_url(remotes: dict[str, dict[str, str]], remote_name: str) -> str:
    remote = remotes.get(remote_name, {})
    return remote.get("fetch") or remote.get("push") or "未设置"


def display_width(text: str) -> int:
    return sum(
        2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
        for char in text
    )


def pad_display(text: str, width: int) -> str:
    return text + (" " * max(width - display_width(text), 1))


def log_status_row(label: str, value: str, detail: str = "") -> None:
    padded_label = pad_display(label, 12)
    if detail:
        log(f"{padded_label}| {pad_display(value, 24)}| {detail}")
    else:
        log(f"{padded_label}| {value}")


def cmd_status(ctx: RepoContext, _: argparse.Namespace) -> int:
    branch = current_branch(ctx)
    upstream = current_upstream(ctx)
    remotes = remote_map(ctx)
    author_name = git_config(ctx, "user.name")
    author_email = git_config(ctx, "user.email")

    if branch:
        log_status_row("[本地分支]", branch, str(ctx.root))
    else:
        log_status_row("[本地分支]", "未检测到", f"{ctx.root}（可能处于 detached HEAD 状态）")

    if not remotes:
        log_status_row("[远程分支]", '无远程源,使用"仓库：设置远程仓库源"任务设置')
    else:
        if upstream and upstream.get("remote"):
            remote_name = upstream["remote"]
            remote_url = remote_display_url(remotes, remote_name)
            log_status_row("[远程分支]", upstream["full"], f"{remote_name}  {remote_url}")
        else:
            first_remote = sorted(remotes)[0]
            remote_url = remote_display_url(remotes, first_remote)
            log_status_row("[远程分支]", "未绑定", f"{first_remote}  {remote_url}")

        for name in sorted(remotes):
            fetch_url = remotes[name].get("fetch", "未设置")
            push_url = remotes[name].get("push", "未设置")
            log_status_row("[fetch]", name, fetch_url)
            log_status_row("[push]", name, push_url)

    author_name, author_email = fill_missing_author_from_gh(
        ctx,
        author_name,
        author_email,
        bool(remotes),
    )

    log_status_row("[作者信息]", "user.name", author_name or "未设置")
    log_status_row("[作者信息]", "user.email", author_email or "未设置")

    return 0


def cmd_switch(ctx: RepoContext, args: argparse.Namespace) -> int:
    branch_name = args.branch.strip() or prompt_text("请输入要切换或创建的分支名称", required=True)
    ensure_valid_branch_name(ctx, branch_name)
    commit_all_changes(ctx, f"切换分支为{branch_name}前的自动提交")

    remote = configured_remote_if_available(ctx)
    if not remote:
        if local_branch_exists(ctx, branch_name):
            git(ctx, "switch", branch_name)
            log(f"未设置远程源，已切换到已有本地分支：{branch_name}")
        else:
            git(ctx, "switch", "-c", branch_name)
            log(f"未设置远程源，已创建并切换到新本地分支：{branch_name}")
        return 0

    remote_name, remote_source = remote
    log(f"使用远程源: {remote_name}（来源：{remote_source}）")
    log(f"优先检查远程分支：{remote_name}/{branch_name}")
    if fetch_remote_branch(ctx, remote_name, branch_name):
        upstream_ref = remote_tracking_ref(remote_name, branch_name)
        if local_branch_exists(ctx, branch_name):
            git(ctx, "switch", branch_name)
            set_branch_upstream(ctx, branch_name, upstream_ref)
            log(f"远程分支存在，已切换到本地同名分支并绑定：{branch_name} -> {upstream_ref}")
            log("开始同步远程分支最新内容（fast-forward）...")
            merge_result = git(ctx, "merge", "--ff-only", upstream_ref, check=False)
            if merge_result.returncode == 0:
                print_completed_process(merge_result)
                log(f"已同步远程分支：{upstream_ref}")
                return 0

            log("同步远程分支失败，错误原因如下：", stream=sys.stderr)
            print_completed_process(merge_result)
            print_branch_commit_diff(ctx, branch_name, remote_name, branch_name)
            if not confirm_force_pull(f"本地分支 {branch_name} 与远程分支 {upstream_ref} 无法 fast-forward 同步。"):
                raise TaskError("已取消覆盖同步，当前仍停留在本地分支。")
            git(ctx, "reset", "--hard", upstream_ref)
            log(f"已按远程分支覆盖本地分支：{branch_name} -> {upstream_ref}")
            return 0

        git(ctx, "switch", "--track", "-c", branch_name, upstream_ref)
        log(f"已基于远程分支创建并切换：{branch_name} -> {upstream_ref}")
        return 0

    if local_branch_exists(ctx, branch_name):
        git(ctx, "switch", branch_name)
        log(f"远程分支不存在，已切换到已有本地分支：{branch_name}")
    else:
        git(ctx, "switch", "-c", branch_name)
        log(f"远程分支不存在，已创建并切换到新本地分支：{branch_name}")
        log(f"后续运行“仓库：推送分支”可创建远程分支：{remote_name}/{branch_name}")
    return 0


def cmd_commit(ctx: RepoContext, args: argparse.Namespace) -> int:
    changed = working_tree_status(ctx)
    if not changed:
        log("当前没有可提交的改动。")
        return 0

    suggested_message = print_commit_summary(ctx, changed)
    message = args.message.strip() or prompt_text(
        "请输入提交说明(默认如上)",
        default=suggested_message,
        required=True,
        show_default=False,
    )
    commit_all_changes(ctx, message)
    return 0


def working_tree_status(ctx: RepoContext) -> str:
    return git_stdout(ctx, "status", "--short", "--untracked-files=all", check=False)


def has_commits(ctx: RepoContext) -> bool:
    return git(ctx, "rev-parse", "--verify", "HEAD", check=False).returncode == 0


def last_commit_summary(ctx: RepoContext) -> str:
    if not has_commits(ctx):
        return "无提交记录"

    output = git_stdout(
        ctx,
        "log",
        "-1",
        "--format=%h%x1f%cd%x1f%s",
        "--date=format:%Y-%m-%d %H:%M:%S",
        check=False,
    )
    if not output:
        return "无法读取上次提交信息"

    parts = output.split("\x1f", 2)
    if len(parts) != 3:
        return output
    return f"{parts[0]}  {parts[1]}  {parts[2]}"


def status_changed_path(status_line: str) -> str:
    if len(status_line) <= 3:
        return status_line.strip()

    path_text = status_line[3:].strip()
    if " -> " in path_text:
        path_text = path_text.split(" -> ")[-1].strip()
    return path_text.strip('"')


def semantic_area_for_path(path_text: str) -> str:
    path = path_text.replace("\\", "/")

    if path == "scripts/git/repo_tasks.py":
        return "Git 仓库任务脚本"
    if path == ".vscode/tasks.json":
        return "VS Code 仓库任务配置"
    if path.startswith(".vscode/") or path.endswith(".code-workspace"):
        return "VS Code 工作区配置"
    if path == ".codex/skills/repo-git-workflow/SKILL.md":
        return "Git 工作流 skill"
    if path.startswith(".codex/skills/codex-project-foundation/"):
        return "项目基础框架 skill"
    if path.startswith(".codex/skills/codex-skill-generator/"):
        return "Codex skill 生成规则"
    if path.startswith(".codex/skills/"):
        return "Codex skill 文档"
    if path == "AGENTS.md":
        return "Codex 项目规则"
    if path == "README.md" or path.startswith("docs/"):
        return "项目文档"
    if path == ".gitignore":
        return "Git 忽略规则"
    if path.startswith("scripts/git/"):
        return "Git 辅助脚本"
    if path.startswith("scripts/"):
        return "项目脚本"
    if path.startswith("Bin/"):
        return "构建产物目录"
    if path.startswith("."):
        return "项目配置"
    return "项目文件"


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def join_chinese_items(items: list[str]) -> str:
    if not items:
        return "项目改动"
    if len(items) == 1:
        return items[0]
    final_separator = "和 " if items[-1][:1].isascii() else "和"
    if len(items) == 2:
        return f"{items[0]}{final_separator}{items[1]}"
    if len(items) == 3:
        return f"{items[0]}、{items[1]}{final_separator}{items[2]}"
    return f"{items[0]}、{items[1]}{final_separator}{items[2]}等{len(items)}类内容"


def change_verb(status_lines: list[str]) -> str:
    status_text = "".join(line[:2] for line in status_lines)
    has_added = "A" in status_text or "?" in status_text
    has_deleted = "D" in status_text
    has_renamed = "R" in status_text
    has_modified = any(marker in status_text for marker in ("M", "T", "U"))

    if has_deleted and not (has_added or has_modified or has_renamed):
        return "清理"
    if has_added and not (has_deleted or has_modified or has_renamed):
        return "新增"
    if has_renamed or (has_added and has_deleted):
        return "调整"
    return "更新"


def suggested_commit_message(status_text: str) -> str:
    status_lines = [line for line in status_text.splitlines() if line.strip()]
    areas = unique_preserve_order(
        [semantic_area_for_path(status_changed_path(line)) for line in status_lines]
    )
    area_text = join_chinese_items(areas)
    separator = " " if area_text[:1].isascii() else ""
    return f"{change_verb(status_lines)}{separator}{area_text}"


def print_commit_summary(ctx: RepoContext, status_text: str) -> str:
    suggested_message = suggested_commit_message(status_text)
    diff_stat = git_stdout(ctx, "diff", "--stat", "HEAD", "--", check=False) if has_commits(ctx) else ""

    print_section("上次提交")
    log(last_commit_summary(ctx))

    print_section("本次改动")
    log(status_text)

    if diff_stat:
        print_section("改动统计")
        log(diff_stat)

    print_section("默认提交说明")
    log(suggested_message)
    return suggested_message


def commit_all_changes(ctx: RepoContext, message: str) -> bool:
    changed = working_tree_status(ctx)
    if not changed:
        log("当前没有可提交的改动。")
        return False

    git(ctx, "add", "-A")

    print_section("即将提交的改动")
    log(working_tree_status(ctx) or "无")

    result = git(ctx, "commit", "-m", message)
    log(result.stdout.strip() or "提交完成。")
    return True


def cmd_push(ctx: RepoContext, args: argparse.Namespace) -> int:
    current_branch_name = ensure_branch(ctx)
    remote_name, remote_source = require_configured_remote(ctx)
    target_branch = args.branch.strip() or prompt_text(
        "请输入要推送到的远程分支名称",
        default=current_branch_name,
        required=True,
    )
    ensure_valid_branch_name(ctx, target_branch)

    log(f"使用远程源: {remote_name}（来源：{remote_source}）")
    log(f"本地分支: {current_branch_name}")
    log(f"目标远程分支: {target_branch}")

    if fetch_remote_branch(ctx, remote_name, target_branch):
        log(f"远程分支已存在，开始普通推送：{remote_name}/{target_branch}")
    else:
        log(f"远程分支不存在，将自动创建并推送：{remote_name}/{target_branch}")

    if target_branch == current_branch_name:
        push_args = ["push", "-u", remote_name, current_branch_name]
        force_push_args = ["push", "--force", "-u", remote_name, current_branch_name]
    else:
        push_args = ["push", remote_name, f"HEAD:{target_branch}"]
        force_push_args = ["push", "--force", remote_name, f"HEAD:{target_branch}"]

    return run_push_with_optional_force(
        ctx,
        push_args,
        force_push_args,
        f"已推送本地分支 {current_branch_name} 到 {remote_name}/{target_branch}",
        f"已强制推送本地分支 {current_branch_name} 到 {remote_name}/{target_branch}",
        remote_name,
        current_branch_name,
        target_branch,
    )


def remote_tracking_ref(remote_name: str, branch_name: str) -> str:
    return f"{remote_name}/{branch_name}"


def set_branch_upstream(ctx: RepoContext, branch_name: str, upstream_ref: str) -> None:
    git(ctx, "branch", "--set-upstream-to", upstream_ref, branch_name)


def abort_merge_if_needed(ctx: RepoContext) -> None:
    merge_head_text = git_stdout(ctx, "rev-parse", "--git-path", "MERGE_HEAD", check=False)
    merge_head = Path(merge_head_text)
    if not merge_head.is_absolute():
        merge_head = ctx.root / merge_head
    if merge_head.exists():
        git(ctx, "merge", "--abort", check=False)


def overwrite_with_remote_branch(
    ctx: RepoContext, remote_name: str, branch_name: str
) -> None:
    upstream_ref = remote_tracking_ref(remote_name, branch_name)
    if local_branch_exists(ctx, branch_name):
        git(ctx, "switch", branch_name)
        set_branch_upstream(ctx, branch_name, upstream_ref)
        git(ctx, "reset", "--hard", upstream_ref)
        log(f"已切换并覆盖本地分支：{branch_name} -> {upstream_ref}")
        return

    git(ctx, "switch", "--track", "-c", branch_name, upstream_ref)
    log(f"已创建并切换到远程跟踪分支：{branch_name} -> {upstream_ref}")


def cmd_pull_remote(ctx: RepoContext, args: argparse.Namespace) -> int:
    current_branch_name = ensure_branch(ctx)
    remote_name, remote_source = require_configured_remote(ctx)
    branch_name = args.branch.strip() or prompt_text(
        "请输入要拉取的远程分支名称",
        default=current_branch_name,
        required=True,
    )
    ensure_valid_branch_name(ctx, branch_name)

    log(f"使用远程源: {remote_name}（来源：{remote_source}）")
    log(f"目标远程分支: {branch_name}")
    commit_all_changes(ctx, f"拉取远程分支{remote_name}/{branch_name}前的自动提交")

    pull_started = perf_counter()
    log(f"正在检查远程分支是否存在：{remote_name}/{branch_name}")
    if not fetch_remote_branch(ctx, remote_name, branch_name):
        log(f"远程分支{remote_name}/{branch_name}不存在。")
        return 0

    upstream_ref = remote_tracking_ref(remote_name, branch_name)
    if branch_name == current_branch_name:
        log(f"远程分支与当前本地分支同名，开始合并：{upstream_ref}")
        merge_result = git(ctx, "merge", "--no-edit", upstream_ref, check=False)
        if merge_result.returncode == 0:
            print_completed_process(merge_result)
            set_branch_upstream(ctx, branch_name, upstream_ref)
            log(
                f"已合并远程分支 {upstream_ref}，命令耗时 "
                f"{format_duration(perf_counter() - pull_started)}"
            )
            return 0

        log("合并远程分支失败，错误原因如下：", stream=sys.stderr)
        print_completed_process(merge_result)
        abort_merge_if_needed(ctx)
        if not confirm_force_pull(f"当前分支 {current_branch_name} 与 {upstream_ref} 无法自动合并。"):
            raise TaskError("已取消覆盖拉取。")

        overwrite_with_remote_branch(ctx, remote_name, branch_name)
        log(
            f"已覆盖拉取远程分支 {upstream_ref}，命令耗时 "
            f"{format_duration(perf_counter() - pull_started)}"
        )
        return 0

    if not confirm_force_pull(
        f"当前本地分支为 {current_branch_name}，目标远程分支为 {upstream_ref}，分支不同。"
    ):
        raise TaskError("已取消覆盖拉取。")

    overwrite_with_remote_branch(ctx, remote_name, branch_name)
    log(
        f"已拉取并切换到远程分支 {upstream_ref}，命令耗时 "
        f"{format_duration(perf_counter() - pull_started)}"
    )
    return 0


def cmd_set_remote(ctx: RepoContext, args: argparse.Namespace) -> int:
    remotes = remote_map(ctx)
    configured_remote = configured_repo_task_remote(ctx) or ("origin" if "origin" in remotes else "")
    remote_name = args.name.strip() or prompt_text(
        "请输入远程源名称",
        default=configured_remote or "origin",
        required=True,
    )

    current_url = remote_display_url(remotes, remote_name)
    if current_url == "未设置":
        current_url = ""
    remote_url = args.url.strip() or prompt_text(
        "请输入远程仓库地址",
        default=current_url,
        required=True,
    )

    if remote_name in remotes:
        git(ctx, "remote", "set-url", remote_name, remote_url)
        git(ctx, "remote", "set-url", "--push", remote_name, remote_url)
        log(f"已更新远程源：{remote_name} -> {remote_url}")
    else:
        git(ctx, "remote", "add", remote_name, remote_url)
        log(f"已新增远程源：{remote_name} -> {remote_url}")

    set_configured_repo_task_remote(ctx, remote_name)
    log(f"已设置仓库默认远程源：{remote_name}")

    remotes = remote_map(ctx)
    for name in sorted(remotes):
        fetch_url = remotes[name].get("fetch", "未设置")
        push_url = remotes[name].get("push", "未设置")
        log(f"[fetch] {name}  {fetch_url}")
        log(f"[push] {name}  {push_url}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Repository task helpers for VS Code/Codex."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser(
        "status", help="Show branch, remote and author information."
    )
    status_parser.set_defaults(handler=cmd_status)

    switch_parser = subparsers.add_parser(
        "switch", help="Switch to an existing branch or create it."
    )
    switch_parser.add_argument("--branch", default="")
    switch_parser.set_defaults(handler=cmd_switch)

    commit_parser = subparsers.add_parser(
        "commit", help="Stage all changes and create a commit."
    )
    commit_parser.add_argument("--message", default="")
    commit_parser.set_defaults(handler=cmd_commit)

    push_parser = subparsers.add_parser(
        "push", help="Push current HEAD to a remote branch."
    )
    push_parser.add_argument("--branch", default="")
    push_parser.set_defaults(handler=cmd_push)

    pull_remote_parser = subparsers.add_parser(
        "pull-remote", help="Pull a remote branch with merge or confirmed overwrite."
    )
    pull_remote_parser.add_argument("--branch", default="")
    pull_remote_parser.set_defaults(handler=cmd_pull_remote)

    set_remote_parser = subparsers.add_parser(
        "set-remote", help="Add or update a remote binding."
    )
    set_remote_parser.add_argument("--name", default="")
    set_remote_parser.add_argument("--url", default="")
    set_remote_parser.set_defaults(handler=cmd_set_remote)

    return parser


def main() -> int:
    configure_stdio()
    parser = build_parser()
    args = parser.parse_args()
    task_name = command_display_name(args.command)
    task_started_at = current_datetime_text()
    task_started_clock = perf_counter()
    exit_code = 1

    log(f"任务开始：{task_name}")
    log(f"开始时间：{task_started_at}")

    try:
        ctx = build_repo_context()
        exit_code = args.handler(ctx, args)
        return exit_code
    except TaskError as error:
        log(str(error), stream=sys.stderr)
        return 1
    finally:
        status_text = "成功" if exit_code == 0 else "失败"
        log(f"任务结束：{task_name}（{status_text}）")
        log(
            f"结束时间：{current_datetime_text()}，总耗时 {format_duration(perf_counter() - task_started_clock)}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
