from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
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
    cache_dir: Path


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
        "push-current": "仓库：推送当前分支",
        "push-branch": "仓库：推送指定分支",
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
    cache_dir = root / "temp" / "git_tasks"
    return RepoContext(git_exe=git_exe, root=root, cache_dir=cache_dir)


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


def task_cache_path(ctx: RepoContext, task_key: str) -> Path:
    if not re.fullmatch(r"[a-z0-9-]+", task_key):
        raise TaskError(f"任务缓存名称不合法：{task_key}")
    return ctx.cache_dir / f"{task_key}.json"


def load_task_cache(ctx: RepoContext, task_key: str) -> dict[str, Any]:
    cache_path = task_cache_path(ctx, task_key)
    if not cache_path.exists():
        return {}

    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_task_cache(ctx: RepoContext, task_key: str, **updates: str | None) -> None:
    cache = load_task_cache(ctx, task_key)
    for key, value in updates.items():
        if value is None:
            continue
        text = value.strip()
        if text:
            cache[key] = text

    cache_path = task_cache_path(ctx, task_key)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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


def resolve_remote(ctx: RepoContext, task_key: str, explicit_remote: str) -> tuple[str, str]:
    remote_input = explicit_remote.strip()
    if remote_input:
        return remote_input, "手动输入"

    cache = load_task_cache(ctx, task_key)
    cached_remote = str(cache.get("last_remote", "")).strip()
    if cached_remote:
        return cached_remote, "当前任务缓存"

    upstream = current_upstream(ctx)
    if upstream and upstream.get("remote"):
        return upstream["remote"], "当前上游"

    return "origin", "默认值"


def resolve_target_branch(
    ctx: RepoContext, task_key: str, explicit_branch: str
) -> tuple[str, str]:
    branch_input = explicit_branch.strip()
    if branch_input:
        return branch_input, "手动输入"

    cache = load_task_cache(ctx, task_key)
    cached_branch = str(cache.get("last_branch", "")).strip()
    if cached_branch:
        return cached_branch, "当前任务缓存"

    return ensure_branch(ctx), "当前分支"


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


def confirm_force_push() -> bool:
    print_section("推送冲突")
    log("检测到远程分支存在未合并提交，普通推送已被 Git 拒绝。")
    log("如果确认要覆盖远程分支，请输入 Y 或 yes 继续强制推送。")
    log("输入其他内容或直接回车将取消。")
    try:
        answer = input(f"[{current_time_text()}] 是否执行强制推送？[y/N]: ").strip().lower()
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
    task_key: str,
    push_args: list[str],
    force_push_args: list[str],
    success_message: str,
    force_success_message: str,
    remote_name: str,
    branch_name: str,
) -> int:
    push_started = perf_counter()
    log("开始执行普通推送...")
    result = git_stream(ctx, *push_args, check=False)
    if result.returncode == 0:
        save_task_cache(ctx, task_key, last_remote=remote_name, last_branch=branch_name)
        log(f"{success_message}，命令耗时 {format_duration(perf_counter() - push_started)}")
        return 0

    if not is_non_fast_forward_push_error(result):
        raise TaskError(
            f"普通推送失败，命令耗时 {format_duration(perf_counter() - push_started)}。"
            " 详细输出见上方日志。"
        )

    log(f"普通推送失败，命令耗时 {format_duration(perf_counter() - push_started)}")

    if not sys.stdin.isatty():
        raise TaskError("当前终端不可交互，无法确认是否强制推送。")

    if not confirm_force_push():
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

    save_task_cache(ctx, task_key, last_remote=remote_name, last_branch=branch_name)
    log(
        f"{force_success_message}，命令耗时 {format_duration(perf_counter() - force_started)}"
    )
    return 0


def print_section(title: str) -> None:
    log()
    log(f"== {title} ==")


def print_remotes(ctx: RepoContext) -> None:
    remotes = remote_map(ctx)
    upstream = current_upstream(ctx)

    print_section("远程仓库")
    if not remotes:
        log("未配置任何远程仓库。")
        log('示例：git remote add origin https://github.com/your-name/your-repo.git')
        return

    for name in sorted(remotes):
        markers: list[str] = []
        if upstream and name == upstream.get("remote"):
            markers.append("当前上游")

        marker_text = f" [{'、'.join(markers)}]" if markers else ""
        fetch_url = remotes[name].get("fetch", "未设置")
        push_url = remotes[name].get("push", fetch_url)
        log(f"- {name}{marker_text}")
        log(f"  fetch: {fetch_url}")
        log(f"  push:  {push_url}")


def cmd_status(ctx: RepoContext, _: argparse.Namespace) -> int:
    branch = current_branch(ctx)
    upstream = current_upstream(ctx)
    author_name = git_config(ctx, "user.name")
    author_email = git_config(ctx, "user.email")

    print_section("仓库信息")
    log(f"仓库根目录: {ctx.root}")
    log(f"Git 路径: {ctx.git_exe}")

    print_section("当前分支")
    if branch:
        log(f"当前分支: {branch}")
    else:
        log("当前分支: 未检测到（可能处于 detached HEAD 状态）")

    if upstream:
        log(f"当前上游: {upstream['full']}")
        if branch:
            log(f"当前绑定: {branch} -> {upstream['full']}")
    else:
        log("当前上游: 未设置")
        log(f"示例：git push -u origin {branch or '<branch>'}")

    print_remotes(ctx)

    print_section("作者信息")
    if author_name:
        log(f"user.name : {author_name}")
    else:
        log("user.name : 未设置")
        log('示例：git config --global user.name "Your Name"')

    if author_email:
        log(f"user.email: {author_email}")
    else:
        log("user.email: 未设置")
        log('示例：git config --global user.email "name@example.com"')

    return 0


def cmd_switch(ctx: RepoContext, args: argparse.Namespace) -> int:
    branch_name = args.branch.strip()
    if not branch_name:
        raise TaskError("分支名称不能为空。")
    ensure_valid_branch_name(ctx, branch_name)

    if local_branch_exists(ctx, branch_name):
        git(ctx, "switch", branch_name)
        log(f"已切换到已有分支：{branch_name}")
        save_task_cache(ctx, "switch", last_branch=branch_name)
        return 0

    remote_name, remote_source = resolve_remote(ctx, "switch", args.remote)
    ensure_remote_exists(ctx, remote_name)
    log(f"使用远程源: {remote_name}（来源：{remote_source}）")

    log(f"本地分支不存在，正在检查远程分支：{remote_name}/{branch_name}")
    if fetch_remote_branch(ctx, remote_name, branch_name):
        git(ctx, "switch", "--track", "-c", branch_name, f"{remote_name}/{branch_name}")
        log(f"已基于远程分支创建并切换：{branch_name} -> {remote_name}/{branch_name}")
        log("开始拉取远程分支最新内容...")
        git_stream(ctx, "pull", "--ff-only", remote_name, branch_name)
        log(f"已拉取远程分支最新内容：{remote_name}/{branch_name}")
    else:
        git(ctx, "switch", "-c", branch_name)
        log(f"远程分支不存在，已创建并切换到新本地分支：{branch_name}")
        log(f"后续运行“仓库：推送当前分支”会创建远程分支：{remote_name}/{branch_name}")

    save_task_cache(ctx, "switch", last_remote=remote_name, last_branch=branch_name)
    return 0


def cmd_commit(ctx: RepoContext, args: argparse.Namespace) -> int:
    message = args.message.strip()
    if not message:
        raise TaskError("提交说明不能为空。")

    commit_all_changes(ctx, message)
    return 0


def commit_all_changes(ctx: RepoContext, message: str) -> bool:
    changed = git_stdout(ctx, "status", "--short", check=False)
    if not changed:
        log("当前没有可提交的改动。")
        return False

    git(ctx, "add", "-A")

    print_section("即将提交的改动")
    log(git_stdout(ctx, "status", "--short", check=False) or "无")

    result = git(ctx, "commit", "-m", message)
    log(result.stdout.strip() or "提交完成。")
    return True


def cmd_push_current(ctx: RepoContext, args: argparse.Namespace) -> int:
    branch_name = ensure_branch(ctx)
    remote_name, source = resolve_remote(ctx, "push-current", args.remote)
    ensure_remote_exists(ctx, remote_name)

    log(f"使用远程源: {remote_name}（来源：{source}）")
    return run_push_with_optional_force(
        ctx,
        "push-current",
        ["push", "-u", remote_name, branch_name],
        ["push", "--force", "-u", remote_name, branch_name],
        f"已推送当前分支到 {remote_name}/{branch_name}",
        f"已强制推送当前分支到 {remote_name}/{branch_name}",
        remote_name,
        branch_name,
    )


def cmd_push_branch(ctx: RepoContext, args: argparse.Namespace) -> int:
    remote_name, remote_source = resolve_remote(ctx, "push-branch", args.remote)
    ensure_remote_exists(ctx, remote_name)
    target_branch, branch_source = resolve_target_branch(
        ctx, "push-branch", args.branch
    )

    log(f"使用远程源: {remote_name}（来源：{remote_source}）")
    log(f"目标分支: {target_branch}（来源：{branch_source}）")
    return run_push_with_optional_force(
        ctx,
        "push-branch",
        ["push", remote_name, f"HEAD:{target_branch}"],
        ["push", "--force", remote_name, f"HEAD:{target_branch}"],
        f"已将当前内容推送到 {remote_name}/{target_branch}",
        f"已强制将当前内容推送到 {remote_name}/{target_branch}",
        remote_name,
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
    remote_name = args.remote.strip()
    branch_name = args.branch.strip()

    if not remote_name:
        raise TaskError("远程源名称不能为空。")
    if not branch_name:
        raise TaskError("远程分支名称不能为空。")
    ensure_valid_branch_name(ctx, branch_name)
    ensure_remote_exists(ctx, remote_name)

    log(f"使用远程源: {remote_name}")
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
            save_task_cache(ctx, "pull-remote", last_remote=remote_name, last_branch=branch_name)
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
        save_task_cache(ctx, "pull-remote", last_remote=remote_name, last_branch=branch_name)
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
    save_task_cache(ctx, "pull-remote", last_remote=remote_name, last_branch=branch_name)
    log(
        f"已拉取并切换到远程分支 {upstream_ref}，命令耗时 "
        f"{format_duration(perf_counter() - pull_started)}"
    )
    return 0


def cmd_set_remote(ctx: RepoContext, args: argparse.Namespace) -> int:
    remote_name = args.name.strip()
    remote_url = args.url.strip()

    if not remote_name:
        raise TaskError("远程源名称不能为空。")
    if not remote_url:
        raise TaskError("远程仓库地址不能为空。")

    remotes = remote_map(ctx)
    if remote_name in remotes:
        git(ctx, "remote", "set-url", remote_name, remote_url)
        git(ctx, "remote", "set-url", "--push", remote_name, remote_url)
        log(f"已更新远程源：{remote_name} -> {remote_url}")
    else:
        git(ctx, "remote", "add", remote_name, remote_url)
        log(f"已新增远程源：{remote_name} -> {remote_url}")

    save_task_cache(ctx, "set-remote", last_remote=remote_name, last_url=remote_url)
    print_remotes(ctx)
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
    switch_parser.add_argument("--branch", required=True)
    switch_parser.add_argument("--remote", default="")
    switch_parser.set_defaults(handler=cmd_switch)

    commit_parser = subparsers.add_parser(
        "commit", help="Stage all changes and create a commit."
    )
    commit_parser.add_argument("--message", required=True)
    commit_parser.set_defaults(handler=cmd_commit)

    push_current_parser = subparsers.add_parser(
        "push-current", help="Push current branch to a remote."
    )
    push_current_parser.add_argument("--remote", default="")
    push_current_parser.set_defaults(handler=cmd_push_current)

    push_branch_parser = subparsers.add_parser(
        "push-branch", help="Push current HEAD to a target remote branch."
    )
    push_branch_parser.add_argument("--remote", default="")
    push_branch_parser.add_argument("--branch", default="")
    push_branch_parser.set_defaults(handler=cmd_push_branch)

    pull_remote_parser = subparsers.add_parser(
        "pull-remote", help="Pull a remote branch with merge or confirmed overwrite."
    )
    pull_remote_parser.add_argument("--remote", required=True)
    pull_remote_parser.add_argument("--branch", required=True)
    pull_remote_parser.set_defaults(handler=cmd_pull_remote)

    set_remote_parser = subparsers.add_parser(
        "set-remote", help="Add or update a remote binding."
    )
    set_remote_parser.add_argument("--name", required=True)
    set_remote_parser.add_argument("--url", required=True)
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
