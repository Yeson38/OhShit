"""危险包装器：dd hook。dd key=value 解析 + 块设备检测 + 大小估算 + 执行调度。"""
import os
import stat
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

from danger_guard.hooks.base import BaseHook, PreviewResult, HookExecutionResult
from danger_guard.hooks import register_hook
from danger_guard.executors import dispatch_exec

_MULTIPLIERS = {
    "": 1, "B": 1,
    "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4,
    "KB": 1000, "MB": 1000**2, "GB": 1000**3, "TB": 1000**4,
}

def _parse_bytesize(token: str) -> int:
    """`4M` -> 4*1024**2；纯数字 `512` -> 512；空或非法 -> 0"""
    if not token:
        return 0
    i = len(token) - 1
    while i >= 0 and not token[i].isdigit():
        i -= 1
    if i < 0:
        return 0
    num_part = token[:i+1]
    suf_part = token[i+1:].upper()
    try:
        num = int(num_part)
    except ValueError:
        return 0
    if suf_part not in _MULTIPLIERS:
        # unknown suffix → just take the number (conservative)
        return num
    return num * _MULTIPLIERS[suf_part]


@dataclass
class DdParsed:
    dd_if: str = ""
    dd_of: str = ""
    bs: str = ""
    ibs: str = ""
    obs: str = ""
    count: str = ""
    skip: str = ""
    seek: str = ""
    conv: str = ""
    status: str = ""
    iflag: str = ""
    oflag: str = ""
    extra_pairs: Dict[str, str] = field(default_factory=dict)


@register_hook
class DdHook(BaseHook):
    name = "dd"
    native_commands = ("dd",)

    def parse_args(self, raw_args: List[str]) -> DdParsed:
        """解析 dd 传统 `key=value` 形式。不能用 shlex 直接切，因为 shell 传入的已是 argv 列表。"""
        p = DdParsed()
        for a in raw_args:
            if a.startswith("--"):
                p.extra_pairs[f"__flag__{a[2:]}"] = ""
                continue
            eq = a.find("=")
            if eq == -1:
                # dd 对裸 token 会报错，但我们放 extra_pairs 留痕
                p.extra_pairs[f"__unknown__{a}"] = ""
                continue
            k, v = a[:eq], a[eq+1:]
            self._apply(p, k, v)
        return p

    @staticmethod
    def _apply(p: DdParsed, k: str, v: str):
        if k == "if":
            p.dd_if = v
        elif k == "of":
            p.dd_of = v
        elif k == "bs":
            p.bs = v
        elif k == "ibs":
            p.ibs = v
        elif k == "obs":
            p.obs = v
        elif k == "count":
            p.count = v
        elif k == "skip":
            p.skip = v
        elif k == "seek":
            p.seek = v
        elif k == "conv":
            p.conv = v
        elif k == "status":
            p.status = v
        elif k == "iflag":
            p.iflag = v
        elif k == "oflag":
            p.oflag = v
        else:
            p.extra_pairs[k] = v

    # ---------- preview ----------
    def preview(self, parsed: DdParsed) -> PreviewResult:
        warnings: List[str] = []
        sample_items: List[str] = []

        if parsed.dd_if:
            if self._is_block_device(parsed.dd_if):
                warnings.append(f"⚠ 输入源是块设备 (block device): {parsed.dd_if}")
        if parsed.dd_of:
            # 只把输出目标放入 sample_items（是真正会被修改的对象；affected_count=1）
            sample_items.append(f"<of>  {parsed.dd_of}")
            if self._is_block_device(parsed.dd_of):
                warnings.append(f"⚠ 高风险：输出目标是块设备 (block device): {parsed.dd_of} —— 直接覆写磁盘/分区")
            if not sample_items and parsed.dd_if:
                # 仅当没有 of 时才把 if 放进 sample_items（极少数情况：dd if=... 打印到 stdout）
                sample_items.append(f"<if>  {parsed.dd_if}")
        elif parsed.dd_if:
            sample_items.append(f"<if>  {parsed.dd_if}")

        # 总大小估算：bs * count；没 bs 用 ibs/obs 的任一个
        bs_val = (
            _parse_bytesize(parsed.bs) or
            _parse_bytesize(parsed.obs) or
            _parse_bytesize(parsed.ibs) or
            512
        )
        count_val = _parse_bytesize(parsed.count)  # count 数字，K/M 也支持但不常见
        # seek 表示跳过 N 个 obs 后写，通常意味着文件至少 (seek+count)*bs
        seek_val = _parse_bytesize(parsed.seek)
        total = bs_val * (count_val + seek_val)

        # 如果未指定 count（dd 一直读到 EOF），估算无法给上限 → 视为高危
        no_size_upper = (parsed.count == "")
        if no_size_upper and not total:
            total = 0

        target_scope_parts = []
        if parsed.dd_if:
            target_scope_parts.append(f"if={parsed.dd_if}")
        if parsed.dd_of:
            target_scope_parts.append(f"of={parsed.dd_of}")
        target_scope = " → ".join(target_scope_parts) if target_scope_parts else "<no targets>"

        risk = 1
        if self._is_block_device(parsed.dd_of) or "/dev/sd" in parsed.dd_of or parsed.dd_of.startswith("/dev/nvme"):
            risk = 3
        elif self._is_block_device(parsed.dd_if) and total >= 1024**3:
            risk = 3
        elif no_size_upper:
            risk = 2 if risk < 2 else risk
        elif total >= 1024**3:
            risk = 3
        elif total >= 100 * 1024**2:
            risk = max(risk, 2)

        # validation_pool：挑 of/if 里的 basename，外加 2-3 个常见磁盘镜像文件名
        pool_src: List[str] = []
        for pth in (parsed.dd_of, parsed.dd_if):
            if not pth:
                continue
            bn = os.path.basename(pth)
            if bn and bn not in pool_src:
                pool_src.append(bn)
        pads = ["backup_20260830.img", "disk_dump.bin", "customer_sda.raw"]
        for pad in pads:
            if pad not in pool_src:
                pool_src.append(pad)
            if len(pool_src) >= 5:
                break

        return PreviewResult(
            affected_count=1,
            total_size_bytes=total,
            sample_items=sample_items,
            target_scope=target_scope,
            risk_level=risk,
            validation_pool=pool_src,
            extra_warnings=warnings,
        )

    @staticmethod
    def _is_block_device(path: str) -> bool:
        """用 stat.S_ISBLK 判断；不存在/无权限/空路径返回 False。"""
        if not path:
            return False
        try:
            st = os.stat(path)
        except (OSError, ValueError):
            return False
        return stat.S_ISBLK(st.st_mode)

    def execute(self, parsed: DdParsed, dry_run: bool = False) -> HookExecutionResult:
        # 将 DdParsed dataclass 转换为 posix_exec.build_dd_command 期望的 dict 结构：
        # - dd_if → if，dd_of → of（因为 if/of 是 Python 保留字，dataclass 字段需改名）
        # - extra_pairs → extra_flags（list of CLI tokens）
        d = asdict(parsed)
        # 字段重映射
        if "dd_if" in d:
            d["if"] = d.pop("dd_if")
        if "dd_of" in d:
            d["of"] = d.pop("dd_of")
        # extra_pairs → extra_flags
        extra_pairs = d.pop("extra_pairs", {})
        extra_flags: List[str] = []
        for k, v in extra_pairs.items():
            if k.startswith("__flag__"):
                extra_flags.append(f"--{k[8:]}")
            elif k.startswith("__unknown__"):
                extra_flags.append(k[11:])
            elif v:
                extra_flags.append(f"{k}={v}")
            else:
                extra_flags.append(k)
        d["extra_flags"] = extra_flags
        return dispatch_exec("dd", d, dry_run)
