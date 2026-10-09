import copy
import unittest
from practice import validate_question, generate_practice


class PracticeTests(unittest.TestCase):
    nodes = [{'id': 'n1', 'title': '增长率', 'evidenceRefs': [{'sourceId': 's1', 'startMs': 0, 'endMs': 10, 'quote': '增长率等于增长量除以基期'}]}]

    def question(self):
        return {'nodeId': 'n1', 'sourceIds': ['s1'], 'kind': 'single', 'task': 'calculation',
                'title': '增长率', 'prompt': '从150增加到180，增长率多少？',
                'options': ['10%', '20%', '30%', '40%'], 'answerIndex': 1,
                'explanation': '（180-150）/150×100%=20%', 'distractorReasons': ['计算错误', '', '把增长量当百分比', '计算错误'],
                'takeaway': '分母使用基期', 'scenario': 'adapted',
                'calculation': {'expression': '(180-150)/150*100', 'value': 20, 'optionValues': [10, 20, 30, 40]}, 'diagram': None}

    def test_valid_calculation_is_checked(self):
        self.assertEqual(validate_question(self.question(), self.nodes)['answerIndex'], 1)

    def test_wrong_answer_is_rejected(self):
        q = self.question(); q['answerIndex'] = 2
        with self.assertRaises(ValueError): validate_question(q, self.nodes)

    def test_unknown_evidence_is_rejected(self):
        q = self.question(); q['sourceIds'] = ['invented']
        with self.assertRaises(ValueError): validate_question(q, self.nodes)

    def test_no_arbitrary_generated_svg(self):
        q = self.question(); q['diagram'] = {'kind': 'svg', 'svg': '<svg/>'}
        with self.assertRaises(ValueError): validate_question(q, self.nodes)

    def test_chart_answer_must_match_its_data(self):
        q = self.question(); q['diagram'] = {'kind': 'bar', 'title': '销量', 'unit': '件',
            'values': [{'label': '去年', 'value': 100}, {'label': '今年', 'value': 180}],
            'check': {'operation': 'growth_rate', 'fromIndex': 0, 'toIndex': 1}}
        with self.assertRaises(ValueError): validate_question(q, self.nodes)

    def test_invalid_questions_are_dropped_without_retry(self):
        bad = self.question(); bad['answerIndex'] = 3
        calls = []
        def ask(payload): calls.append(payload); return {'questions': [bad, self.question()]}
        result = generate_practice(self.nodes, [], 3, 'basic', ask_json=ask)
        self.assertEqual(len(result['questions']), 1)
        self.assertEqual(result['rejectedCount'], 1)
        self.assertEqual(len(calls), 1)

    def test_duplicate_options_are_rejected(self):
        q = self.question(); q['options'][0] = q['options'][1]
        with self.assertRaises(ValueError): validate_question(q, self.nodes)

    def test_numeric_option_text_must_match_the_checked_value(self):
        q = self.question(); q['options'][1] = '25%'
        with self.assertRaises(ValueError): validate_question(q, self.nodes)

    def test_circuit_matches_topology_and_answer(self):
        q = self.question(); q.update(prompt='求总电流', options=['1 A', '2 A', '3 A', '6 A'], answerIndex=2)
        q['distractorReasons'] = ['错误', '错误', '', '错误']
        q['calculation'] = {'expression': '12/(2+3*6/(3+6))', 'value': 3, 'optionValues': [1, 2, 3, 6]}
        q['diagram'] = {'kind': 'circuit', 'topology': 'r1_series_r2_parallel_r3', 'voltage': 12, 'r1': 2, 'r2': 3, 'r3': 6, 'target': 'total_current'}
        checked = validate_question(q, self.nodes)
        self.assertTrue(checked['validation']['diagramChecked'])
        self.assertNotIn('target', checked['diagram'])
        q['diagram']['voltage'] = 24
        with self.assertRaises(ValueError): validate_question(q, self.nodes)

    def test_chart_does_not_publish_the_answer_check(self):
        q = self.question(); q['diagram'] = {'kind': 'line', 'title': '销量', 'unit': '件',
            'values': [{'label': '去年', 'value': 150}, {'label': '今年', 'value': 180}],
            'check': {'operation': 'growth_rate', 'fromIndex': 0, 'toIndex': 1}}
        self.assertNotIn('check', validate_question(q, self.nodes)['diagram'])


if __name__ == '__main__': unittest.main()
