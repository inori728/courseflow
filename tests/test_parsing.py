import unittest

from courseflow.parsing import _parse_cell, _tokenize_cell, parse_grid


class CellParsingTests(unittest.TestCase):
    def test_parenthesized_single_week_is_not_a_course(self):
        parsed = _parse_cell("高等数学 1-16周\uff08单\uff09 教一A101")
        self.assertEqual(parsed, [("高等数学", "教一A101", "1-16周\uff08单\uff09")])

    def test_space_separated_single_week_keeps_modifier(self):
        parsed = _parse_cell("高等数学 1-16周 单周 教一A101")
        self.assertEqual(parsed, [("高等数学", "教一A101", "1-16周单周")])

    def test_mixed_week_list_keeps_room(self):
        parsed = _parse_cell("高等数学 1-4,6,8-10周 教一A101")
        self.assertEqual(parsed, [("高等数学", "教一A101", "1-4,6,8-10周")])

    def test_two_courses_in_one_cell(self):
        parsed = _parse_cell("高数 1-16周 A101 英语 1-8周 B202")
        self.assertEqual(parsed, [
            ("高数", "A101", "1-16周"),
            ("英语", "B202", "1-8周"),
        ])

    def test_room_number_is_not_parsed_as_week(self):
        tokens = _tokenize_cell("高数 1-16周 东4-201")
        self.assertEqual(tokens, ["高数", "1-16周", "东4-201"])

    def test_parse_grid_basic(self):
        rows = [
            ["节次", "周一", "周二", "周三"],
            ["1-2", "高数 1-16周 A101", "", ""],
        ]
        courses = parse_grid(rows)
        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0].name, "高数")
        self.assertEqual(courses[0].room, "A101")
        self.assertEqual(courses[0].weeks, "1-16周")
        self.assertEqual((courses[0].day, courses[0].start, courses[0].end), (0, 1, 2))

    def test_unknown_text_is_not_a_fake_week(self):
        parsed = _parse_cell("习题课 考试周 A101")
        self.assertEqual(parsed[0][2], "")


if __name__ == "__main__":
    unittest.main()
