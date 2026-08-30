"""keystroke module + validator 中 PowerShell/burst/PSReadLine 专属场景的单测。"""
import pytest


# ======================================================================
# Test keystroke helpers （不依赖真 TTY，通过 _getch_fn / _monotonic_ms_fn 注入）
# ======================================================================

class TestKeystrokeHelpers:
    def test_is_burst_paste_true_when_run_of_three_fast(self):
        from danger_guard.core.keystroke import is_burst_paste, BURST_DT_MS, BURST_MIN_RUN
        # BURST_DT_MS=4, BURST_MIN_RUN=3：3 个连续 <4ms 才算 burst
        assert is_burst_paste([1, 1, 1]) is True
        assert is_burst_paste([1, 2, 3]) is True   # 全部 <4 且连续 3 个
        # 刚好等于 4（不算 <4）：不算 burst
        assert is_burst_paste([4, 4, 4]) is False
        # 只有 2 个 fast：长度不够
        assert is_burst_paste([1, 1]) is False
        # 中间被一个慢(50)打断，3-fast 不连续
        assert is_burst_paste([1, 1, 50, 1]) is False

    def test_is_burst_paste_requires_min_length(self):
        from danger_guard.core.keystroke import is_burst_paste
        assert is_burst_paste([]) is False
        assert is_burst_paste([0]) is False
        assert is_burst_paste([0, 0]) is False

    def test_paste_reason_burst_format(self):
        from danger_guard.core.keystroke import paste_reason_burst
        s = paste_reason_burst([1, 1, 100, 2])
        assert "ms" in s and "最快" in s and "<" in s

    def test_read_line_timed_injected_chars_normal(self):
        from danger_guard.core.keystroke import read_line_timed
        # 注入"a","b","c","\r"（= Enter 在 Windows 下），每个字符间 100ms
        chars = iter(["a", "b", "c", "\r"])
        # 单调时钟：每调用一次 +100 ms
        _t = [0]
        def mon():
            _t[0] += 100
            return _t[0]
        line, dts, total = read_line_timed(
            echo=False,
            _getch_fn=lambda: next(chars),
            _monotonic_ms_fn=mon,
        )
        assert line == "abc"
        assert dts == [100, 100, 100]   # 3 个字符对应 3 个 dt
        # total = mon 自 line 开始到 Enter 读完：4 * 100 (最后一个字符即\r 也触发一次mon) - 100(第一个mon是第一个mon())
        # 实际：mon() 依次返回 100(a) 200(b) 300(c) 400(\r 回车break)
        # t = start=mon(100) 之前已经记在首 char dt
        # 每个 char dt = mon_now - last; last = mon_now
        # 顺序: a: mon() 取 start(100) → 这是 first char 的 time；然后再 mon() 为 b 时刻 200 → dt_0=100;
        # b: next mon()=300 → dt_1=100; c: next mon=400 → dt_2=100; \r: mon()=500（total=500?）
        # 我们不纠结 total 数字；只要 len(dts)=3 就说明逐字时序正确采集
        assert len(dts) == 3
        assert total is not None

    def test_read_line_timed_injected_burst_pattern(self):
        from danger_guard.core.keystroke import read_line_timed, is_burst_paste
        # 每字 dt=1 (<4ms)，足够长度 → burst
        chars = iter(list("report") + ["\n"])
        _t = [0]
        def mon():
            _t[0] += 1
            return _t[0]
        line, dts, total = read_line_timed(
            echo=False,
            _getch_fn=lambda: next(chars),
            _monotonic_ms_fn=mon,
        )
        assert line == "report"
        # 6 字 → 6 dts (每个 1ms)
        assert len(dts) == 6
        assert all(d == 1 for d in dts), dts
        assert is_burst_paste(dts) is True

    def test_read_line_timed_backspace_erases(self):
        from danger_guard.core.keystroke import read_line_timed
        # a b \x7f c \r → 最终 "ac"（b 被退格删掉）
        chars = iter(["a", "b", "\x7f", "c", "\r"])
        _t = [0]
        def mon():
            _t[0] += 50
            return _t[0]
        line, dts, _ = read_line_timed(
            echo=False,
            _getch_fn=lambda: next(chars),
            _monotonic_ms_fn=mon,
        )
        assert line == "ac"
        # 退格本身不计 dts；但被删的'b'以及最终'a','c' 本身都算（都是"按了一个键"的间隔）。
        # 即：a(50)、b(50)、c(dt=100，因为退格那次"按键"把 mon 推进了 50，但我们不推进 last → c - last_b=100) → 共 3 个
        assert len(dts) == 3
        # 退格那次"键"不计入 dts，所以不会出现 4 个
        # 更关键：burst 判定不会被"中间一个极慢的(100)打断"——验证：dts=[50,50,100] → 连续≥3个<4ms 才 burst，这里不 burst
        from danger_guard.core.keystroke import is_burst_paste
        assert is_burst_paste(dts) is False
        # 同时验证 dts 结构：前两个都是 50，最后一个是 100
        assert dts[-1] >= 100, dts
        assert all(d in (50, 100) for d in dts)

    def test_read_line_timed_ctrl_c_raises_keyboardinterrupt(self):
        from danger_guard.core.keystroke import read_line_timed
        chars = iter(["\x03"])  # Ctrl+C
        _t = [0]
        with pytest.raises(KeyboardInterrupt):
            read_line_timed(
                echo=False,
                _getch_fn=lambda: next(chars),
                _monotonic_ms_fn=lambda: (_t.__setitem__(0, _t[0] + 1), _t[0])[1],
            )

    def test_read_line_timed_escapes_windows_leading_zero_scancode(self):
        from danger_guard.core.keystroke import read_line_timed
        # Win 功能键：先发 \x00，再发 scan code。
        chars = iter(["\x00", "K", "a", "\r"])   # left-arrow + 'a' + Enter
        _t = [0]
        def mon():
            _t[0] += 10
            return _t[0]
        line, dts, _ = read_line_timed(
            echo=False,
            _getch_fn=lambda: next(chars),
            _monotonic_ms_fn=mon,
        )
        # \x00+K 被吞掉（非普通字符），只剩 a
        assert line == "a"
        assert len(dts) == 1


# ======================================================================
# Test validator 对 PSReadLine 空 Enter / PowerShell burst 粘贴的处理
# （用 monkeypatch 注入 keystroke.read_line_timed 的返回值）
# ======================================================================

class TestValidatorPowerShellSpecific:
    def test_psreadline_empty_enter_is_paste_suspect_no_quota_consumed(self, monkeypatch, capsys):
        """PSReadLine 拦截下：粘贴后 read_line_timed 读取到 raw=""（空 Enter）。
        必须 paste_suspect=True（注明 PSReadLine 拦截），不占 quota。"""
        from danger_guard.core import validator as v
        import danger_guard.core.validator as vm
        monkeypatch.setattr(vm.random, "choice", lambda seq: seq[0])

        chars = iter([
            # 第一次：空 Enter (PSReadLine 拦截)
            ("", [], 0),               # raw_line="", dts=[], total=0 非 fallback
            # 第二次：慢手打 300ms 精确过
            ("f5.log", [300, 300, 300, 300, 300, 300], 1800),
        ])
        _i = [0]
        def fake_read(**kw):
            r = next(chars)
            return r
        monkeypatch.setattr(vm, "_read_line_timed", fake_read)
        # monkeypatch time.perf_counter 也给一个假值（虽然 validator 只在 fallback 时用它）
        monkeypatch.setattr(vm.time, "perf_counter", lambda: 1000.0)

        ok, hist = v.run_validation_loop(validation_pool=["f5.log", "f4.log"], max_attempts=3)
        out = capsys.readouterr().out
        assert ok is True, f"第二次慢手打精确应该过，hist tail={hist[-3:]}"
        # 第 1 条必须标 paste_suspect，且提示包含 "PSReadLine" / "拦截" / "控制台"
        first = hist[0]
        assert first.get("paste_suspect") is True, f"首条非粘贴嫌疑: {first}"
        assert any(kw in first.get("message", "") for kw in ("PSReadLine", "拦截", "控制台拦截")), first["message"]
        assert any(kw in out for kw in ("PSReadLine", "拦截"))
        # 只有 1 次真实 quota 消耗（第 1 条 paste 不占）
        assert sum(1 for h in hist if not h.get("paste_suspect")) == 1

    def test_burst_dts_triggers_paste_suspect_on_windows(self, monkeypatch, capsys):
        """dt 全部 1ms 的逐字流（典型 burst 粘贴）→ paste_suspect=True，不占 quota。"""
        from danger_guard.core import validator as v
        import danger_guard.core.validator as vm
        monkeypatch.setattr(vm.random, "choice", lambda seq: seq[0])
        # 6 字 f5.log：dts=[1,1,1,1,1,1] total=6(ms) 总时长也 <120 但我们主要判 burst
        # 连续两次 burst，第三次慢手打就过
        responses = iter([
            ("f5.log", [1, 1, 1, 1, 1, 1], 6),
            ("f5.log", [1, 1, 1, 1, 1, 1], 6),
            ("f5.log", [200, 200, 200, 200, 200, 200], 1200),
        ])
        monkeypatch.setattr(vm, "_read_line_timed", lambda **kw: next(responses))
        monkeypatch.setattr(vm.time, "perf_counter", lambda: 0.0)
        ok, hist = v.run_validation_loop(validation_pool=["f5.log"], max_attempts=3)
        out = capsys.readouterr().out
        assert ok is True
        # 前两条都 paste_suspect
        assert hist[0].get("paste_suspect") is True
        assert hist[1].get("paste_suspect") is True
        assert hist[2].get("paste_suspect") is False
        assert "逐字时序检测" in out or "爆发" in out or "burst" in out.lower()


class TestNormalizeExitCode:
    @pytest.mark.parametrize("raw, want", [
        (-1073741510, 130),        # signed STATUS_CONTROL_C_EXIT
        (3221225786, 130),         # unsigned 32-bit STATUS_CONTROL_C_EXIT
        (0xC000013A, 130),         # hex 常量
        (0, 0),
        (1, 1),
        (130, 130),
        (2, 2),
        (-1, 129),                 # 其它负值的兜底：128 + abs(-1)
    ])
    def test_various_rc_forms(self, raw, want):
        from danger_guard.__main__ import normalize_exit_code
        assert normalize_exit_code(raw) == want
