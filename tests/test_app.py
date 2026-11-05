import unittest
from unittest.mock import patch

from app import app
from assistant_core import ServiceError, cleanup, transliterate
from evaluate import distance
from writing_backend import WritingError


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_home(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Your Hinglish', response.data)

    def test_invalid_requests(self):
        cases = [None, [], {'text': ''}, {'text': 12}, {'text': 'x' * 2001},
                 {'text': 'hello', 'action': 'delete'}, {'text': 'hello', 'tone': 'bad'},
                 {'text': 'hello', 'preserve_english': 'false'},
                 {'text': 'hello', 'action': []}, {'text': 'hello', 'tone': {}}]
        for data in cases:
            with self.subTest(data=str(data)[:60]):
                self.assertEqual(self.client.post('/api/write', json=data).status_code, 400)

    def test_model_failure_has_actionable_response(self):
        with patch('app.transliterate', side_effect=ServiceError('Model unavailable')):
            response = self.client.post('/api/write', json={'text': 'namaste'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json['error'], 'Model unavailable')

    def test_conversion_contract(self):
        with patch('assistant_core.word_candidates', return_value=('नमस्ते', 'नमस्थे')):
            response = self.client.post('/api/write', json={'text': 'namaste 😊'})
        self.assertEqual(response.json['text'], 'नमस्ते 😊')
        self.assertEqual(response.json['alternatives'][0]['source'], 'namaste')

    def test_llm_unconfigured_is_explicit(self):
        with patch('writing_backend.start_model_server', side_effect=WritingError('Param1 is not configured')):
            response = self.client.post('/api/write', json={'text': 'नमस्ते', 'action': 'rewrite'})
        self.assertEqual(response.status_code, 503)
        self.assertIn('not configured', response.json['error'])


class CoreTests(unittest.TestCase):
    @patch('assistant_core.word_candidates', return_value=('नमस्ते',))
    def test_preserves_layout_native_script_urls_and_emails(self, model):
        text = '😊 namaste\n  नमस्ते 42 https://example.com/hello?q=1 a.b@example.com!'
        result = transliterate(text)
        self.assertEqual(result['text'], '😊 नमस्ते\n  नमस्ते 42 https://example.com/hello?q=1 a.b@example.com!')
        self.assertEqual(result['alternatives'][0]['start'], 2)
        self.assertEqual(model.call_count, 1)

    @patch('assistant_core.word_candidates', return_value=('कॉलेज',))
    def test_english_option_changes_policy(self, model):
        self.assertEqual(transliterate('college PDF')['text'], 'college PDF')
        self.assertEqual(transliterate('college', False)['text'], 'कॉलेज')

    def test_cleanup_keeps_linebreaks(self):
        self.assertEqual(cleanup('  नमस्ते  !\n  hello  '), 'नमस्ते!\n hello')

    def test_edit_distance_counts_insert_delete_substitute(self):
        self.assertEqual(distance('kitten', 'sitting'), 3)
        self.assertEqual(distance('', 'ab'), 2)
        self.assertEqual(distance(['a', 'b'], ['b']), 1)


if __name__ == '__main__':
    unittest.main()
