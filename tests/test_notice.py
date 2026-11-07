import copy
from datetime import date, time
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from courseflow.model import Course, Timetable
from courseflow.notice import NoticeError, NoticeIntent, accept_preview, find_candidates, preview_notice
from courseflow.schedule import resolve_course
from courseflow.source import load_source, save_source


def timetable():
    clocks = {1: (time(8), time(8, 45)), 2: (time(8, 50), time(9, 35)),
              5: (time(14), time(14, 45)), 6: (time(14, 50), time(15, 35)),
              7: (time(16), time(16, 45)), 8: (time(16, 50), time(17, 35))}
    return Timetable(semester_start=date(2026, 9, 7), weeks_total=16, period_times=clocks,
                     courses=[Course("体育", 1, 7, 8, "操场", "1-16周"),
                              Course("体育", 3, 7, 8, "体育馆", "1-16周")])


def intent(**changes):
    fields = dict(course_name="体育", source_week=7, target_week=9, target_day=4, target_time="14:00")
    fields.update(changes)
    return NoticeIntent(**fields)


class NotificationTests(unittest.TestCase):
    def test_cross_week_preserves_existing_target_week_and_original_input(self):
        original = timetable()
        before = copy.deepcopy(original)
        draft = intent()
        candidates = find_candidates(original, draft)
        self.assertEqual(len(candidates), 2)
        preview = preview_notice(original, draft, [candidates[0]])
        changed = accept_preview(original, preview)
        occurrences = resolve_course(changed.courses[0], 16)
        self.assertEqual(original, before)
        self.assertFalse(any(o.week == 7 for o in occurrences))
        self.assertEqual(len([o for o in occurrences if o.week == 9]), 2)
        self.assertTrue(any(o.week == 9 and o.day == 1 and o.start == 7 for o in occurrences))
        self.assertTrue(any(o.week == 9 and o.day == 4 and o.start == 5 and o.end == 6 for o in occurrences))
        self.assertEqual(len(occurrences), 16)
        self.assertEqual(len(resolve_course(changed.courses[1], 16)), 16)

    def test_select_all_same_destination_requires_resolution(self):
        tt, draft = timetable(), intent()
        preview = preview_notice(tt, draft, find_candidates(tt, draft))
        self.assertTrue(preview.new_conflicts)
        with self.assertRaises(NoticeError):
            accept_preview(tt, preview)

    def test_each_selected_occurrence_can_have_its_own_destination(self):
        tt, draft = timetable(), intent()
        candidates = find_candidates(tt, draft)
        preview = preview_notice(tt, draft, candidates, {candidates[1].token: {"target_day": 5}})
        self.assertEqual(preview.new_conflicts, [])
        changed = accept_preview(tt, preview)
        self.assertEqual(changed.courses[1].changes[0].day, 5)

    def test_move_can_collide_with_same_courses_regular_target_occurrence(self):
        tt = timetable()
        draft = intent(target_day=1, target_periods="7-8", target_time="")
        preview = preview_notice(tt, draft, find_candidates(tt, draft)[:1])
        self.assertTrue(any("两次课" in text for text in preview.new_conflicts))

    def test_cancel_does_not_mistake_shorter_old_conflict_for_new_conflict(self):
        tt = timetable()
        tt.courses.append(Course("其他课", 1, 7, 8, "A101", "1-16周"))
        draft = intent(action="cancel")
        preview = preview_notice(tt, draft, find_candidates(tt, draft)[:1])
        self.assertEqual(preview.new_conflicts, [])
        changed = accept_preview(tt, preview)
        self.assertEqual(changed.courses[0].skip, [7])

    def test_missing_weekday_and_unmapped_clock_are_not_guessed(self):
        tt = timetable()
        for draft in [intent(target_day=None), intent(target_time="14:15")]:
            with self.assertRaises(NoticeError):
                preview_notice(tt, draft, find_candidates(tt, draft)[:1])

    def test_changed_timetable_invalidates_preview(self):
        tt, draft = timetable(), intent()
        preview = preview_notice(tt, draft, find_candidates(tt, draft)[:1])
        tt.courses[0].room = "新地点"
        with self.assertRaises(NoticeError):
            accept_preview(tt, preview)

    def test_cross_week_yaml_roundtrip_keeps_original_and_target_weeks(self):
        tt, draft = timetable(), intent()
        changed = accept_preview(tt, preview_notice(tt, draft, find_candidates(tt, draft)[:1]))
        with TemporaryDirectory() as folder:
            path = Path(folder) / "课程.yaml"
            save_source(changed, path)
            again = load_source(path)
        change = again.courses[0].changes[0]
        self.assertEqual((change.week, change.target_week), (7, 9))
        self.assertEqual(again.warnings, [])

    def test_duration_is_checked_using_actual_period_times(self):
        tt = timetable()
        tt.period_times[6] = (time(14, 50), time(15, 20))
        draft = intent()
        with self.assertRaisesRegex(NoticeError, "时长"):
            preview_notice(tt, draft, find_candidates(tt, draft)[:1])

    def test_original_week_with_two_classes_needs_selection(self):
        tt, draft = timetable(), intent()
        with self.assertRaises(NoticeError):
            preview_notice(tt, draft, [])

    def test_zero_per_candidate_target_week_is_rejected_instead_of_defaulted(self):
        tt, draft = timetable(), intent()
        candidate = find_candidates(tt, draft)[0]
        for week in (0, ""):
            with self.assertRaises(NoticeError):
                preview_notice(tt, draft, [candidate], {candidate.token: {"target_week": week}})


if __name__ == "__main__":
    unittest.main()
