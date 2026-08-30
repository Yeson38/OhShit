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
    def test_exact_match_is_rejected_anti_copy_paste(self):
        ok, msg = validate_challenge(
            user_input="report_final_v3.docx",
            challenge="report_final_v3.docx",
        )
        assert ok is False, "完全精确一致必须被拒绝（防复制粘贴）"
        assert "复制" in msg or "粘贴" in msg or "copy" in msg.lower() or "paste" in msg.lower()

    def test_fuzzy_match_passes_with_shape_substitution(self):
        ok, msg = validate_challenge(
            user_input="Rep0rt_F1nal_v3.docx",   # o→0, i→1
            challenge="report_final_v3.docx",
        )
        assert ok is True
        assert "通过" in msg or "pass" in msg.lower()

    def test_case_insensitive_but_not_exact(self):
        # 大小写不同 = 字节级不同，不算复制粘贴，应通过
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
        # 用户不小心多加空格也算正确尝试
        ok, _ = validate_challenge(
            user_input="  Rep0rt_f1nal_v3.docx  \t",
            challenge="report_final_v3.docx",
        )
        assert ok is True


# ========== 3 次重试循环 ==========

class TestRunValidationLoop:
    def test_first_attempt_correct_passes(self, monkeypatch):
        from tests.conftest import patch_user_input
        monkeypatch.setattr('random.choice', lambda seq: seq[0])  # 强制选第一个
        patch_user_input(monkeypatch, ["Report_Final.DOCX"])   # 与 report_final.docx 大小写不同
        result, history = run_validation_loop(
            validation_pool=["report_final.docx", "thesis.pdf", "customer.sql"],
            max_attempts=3,
        )
        assert result is True

    def test_three_wrong_attempts_fails_with_rotation(self, monkeypatch):
        from tests.conftest import patch_user_input
        # 强制依次选第0、1、2个，确保三次挑战不同
        seq_tracker = {'idx': -1}
        def _force_rotate(seq):
            seq_tracker['idx'] = (seq_tracker['idx'] + 1) % len(seq)
            return seq[seq_tracker['idx']]
        monkeypatch.setattr('random.choice', _force_rotate)
        patch_user_input(monkeypatch, ["blah1", "blah2", "blah3"])
        result, history = run_validation_loop(
            validation_pool=["a.txt", "b.txt", "c.txt"],
            max_attempts=3,
        )
        assert result is False
        # 历史应记录 3 次挑战，且每次的挑战文件名不同（轮换）
        assert len(history) == 3
        challenges_used = [h["challenge"] for h in history]
        assert len(set(challenges_used)) == 3, "三次失败的挑战文件名必须轮换不同，防止死磕一个"

    def test_ctrl_c_exits_gracefully(self, monkeypatch):
        def fake_input_always_raises(*a, **kw):
            raise KeyboardInterrupt()
        monkeypatch.setattr('sys.stdin.readline', fake_input_always_raises)
        with pytest.raises(KeyboardInterrupt):
            run_validation_loop(validation_pool=["a.txt"], max_attempts=3)
