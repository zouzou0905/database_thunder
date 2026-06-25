import unittest
from decimal import Decimal

from scripts.common import (
    normalize_keyword,
    parse_history_numbers,
    parse_history_percents,
    parse_history_ranks,
    parse_int,
    parse_percent,
    parse_rank_range,
    parse_three_money_values,
    parse_two_numbers,
)


class CommonParserTests(unittest.TestCase):
    def test_normalize_keyword(self):
        self.assertEqual(normalize_keyword("  Pet   Hair Remover "), "pet hair remover")

    def test_parse_int(self):
        self.assertEqual(parse_int("155,714"), 155714)
        self.assertIsNone(parse_int("-"))

    def test_parse_percent(self):
        self.assertEqual(parse_percent("21.13%"), Decimal("0.2113"))

    def test_parse_history_ranks(self):
        self.assertEqual(
            parse_history_ranks("上月 | 4月前 | 12月前 | 197,419 | 222,858 | 158,341"),
            (197419, 222858, 158341),
        )

    def test_parse_pipe_numbers(self):
        self.assertEqual(parse_history_numbers("41,705 | 67,144 | 2,627"), (41705, 67144, 2627))
        self.assertEqual(
            parse_history_percents("21.13% | 30.13% | 1.66%"),
            (Decimal("0.2113"), Decimal("0.3013"), Decimal("0.0166")),
        )

    def test_parse_display_and_ppc(self):
        self.assertEqual(parse_two_numbers("30,712 | 449"), (Decimal("30712"), Decimal("449")))
        self.assertEqual(
            parse_three_money_values("£0.46 | £0.61 | £0.76"),
            (Decimal("0.46"), Decimal("0.61"), Decimal("0.76")),
        )

    def test_parse_rank_range_ignores_timestamp(self):
        self.assertEqual(parse_rank_range("sellersprite_aba_0001_0511.csv"), (1, 511))
        self.assertEqual(
            parse_rank_range("sellersprite_aba_batch_001_0001_0100_1780045268543.csv"),
            (1, 100),
        )
        self.assertEqual(
            parse_rank_range("sellersprite_aba_auto_done_002_0101_0187_1780045831094.csv"),
            (101, 187),
        )


if __name__ == "__main__":
    unittest.main()
