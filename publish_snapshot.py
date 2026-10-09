#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Push the rendered dashboard to the cloud so the Kindle can read it remotely.

WHY THIS EXISTS
    The normal setup is LAN-only: the Kindle talks straight to the PC bridge on
    :8765, which only works while both sit on the same WiFi. This script breaks
    that tie by turning the dashboard into a SNAPSHOT: it asks the local bridge
    for the same PNG the Kindle would have fetched, then uploads it (plus
    status.json) to a cloud file host. The Kindle then reads a fixed https URL
    from anywhere -- no LAN, no tunnel, no open port, and the PC is never
    reachable from the internet (it only ever makes outbound requests).

    The PC going offline does not blank the Kindle: the last pushed snapshot
    stays up until the next successful push.

BACKEND
    GitHub (free tier) via the Contents API. Chosen because it needs no payment
    method, gives a stable raw URL, and needs no local git (this machine does
    not even have git on PATH). Every push is one commit, so keep the interval
    sane (default 5 min) rather than pushing every refresh cycle.

USAGE
    python publish_snapshot.py --check      # verify repo/token, print the URL
    python publish_snapshot.py --once       # push one snapshot and exit
    python publish_snapshot.py --once --dry-run
    python publish_snapshot.py --loop       # keep pushing every N seconds

CONFIG
    publish.ini next to this file (see publish.ini.example). Never commit it --
    it holds your token. Env vars override: WB_GH_TOKEN, WB_GH_REPO, WB_GH_OWNER.
"""

import argparse
import base64
import configparser
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(HERE, "publish.ini")
API = "https://api.github.com"

DEFAULTS = {
    "backend": "github",
    "owner": "",
    "repo": "",
    "branch": "main",
    "token": "",
    "png_path": "cover.png",
    "json_path": "status.json",
    "push_status": "true",
    "bridge": "http://127.0.0.1:8765",
    "width": "1072",
    "height": "1448",
    "theme": "dark",
    "interval": "300",
    # single = rewrite history to ONE commit per push (repo size stays flat,
    #          no manual cleanup ever); append = one commit per push (history
    #          grows ~18MB/day at the default interval).
    "history": "single",
}


LOGPATH = os.path.join(HERE, "publish.log")


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line)
    # Also write to publish.log: the launcher uses pythonw, which has no
    # console, so shell redirection cannot be relied on to capture anything.
    try:
        with open(LOGPATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---- config -------------------------------------------------------------
def load_config(path):
    cfg = dict(DEFAULTS)
    cp = configparser.ConfigParser()
    if os.path.exists(path):
        try:
            cp.read(path, encoding="utf-8")
        except Exception as e:
            log("配置文件读取失败 (%s)，使用默认值: %s" % (path, e))
        if cp.has_section("publish"):
            for k in DEFAULTS:
                if cp.has_option("publish", k):
                    cfg[k] = cp.get("publish", k).strip()
    # env overrides (safer than keeping the token on disk)
    if os.environ.get("WB_GH_TOKEN"):
        cfg["token"] = os.environ["WB_GH_TOKEN"].strip()
    if os.environ.get("WB_GH_OWNER"):
        cfg["owner"] = os.environ["WB_GH_OWNER"].strip()
    if os.environ.get("WB_GH_REPO"):
        cfg["repo"] = os.environ["WB_GH_REPO"].strip()
    cfg["push_status"] = cfg["push_status"].lower() in ("1", "true", "yes", "on")
    return cfg


def validate(cfg):
    missing = [k for k in ("owner", "repo", "token") if not cfg.get(k)]
    if missing:
        raise RuntimeError(
            "publish.ini 缺少配置: %s —— 复制 publish.ini.example 为 publish.ini 并填写"
            % ", ".join(missing))
    if cfg["backend"] != "github":
        raise RuntimeError("目前只实现 github 后端，backend=%r" % cfg["backend"])


# ---- GitHub Contents API ------------------------------------------------
def _req(url, token, method="GET", body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "workbuddy-koreader-monitor")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    # ProxyHandler({}) ignores any system proxy -- the bridge is local and a
    # corporate proxy would happily break 127.0.0.1 requests.
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with op.open(req, timeout=40) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = b""
        try:
            raw = e.read()
        except Exception:
            pass
        try:
            obj = json.loads(raw) if raw else {}
        except Exception:
            obj = {"message": raw[:200].decode("utf-8", "replace")}
        return e.code, obj


def _contents_url(cfg, path, with_ref=False):
    url = "%s/repos/%s/%s/contents/%s" % (
        API, urllib.parse.quote(cfg["owner"], safe=""),
        urllib.parse.quote(cfg["repo"], safe=""),
        urllib.parse.quote(path, safe="/"))
    if with_ref:
        url += "?ref=" + urllib.parse.quote(cfg["branch"], safe="")
    return url


def gh_get_sha(cfg, path):
    """Current blob sha of `path`, or None when the file does not exist yet."""
    st, obj = _req(_contents_url(cfg, path, with_ref=True), cfg["token"])
    if st == 200:
        return obj.get("sha")
    if st == 404:
        return None
    raise RuntimeError("读取 %s 失败: HTTP %s %s" % (path, st, obj.get("message")))


def blob_sha(data):
    """Git blob object id -- lets us compare against the remote sha WITHOUT
    downloading the file back. Used to skip no-op pushes."""
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def gh_put(cfg, path, data, message):
    """Create or update `path` in one commit.

    Returns (changed, existed). `changed=False` means the remote already held
    byte-identical content and NO commit was made -- essential for the loop
    mode, where pushing every few minutes would otherwise pile up ~300 commits
    a day (each storing a full PNG) and bloat the repo fast.
    """
    body = {
        "message": message,
        "content": base64.b64encode(data).decode("ascii"),
        "branch": cfg["branch"],
    }
    sha = gh_get_sha(cfg, path)
    if sha and sha == blob_sha(data):
        return False, True
    if sha:
        body["sha"] = sha       # required to update an existing file
    st, obj = _req(_contents_url(cfg, path), cfg["token"], "PUT", body)
    if st in (200, 201):
        return True, sha is not None
    raise RuntimeError("上传 %s 失败: HTTP %s %s" % (path, st, obj.get("message")))


def gh_check(cfg):
    st, obj = _req("%s/repos/%s/%s" % (
        API, urllib.parse.quote(cfg["owner"], safe=""),
        urllib.parse.quote(cfg["repo"], safe="")), cfg["token"])
    if st != 200:
        raise RuntimeError("访问仓库失败: HTTP %s %s" % (st, obj.get("message")))
    return obj


# ---- Git Database API: keep the repo at ONE commit forever ---------------
# The plain Contents API appends a commit per push. At the default 5-minute
# interval that is ~300 commits/day, each carrying a full PNG -- the repo
# would grow by ~18MB a day and need periodic manual cleanup.
#
# A snapshot repo has no use for history: only the latest image matters. So we
# publish through the Git Database API instead -- build a tree with just the
# two files, create a ROOT commit (no parents), and force-move the branch to
# it. History depth stays 1, old objects become unreachable and get GC'd, and
# the public raw URL never changes. Fully automatic, no cleanup ever.

def _git_url(cfg, tail):
    return "%s/repos/%s/%s/git/%s" % (
        API, urllib.parse.quote(cfg["owner"], safe=""),
        urllib.parse.quote(cfg["repo"], safe=""), tail)


def gh_git_blob(cfg, data):
    st, obj = _req(_git_url(cfg, "blobs"), cfg["token"], "POST", {
        "content": base64.b64encode(data).decode("ascii"),
        "encoding": "base64",
    })
    if st not in (200, 201):
        raise RuntimeError("创建 blob 失败: HTTP %s %s" % (st, obj.get("message")))
    return obj["sha"]


def gh_git_tree(cfg, entries):
    """entries = [(path, blob_sha), ...] -> tree sha."""
    st, obj = _req(_git_url(cfg, "trees"), cfg["token"], "POST", {
        "tree": [{"path": p, "mode": "100644", "type": "blob", "sha": s}
                 for p, s in entries],
    })
    if st not in (200, 201):
        raise RuntimeError("创建 tree 失败: HTTP %s %s" % (st, obj.get("message")))
    return obj["sha"]


def gh_git_commit(cfg, tree_sha, message):
    """Create a ROOT commit (no parents) -- this is what keeps history at 1."""
    body = {"message": message, "tree": tree_sha, "parents": []}
    st, obj = _req(_git_url(cfg, "commits"), cfg["token"], "POST", body)
    if st not in (200, 201):
        # some API versions reject an explicit empty parents list
        st, obj = _req(_git_url(cfg, "commits"), cfg["token"], "POST",
                       {"message": message, "tree": tree_sha})
    if st not in (200, 201):
        raise RuntimeError("创建 commit 失败: HTTP %s %s" % (st, obj.get("message")))
    return obj["sha"]


def gh_current_tree(cfg):
    """Tree sha currently at the branch tip, or None when the branch is empty."""
    st, obj = _req(_git_url(cfg, "refs/heads/" + cfg["branch"]), cfg["token"])
    if st != 200:
        return None
    commit_sha = (obj.get("object") or {}).get("sha")
    if not commit_sha:
        return None
    st, obj = _req(_git_url(cfg, "commits/" + commit_sha), cfg["token"])
    if st != 200:
        return None
    return (obj.get("tree") or {}).get("sha")


def gh_git_set_ref(cfg, commit_sha):
    """Force-move the branch to commit_sha, creating it if it does not exist."""
    ref = "refs/heads/" + cfg["branch"]
    # NOTE: the update endpoint is /git/refs/heads/<branch> -- "heads/" is
    # required here, while the create endpoint below takes the full ref name.
    st, obj = _req(_git_url(cfg, "refs/heads/" + cfg["branch"]), cfg["token"],
                   "PATCH", {"sha": commit_sha, "force": True})
    if st == 200:
        return True
    if st == 404 or st == 422:
        st, obj = _req(_git_url(cfg, "refs"), cfg["token"], "POST",
                       {"ref": ref, "sha": commit_sha})
        if st in (200, 201):
            return True
    raise RuntimeError("更新分支 %s 失败: HTTP %s %s"
                       % (cfg["branch"], st, obj.get("message")))


def push_single_commit(cfg, files, message):
    """Publish `files` as the repo's ONE AND ONLY commit. Returns changed(bool)."""
    entries = [(path, gh_git_blob(cfg, data)) for path, data in files]
    tree = gh_git_tree(cfg, entries)
    if gh_current_tree(cfg) == tree:
        return False            # identical content -> no commit at all
    gh_git_set_ref(cfg, gh_git_commit(cfg, tree, message))
    return True


# ---- local bridge -------------------------------------------------------
def fetch_bytes(url, timeout=20):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with op.open(url, timeout=timeout) as r:
        return r.read()


def cover_url(cfg, theme="dark"):
    """Per-theme cover URL from the local bridge. We now push BOTH a dark and a
    light cover every cycle so the Kindle can switch skins in remote (cloud)
    mode too -- there the static PNG's query string is ignored by the CDN and
    the theme is baked into the FILE NAME (cover_dark.png / cover_light.png)."""
    return "%s/cover.png?w=%s&h=%s&layout=grouped&mono=1&theme=%s" % (
        cfg["bridge"].rstrip("/"), cfg["width"], cfg["height"], theme)


def base_url(cfg):
    """What the Kindle fills into 设置桥地址 -- the plugin appends /cover.png."""
    return "https://raw.githubusercontent.com/%s/%s/%s" % (
        cfg["owner"], cfg["repo"], cfg["branch"])


def cover_file_url(cfg):
    """The full PNG URL, for eyeballing in a browser."""
    return base_url(cfg) + "/" + cfg["png_path"].lstrip("/")


# ---- the actual push ----------------------------------------------------
def publish_once(cfg, dry_run=False):
    # Push BOTH themes so the Kindle can switch skins in remote (cloud) mode.
    # In remote mode the static file's query string is ignored by the CDN, so
    # the theme must be baked into the file name: cover_dark.png / cover_light.png.
    covers = {}
    for theme in ("dark", "light"):
        try:
            data = fetch_bytes(cover_url(cfg, theme))
        except Exception as e:
            log("封面(主题=%s)获取失败: %s" % (theme, e))
            continue
        # PNG magic -- a bridge that is up but misconfigured returns HTML/JSON.
        if not data.startswith(b"\x89PNG"):
            log("桥返回的不是 PNG（主题=%s，前 8 字节=%r）—— 检查 bridge/width/height"
                % (theme, data[:8]))
            continue
        covers[theme] = data

    if not covers:
        raise RuntimeError("两种主题封面都获取失败 —— 检查桥是否在运行 / width / height")

    status = None
    if cfg["push_status"]:
        try:
            status = fetch_bytes(cfg["bridge"].rstrip("/") + "/status.json")
            json.loads(status.decode("utf-8"))     # sanity: must be JSON
        except Exception as e:
            log("status.json 获取失败（跳过，不影响封面）: %s" % e)
            status = None

    msg = "workbuddy snapshot %s" % time.strftime("%Y-%m-%d %H:%M:%S")
    if dry_run:
        for theme, data in covers.items():
            log("dry-run: cover_%s.png %d 字节" % (theme, len(data)))
        log("dry-run: status.json %s —— 未上传"
            % (("%d 字节" % len(status)) if status else "不推送"))
        log("dry-run: 目标 %s:%s/ (cover_dark.png + cover_light.png)"
            % (cfg["owner"], cfg["repo"]))
        log("dry-run: Kindle 桥地址填 → %s" % base_url(cfg))
        log("dry-run: 暗色直链 → %s/cover_dark.png" % base_url(cfg))
        log("dry-run: 亮色直链 → %s/cover_light.png" % base_url(cfg))
        return True

    files = [("cover_%s.png" % theme, data) for theme, data in covers.items()]
    # Backward-compat / fallback: also keep a plain `cover.png` (light-preferred)
    # so an older single-cover plugin -- or a future Kindle-side fallback -- still
    # resolves, and a stale single-cover publisher can never wipe the only file
    # the current plugin needs. The single-commit tree is exactly `files`, so
    # including cover.png here is what keeps it alive on GitHub.
    fallback = covers.get("light") or covers.get("dark")
    if fallback:
        files.append(("cover.png", fallback))
    if status:
        files.append((cfg["json_path"], status))

    if str(cfg.get("history", "single")).lower() == "single":
        changed = push_single_commit(cfg, files, msg)
        if changed:
            names = ", ".join(p for p, _ in files)
            log("已发布 [%s]%s —— 历史重写为单个 commit"
                % (names, (" + status.json" if status else "")))
        else:
            log("内容与远端一致，跳过（未产生 commit）")
        return True

    # append mode: one commit per push. History grows -- see `history` in ini.
    changed, existed = gh_put(cfg, cfg["png_path"], png, msg)
    if changed:
        log("封面已上传 %d 字节（%s）" % (len(png), "更新" if existed else "新建"))
    else:
        log("封面与远端一致，跳过（不产生 commit）")
    if status:
        try:
            c2, e2 = gh_put(cfg, cfg["json_path"], status, msg)
            if c2:
                log("status.json 已上传 %d 字节（%s）"
                    % (len(status), "更新" if e2 else "新建"))
            else:
                log("status.json 无变化，跳过")
        except Exception as e:
            log("status.json 上传失败（封面已成功）: %s" % e)
    return True


# ---- entry point --------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="把看板快照推送到 GitHub，供 Kindle 远程查看")
    ap.add_argument("--config", default=DEFAULT_CONFIG, help="publish.ini 路径")
    ap.add_argument("--once", action="store_true", help="推送一次后退出")
    ap.add_argument("--loop", action="store_true", help="按间隔持续推送")
    ap.add_argument("--interval", type=int, default=0, help="推送间隔（秒）")
    ap.add_argument("--check", action="store_true", help="只验证仓库/token 并打印地址")
    ap.add_argument("--dry-run", action="store_true", help="取数据但不上传")
    args = ap.parse_args()

    cfg = load_config(args.config)
    try:
        validate(cfg)
    except RuntimeError as e:
        log(str(e))
        return 2

    if args.check:
        try:
            info = gh_check(cfg)
            log("仓库 OK: %s (private=%s)" % (info.get("full_name"), info.get("private")))
            log("Kindle 桥地址填这个：")
            log("  https://raw.githubusercontent.com/%s/%s/%s"
                % (cfg["owner"], cfg["repo"], cfg["branch"]))
            log("即封面文件 %s 必须存在于该仓库根目录/对应路径" % cfg["png_path"])
            return 0
        except Exception as e:
            log(str(e))
            return 1

    if not (args.once or args.loop):
        ap.print_help()
        return 2

    interval = args.interval or int(cfg["interval"] or 300)

    if args.once:
        try:
            publish_once(cfg, args.dry_run)
            return 0
        except Exception as e:
            log("推送失败: %s" % e)
            return 1

    log("开始持续推送，间隔 %d 秒，Ctrl+C 停止（每轮自动重载 publish.ini）" % interval)
    while True:
        # Re-read publish.ini every round so editing the config (interval, token,
        # branch, ...) takes effect WITHOUT restarting the publisher.
        try:
            cfg = load_config(args.config)
            validate(cfg)
            # Re-read interval every round too, so editing it in publish.ini
            # takes effect on the next cycle WITHOUT restarting the publisher.
            if not args.interval:
                interval = int(cfg["interval"] or 300)
        except RuntimeError as e:
            log(str(e))
            try:
                time.sleep(interval)
            except KeyboardInterrupt:
                log("已停止")
                return 0
            continue
        try:
            publish_once(cfg, args.dry_run)
        except KeyboardInterrupt:
            log("已停止")
            return 0
        except Exception as e:
            log("推送失败: %s" % e)
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            log("已停止")
            return 0


if __name__ == "__main__":
    sys.exit(main())
