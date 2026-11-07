import unittest

from courseflow.weeks import looks_like_week_expression, parse_weeks


class WeekParsingTests(unittest.TestCase):
    def test_plain_range(self):
        self.assertEqual(parse_weeks("1-16周"), set(range(1, 17)))

    def test_single_week_words(self):
        self.assertEqual(parse_weeks("第三周"), {3})
        self.assertEqual(parse_weeks("第2周"), {2})

    def test_chinese_range(self):
        self.assertEqual(parse_weeks("三至十六周"), set(range(3, 17)))

    def test_mixed_list(self):
        self.assertEqual(
            parse_weeks("1-4,6,8-10周"),
            {1, 2, 3, 4, 6, 8, 9, 10},
        )
        self.assertEqual(
            parse_weeks("第1-4周,第6周"),
            {1, 2, 3, 4, 6},
        )
        self.assertEqual(
            parse_weeks("1-4周,6周"),
            {1, 2, 3, 4, 6},
        )

    def test_odd_even_modifiers(self):
        odd = {1, 3, 5, 7, 9, 11, 13, 15}
        even = {2, 4, 6, 8, 10, 12, 14, 16}
        self.assertEqual(parse_weeks("1-16周(单)"), odd)
        self.assertEqual(parse_weeks("1-16周\uff08单周\uff09"), odd)
        self.assertEqual(parse_weeks("1-16周 单周"), odd)
        self.assertEqual(parse_weeks("1-16周(双)"), even)
        self.assertEqual(parse_weeks("1-16周\uff08双周\uff09"), even)

    def test_full_semester_words(self):
        self.assertEqual(parse_weeks("单周"), {1, 3, 5, 7, 9, 11, 13, 15})
        self.assertEqual(parse_weeks("双周"), {2, 4, 6, 8, 10, 12, 14, 16})
        self.assertEqual(parse_weeks("每周"), set(range(1, 17)))
        self.assertEqual(parse_weeks("全周"), set(range(1, 17)))

    def test_unknown_is_not_full_semester(self):
        self.assertIsNone(parse_weeks("考试周"))
        self.assertIsNone(parse_weeks("abc"))
        self.assertIsNone(parse_weeks(""))
        self.assertIsNone(parse_weeks("1-16周(单双)"))

    def test_looks_like_expression(self):
        self.assertTrue(looks_like_week_expression("1-16周(单)"))
        self.assertTrue(looks_like_week_expression("1-4,6,8-10周"))
        self.assertFalse(looks_like_week_expression("1-16"))
        self.assertFalse(looks_like_week_expression("考试周"))
        self.assertFalse(looks_like_week_expression("A101"))


if __name__ == "__main__":
    unittest.main()
