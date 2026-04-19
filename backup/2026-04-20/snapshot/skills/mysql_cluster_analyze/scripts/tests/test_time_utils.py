#!/usr/bin/env python3
"""
test_time_utils.py — _beijing_to_unix / _unix_to_beijing 单元测试

时区转换是所有时序查询的核心，偏差会导致指标时间全部对不上。
"""

import sys
import unittest
from pathlib import Path

# 将 atomic 目录加入 import 路径
sys.path.insert(0, str(Path(__file__).parent.parent / "atomic"))

from query_xray_metrics import _beijing_to_unix, _unix_to_beijing


class TestBeijingToUnix(unittest.TestCase):
    """测试北京时间字符串 → Unix timestamp 转换。"""

    def test_known_epoch(self):
        """1970-01-01 08:00:00 北京时间 = Unix 0。"""
        self.assertEqual(_beijing_to_unix("1970-01-01 08:00:00"), 0)

    def test_known_timestamp(self):
        """2026-04-02 04:25:00 北京时间 = 2026-04-01 20:25:00 UTC。"""
        ts = _beijing_to_unix("2026-04-02 04:25:00")
        # UTC: 2026-04-01 20:25:00
        # 手动计算验证
        import calendar
        from datetime import datetime
        expected = calendar.timegm(datetime(2026, 4, 1, 20, 25, 0).timetuple())
        self.assertEqual(ts, expected)

    def test_iso_format(self):
        """支持 T 分隔的 ISO 格式。"""
        ts1 = _beijing_to_unix("2026-04-02 04:25:00")
        ts2 = _beijing_to_unix("2026-04-02T04:25:00")
        self.assertEqual(ts1, ts2)

    def test_midnight_boundary(self):
        """午夜边界：北京 00:00 = 前一天 UTC 16:00。"""
        ts = _beijing_to_unix("2026-04-02 00:00:00")
        expected_beijing = "2026-04-02 00:00:00"
        # 反转验证
        self.assertEqual(_unix_to_beijing(ts), expected_beijing)

    def test_invalid_format_raises(self):
        """无法解析的格式应抛出 ValueError。"""
        with self.assertRaises(ValueError):
            _beijing_to_unix("04/02/2026 04:25:00")

    def test_empty_string_raises(self):
        """空字符串应抛出 ValueError。"""
        with self.assertRaises(ValueError):
            _beijing_to_unix("")


class TestUnixToBeijing(unittest.TestCase):
    """测试 Unix timestamp → 北京时间字符串转换。"""

    def test_epoch_zero(self):
        """Unix 0 = 北京时间 1970-01-01 08:00:00。"""
        self.assertEqual(_unix_to_beijing(0), "1970-01-01 08:00:00")

    def test_roundtrip(self):
        """北京时间 → Unix → 北京时间 往返一致。"""
        original = "2026-04-02 04:25:00"
        ts = _beijing_to_unix(original)
        result = _unix_to_beijing(ts)
        self.assertEqual(result, original)

    def test_roundtrip_multiple(self):
        """多组时间往返一致。"""
        cases = [
            "2026-01-01 00:00:00",
            "2026-06-15 12:30:45",
            "2026-12-31 23:59:59",
            "2026-04-02 04:48:00",
        ]
        for t in cases:
            with self.subTest(t=t):
                self.assertEqual(_unix_to_beijing(_beijing_to_unix(t)), t)


if __name__ == "__main__":
    unittest.main()
