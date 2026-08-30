import pytest
from danger_guard.core.validator import (
    normalize,
    validate_challenge,
    run_validation_loop,
    ConfusableError,
)


# ========== 规范化函数单元测试 ==========

class TestNormalize:
    def test_lowercase(self):
        assert normalize("ABC") == normalize("abc") == "abc"

    def test_letter_o_vs_zero(self):
        assert normalize("hello") == normalize("hell0")
        assert normalize("O") == normalize("0") == normalize("o") == "o"

    def test_l_vs_1_vs_pipe_vs_i(self):
        assert normalize("hello|") == normalize("hello1") == normalize("hellol")
        assert normalize("I") == normalize("1") == normalize("l") == normalize("i") == "l"

    def test_s_vs_5(self):
        assert normalize("snake") == normalize("5nake")

    def test_z_vs_2(self):
        assert normalize("zebra") == normalize("2ebra")

    def test_b_vs_8(self):
        assert normalize("ball") == normalize("8all")

    def test_g_vs_9_vs_q(self):
        assert normalize("goal") == normalize("9oal")
        # q 和 o 在同一组 -> 所以 goal = qoal 但不一定 = 9oal 经过 2 轮
        # 规范化是单向映射表：9->g, q->o, 所以 "goal" == "9oal"，但 "qoal" 会变成 "ooal"
        assert normalize("goal") == normalize("9oal")

    def test_dash_family_normalized(self):
        assert normalize("A-B_C") == normalize("A—B_C") == normalize("A–B_C")

    def test_dot_family(self):
        assert normalize("file.txt") == normalize("file．txt") == normalize("file。txt")

    def test_parentheses_bracket_normalized(self):
        assert normalize("a(b)") == normalize("a（b）") == normalize("a[b]")

    def test_fullwidth_halfwidth_space(self):
        assert normalize("a b") == normalize("a　b")

    def test_slash_backslash(self):
        assert normalize("a/b") == normalize("a\\b") == normalize("a／b")


# ========== B- 判定逻辑 ==========

class TestValidateChallenge:
    # --- 新规则（方案A）：精确 = 直接通过（一次过）---
    def test_exact_match_passes_one_shot_now(self):
        ok, msg = validate_challenge(
            user_input="report_final_v3.docx",
            challenge="report_final_v3.docx",
        )
        assert ok is True, "方案A：一字不差的精确文件名应直接通过（一次过），不再当作粘贴拒绝"
        assert "通过" in msg or "pass" in msg.lower()
        assert "精确" in msg or "一字不差" in msg or "exact" in msg.lower()

    def test_fuzzy_match_passes_with_shape_substitution(self):
        ok, msg = validate_challenge(
            user_input="Rep0rt_F1nal_v3.docx",   # o→0, i→1
            challenge="report_final_v3.docx",
        )
        assert ok is True
        assert "通过" in msg or "pass" in msg.lower()

    def test_case_only_change_still_passes(self):
        # 只改大小写（与精确不等，但 normalize 同）→ 通过
        ok, _ = validate_challenge(
            user_input="Report_Final_V3.DOCX",
            challenge="report_final_v3.docx",
        )
        assert ok is True

    def test_totally_wrong_returns_false_with_distance_hint(self):
        ok, msg = validate_challenge(user_input="blahblah", challenge="report.docx")
        assert ok is False
        # 提示应包含编辑距离或"还差 N 个字符"的语义
        assert any(ch.isdigit() for ch in msg)

    def test_leading_trailing_whitespace_stripped_on_input(self):
        # 用户不小心多加空格，但去除空格后"精确匹配"也该过（一次过）
        ok, _ = validate_challenge(
            user_input="  report_final_v3.docx  \t",
            challenge="report_final_v3.docx",
        )
        assert ok is True


# ========== 3 次重试循环 ==========

class TestRunValidationLoop:
    def test_first_attempt_exact_match_passes_now(self, monkeypatch):
        """方案A：第一次就精确输对，直接通过（不再因'粘贴嫌疑'扣分）。"""
        from tests.conftest import patch_user_input
        monkeypatch.setattr('random.choice', lambda seq: seq[0])
        patch_user_input(monkeypatch, ["report_final.docx"])  # 精确一致
        # 同时 monkeypatch time.perf_counter 给一个"稍慢但不过分"的 dt (200 ms)，避免触发 paste suspect
        _t = [0.0]
        def _fake_perf():
            _t[0] += 0.2
            return _t[0]
        monkeypatch.setattr('time.perf_counter', _fake_perf)
        result, history = run_validation_loop(
            validation_pool=["report_final.docx", "thesis.pdf", "customer.sql"],
            max_attempts=3,
        )
        assert result is True
        assert history[-1]["passed"] is True

    def test_bracketed_paste_markers_are_treated_as_paste_suspect(self, monkeypatch, capsys):
        """Ctrl+Shift+V 在大多数终端会在粘贴内容前后包裹 \e[200~ ... \e[201~。
        只要读到 bracketed paste marker，无论 timing 如何都判定为粘贴（不占 quota，不看精确/模糊）。
        下一次用户去掉 marker 再慢输一遍就能通过。"""
        from tests.conftest import patch_user_input
        monkeypatch.setattr('random.choice', lambda seq: seq[0])
        # 第 1 行是 bracketed paste（\x1b[200~a.txt\x1b[201~）→ 疑似粘贴
        # 第 2 行慢输入 a.txt → 通过
        paste_line = "\x1b[200~a.txt\x1b[201~"
        patch_user_input(monkeypatch, [paste_line, "a.txt"])
        # timing: 第 1 次 paste dt=500ms(慢)，但仍应判 paste_suspect(因为 marker)；
        # 第 2 次 dt=200ms(正常)，精确匹配通过。
        timeline = [0.0, 0.500,   # paste: 慢（但有 marker → 仍判 paste suspect）
                    0.600, 0.800]  # normal
        _i = [0]
        def _tick():
            v = timeline[_i[0]]
            _i[0] += 1
            return v
        monkeypatch.setattr('time.perf_counter', _tick)
        ok, hist = run_validation_loop(validation_pool=["a.txt"], max_attempts=3)
        out = capsys.readouterr().out
        # 第 1 次一定要标 paste_suspect（因为 bracketed marker）
        assert hist[0].get("paste_suspect") is True, f"首条未标 paste_suspect: {hist[0]}"
        # 提示文案包含 "括号粘贴/bracketed/marker/粘贴" 任意一个
        assert any(kw in out for kw in ("粘贴", "括号", "Bracketed", "bracketed", "marker", "200")), f"out: {out[:400]}"
        # 最终通过
        assert ok is True, f"慢输入应通过, hist={hist}"
        # 仅 1 次真实 quota 消耗（paste_suspect 那次不占）
        real_quota = sum(1 for h in hist if not h.get("paste_suspect"))
        assert real_quota == 1

    def test_bracketed_paste_without_closing_marker(self, monkeypatch, capsys):
        """有些终端（tmux 被打断）粘贴只发了 \e[200~ 没发 201~。出现开头 ESC[200~ 就判。"""
        from tests.conftest import patch_user_input
        monkeypatch.setattr('random.choice', lambda seq: seq[0])
        patch_user_input(monkeypatch, ["\x1b[200~a.txt"])  # 开了头没收尾
        timeline = [0.0, 0.400,  # 慢 400ms，纯计时不会判
                    0.500, 0.720] # 第 2 次正常输入
        # 上面 paste 后还有一次正常通过需要再补
        _more = ["a.txt"]
        import io as _io
        monkeypatch.setattr('sys.stdin', _io.StringIO("\x1b[200~a.txt\na.txt\n"))
        _i2 = [0]
        t2 = [0.0, 0.400, 0.500, 0.720]
        def _tick2():
            v = t2[_i2[0] % len(t2)]
            _i2[0] += 1
            return v
        monkeypatch.setattr('time.perf_counter', _tick2)
        ok, hist = run_validation_loop(validation_pool=["a.txt"], max_attempts=3)
        out = capsys.readouterr().out
        assert hist[0].get("paste_suspect") is True, f"第一条应有 paste_suspect: {hist[0]}"
        # 通过
        assert ok is True, f"第二次正常输入应通过: {hist}"
        # 提示包含 paste marker 相关字样
        assert any(kw in out for kw in ("粘贴", "bracketed", "Bracketed", "200", "marker", "ESC"))

    def test_fast_input_triggers_paste_suspect_rejected(self, monkeypatch, capsys):
        """过快（< 120 ms）= 粘贴嫌疑：拒绝并提示'疑似粘贴/毫秒'，但不消耗 3 次 quota。"""
        from tests.conftest import patch_user_input
        monkeypatch.setattr('random.choice', lambda seq: seq[0])  # 固定同一题
        patch_user_input(monkeypatch, [
            "a.txt",  # 1 ms → 快
            "a.txt",  # 1 ms → 快
            "a.txt",  # 1 ms → 快
            "a.txt",  # 1 ms → 快
            "a.txt",  # 300 ms → 通过
        ])
        timeline = [
            0.000, 0.001,   # attempt 1 prompt-start, readline-end → dt=1ms
            0.002, 0.003,   # attempt 2
            0.004, 0.005,   # attempt 3
            0.006, 0.007,   # attempt 4
            0.010, 0.310,   # attempt 5 dt=300ms ≥ 120 → 通过
        ]
        _i = [0]
        def _tick():
            v = timeline[_i[0]]
            _i[0] += 1
            return v
        monkeypatch.setattr('time.perf_counter', _tick)
        result, history = run_validation_loop(
            validation_pool=["a.txt", "b.txt", "c.txt"],
            max_attempts=3,
        )
        out = capsys.readouterr().out
        assert any(kw in out for kw in ("过快", "粘贴", "毫秒", "ms", "疑似")), f"got: {out[:400]}"
        paste_count = sum(1 for h in history if h.get("paste_suspect"))
        assert paste_count >= 4, f"paste_suspect 只有 {paste_count} 条: {history}"
        assert result is True, f"第 5 次慢速应通过，却失败 history={history[-3:]}"

    def test_paste_suspect_does_not_consume_quota(self, monkeypatch, capsys):
        """前 3 次过快都不占 quota → 不触发'耗尽 3 次'；再放慢 1 次精确直接通过。"""
        from tests.conftest import patch_user_input
        monkeypatch.setattr('random.choice', lambda seq: seq[0])  # 固定题
        patch_user_input(monkeypatch, [
            "x.txt",   # 过快 1
            "x.txt",   # 过快 2
            "x.txt",   # 过快 3
            "x.txt",   # 通过（慢）
        ])
        timeline = [0.0, 0.001, 0.010, 0.020, 0.030, 0.200, 0.500]
        _i = [0]
        def _tick():
            v = timeline[_i[0]]
            _i[0] += 1
            return v
        monkeypatch.setattr('time.perf_counter', _tick)
        ok, hist = run_validation_loop(
            validation_pool=["x.txt"],
            max_attempts=3,
        )
        assert ok is True, f"前 3 次 paste_suspect 不应消耗 quota，第 4 次应该正常通过，hist={hist}"
        assert "耗尽" not in capsys.readouterr().out

    def test_ctrl_c_exits_gracefully_no_stack(self, monkeypatch, capsys):
        """Ctrl+C 不再冒泡到外层抛栈；Validator 内部 catch 后返回 False，并标 cancelled=True。"""
        class _RaiseOnRead:
            def readline(self):
                raise KeyboardInterrupt()
        monkeypatch.setattr('sys.stdin', _RaiseOnRead())
        # 现在 run_validation_loop 不应 raise，而应返回 (False, history)，history 里有一条 cancelled
        ok, hist = run_validation_loop(validation_pool=["a.txt"], max_attempts=3)
        assert ok is False, "Ctrl+C 之后应返回 (False, ...)"
        assert any(h.get("cancelled") and "Ctrl" in h.get("message","") for h in hist), f"没有 cancelled 记录: {hist}"
        out = capsys.readouterr().out
        # 用户侧提示应含 "已取消/Ctrl+C/中断"，但不可有 Traceback / KeyboardInterrupt（由上层 engine/__main__ 捕获）
        assert any(kw in out for kw in ("已取消", "Ctrl+C", "中断", "取消"))
        assert "Traceback" not in out
        assert "KeyboardInterrupt" not in out
