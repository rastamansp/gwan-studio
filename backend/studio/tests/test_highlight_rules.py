"""
F17 — testes das regras puras de highlight (domain/highlight_rules.py).
Sem banco, sem Django ORM: `python manage.py test studio.tests.test_highlight_rules`.
"""
from django.test import SimpleTestCase

from domain.highlight_rules import Interval, filter_by_importance, merge_moments


class FilterByImportanceTests(SimpleTestCase):
    def test_keeps_only_moments_at_or_above_threshold(self):
        moments = [
            {'importancia': 9},
            {'importancia': 4},
            {'importancia': 5},
        ]
        result = filter_by_importance(moments, importancia_min=5)
        self.assertEqual([m['importancia'] for m in result], [9, 5])

    def test_empty_input_returns_empty(self):
        self.assertEqual(filter_by_importance([], importancia_min=5), [])


class MergeMomentsTests(SimpleTestCase):
    def test_no_moments_returns_no_intervals(self):
        self.assertEqual(merge_moments([], duration_sec=100, pre_roll=6, post_roll=8, merge_gap=4), [])

    def test_single_moment_applies_pre_and_post_roll(self):
        moments = [{'timestamp': 50.0}]
        result = merge_moments(moments, duration_sec=100, pre_roll=6, post_roll=8, merge_gap=4)
        self.assertEqual(result, [Interval(start=44.0, end=58.0)])

    def test_moment_near_start_clamps_to_zero(self):
        moments = [{'timestamp': 2.0}]
        result = merge_moments(moments, duration_sec=100, pre_roll=6, post_roll=8, merge_gap=4)
        self.assertEqual(result[0].start, 0.0)

    def test_moment_near_end_clamps_to_duration(self):
        moments = [{'timestamp': 98.0}]
        result = merge_moments(moments, duration_sec=100, pre_roll=6, post_roll=8, merge_gap=4)
        self.assertEqual(result[0].end, 100.0)

    def test_close_moments_are_merged_into_one_interval(self):
        # Intervalos brutos: [14,28] e [36,50] — gap de 8s entre eles, <= merge_gap=8 → une.
        moments = [{'timestamp': 20.0}, {'timestamp': 42.0}]
        result = merge_moments(moments, duration_sec=100, pre_roll=6, post_roll=8, merge_gap=8)
        self.assertEqual(result, [Interval(start=14.0, end=50.0)])

    def test_distant_moments_stay_separate(self):
        moments = [{'timestamp': 10.0}, {'timestamp': 90.0}]
        result = merge_moments(moments, duration_sec=100, pre_roll=6, post_roll=8, merge_gap=4)
        self.assertEqual(len(result), 2)

    def test_unsorted_input_is_sorted_before_merging(self):
        moments = [{'timestamp': 90.0}, {'timestamp': 10.0}]
        result = merge_moments(moments, duration_sec=100, pre_roll=6, post_roll=8, merge_gap=4)
        self.assertEqual(len(result), 2)
        self.assertLess(result[0].start, result[1].start)
