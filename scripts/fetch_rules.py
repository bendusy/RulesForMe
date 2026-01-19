#!/usr/bin/env python3
"""根据 manifest 下载远程规则文件 (并行版 multithreaded)。"""

from __future__ import annotations

import argparse
import sys
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Set, Tuple

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:  # pragma: no cover
    print("ERROR: 需要安装 requests，请运行 'pip install requests'。", file=sys.stderr)
    sys.exit(1)

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rulesforme import ManifestError, ManifestSource, RulesetManifest, load_manifest  # noqa: E402


DEFAULT_TIMEOUT = 30
DEFAULT_MAX_WORKERS = 10
DEFAULT_RETRIES = 3


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="下载 manifest 中定义的远程规则文件")
    parser.add_argument(
        "--manifest",
        default=str(ROOT_DIR / "config" / "ruleset_manifest.yaml"),
        help="manifest 文件位置",
    )
    parser.add_argument(
        "--sources",
        nargs="*",
        help="仅下载指定 source id",
    )
    parser.add_argument(
        "--categories",
        nargs="*",
        help="限制在指定分类",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印将要执行的下载",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"超时时间，默认 {DEFAULT_TIMEOUT}",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help=f"并发线程数，默认 {DEFAULT_MAX_WORKERS}",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="显示详细日志",
    )
    return parser.parse_args()


def determine_source_ids(manifest: RulesetManifest, args: argparse.Namespace) -> List[str]:
    if args.sources:
        return args.sources
    if args.categories:
        source_ids: Set[str] = set()
        for cat_name in args.categories:
            if cat_name not in manifest.categories:
                raise ManifestError(f"未知分类: {cat_name}")
            source_ids.update(manifest.categories[cat_name].sources)
        return sorted(source_ids)
    return [sid for sid, src in manifest.sources.items() if src.type == "remote"]


def resolve_destination(manifest: RulesetManifest, source: ManifestSource) -> Path:
    target_path = Path(source.target)
    if target_path.parts and target_path.parts[0] == manifest.defaults.cache_root:
        relative = Path(*target_path.parts[1:]) if len(target_path.parts) > 1 else Path("")
        dest_root = ROOT_DIR / manifest.defaults.cache_root
        dest = dest_root / relative
    else:
        dest_root = ROOT_DIR / manifest.defaults.download_root
        dest = dest_root / target_path
    return dest


def create_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=DEFAULT_RETRIES,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; RulesForMe-Bot/1.0)"
    })
    return session


def process_source(
    session: requests.Session,
    source: ManifestSource,
    dest: Path,
    timeout: int,
    dry_run: bool
) -> Tuple[bool, str]:
    """
    Returns: (success, message)
    """
    if source.uri is None:
        return False, f"Source {source.id} 缺少 URI"

    if dry_run:
        return True, f"[DRY-RUN] {source.uri} -> {dest}"

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest.with_suffix(dest.suffix + ".tmp")

    try:
        # 使用 verify=True 确保安全，如果确实遇到证书问题可考虑 flag 控制
        with session.get(source.uri, timeout=timeout, stream=True) as response:
            response.raise_for_status()
            with tmp_path.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        fh.write(chunk)
    except Exception as exc:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        
        err_msg = f"下载失败 {source.id}: {exc}"
        if source.critical:
            # Critical errors usually stop the show, but in parallel we log them and return False
            return False, f"[CRITICAL] {err_msg}"
        return False, f"[WARN] {err_msg}"

    tmp_path.replace(dest)
    return True, f"成功: {source.id}"


def main() -> int:
    args = parse_args()
    setup_logging(args.verbose)
    
    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as exc:
        logging.error(f"载入 manifest 失败: {exc}")
        return 1

    try:
        source_ids = determine_source_ids(manifest, args)
    except ManifestError as exc:
        logging.error(f"参数错误: {exc}")
        return 1

    if not source_ids:
        logging.info("无可下载的 source")
        return 0

    logging.info(f"准备下载 {len(source_ids)} 个源，并发数: {args.workers}")

    # 准备任务
    tasks = []
    # 我们为每个线程创建一个 session 或者是共用一个 session?
    # requests.Session 是线程安全的，但 adapter pool size 需要匹配 workers
    # 简单起见，共用一个配置好 pool 的 session
    session = create_session()
    # 调整连接池大小以匹配 workers
    adapter = session.adapters["https://"]
    if isinstance(adapter, HTTPAdapter):
        # 重新 mount 以更新 pool size
        new_adapter = HTTPAdapter(
            pool_connections=args.workers,
            pool_maxsize=args.workers,
            max_retries=adapter.max_retries
        )
        session.mount("https://", new_adapter)
        session.mount("http://", new_adapter)

    final_success = True
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {}
        for sid in source_ids:
            try:
                source = manifest.source_for(sid)
            except ManifestError as exc:
                logging.error(f"配置错误 ({sid}): {exc}")
                final_success = False
                continue
            
            if source.type != "remote":
                continue
            
            dest = resolve_destination(manifest, source)
            future = executor.submit(
                process_source, session, source, dest, args.timeout, args.dry_run
            )
            future_map[future] = source

        # 收集结果
        for future in as_completed(future_map):
            source = future_map[future]
            try:
                success, msg = future.result()
                if success:
                    logging.info(msg)
                else:
                    logging.error(msg)
                    if source.critical:
                        final_success = False
            except Exception as exc:
                logging.error(f"未捕获异常 ({source.id}): {exc}")
                if source.critical:
                    final_success = False

    return 0 if final_success else 1


if __name__ == "__main__":
    sys.exit(main())
