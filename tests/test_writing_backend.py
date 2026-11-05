import unittest
from unittest.mock import Mock, patch

import requests
import writing_backend as backend


class WritingTests(unittest.TestCase):
    def setUp(self):
        backend._cache.clear()
        self.server = patch('writing_backend.start_model_server')
        self.server.start()
        self.addCleanup(self.server.stop)
        self.tokenizer = Mock()
        self.tokenizer.encode.return_value.ids = [256000, 100, 256001]
        self.tokenizer_patch = patch('writing_backend._tokenizer', self.tokenizer)
        self.tokenizer_patch.start()
        self.addCleanup(self.tokenizer_patch.stop)

    def response(self, text='कृपया कल 10 बजे आइए।', finish='stop'):
        result = Mock()
        result.json.return_value = {'tokens': [100, 256001], 'stop_type': 'limit' if finish == 'length' else 'eos'}
        self.tokenizer.decode.return_value = text
        return result

    @patch('writing_backend.requests.post')
    def test_local_request_and_cache(self, post):
        post.return_value = self.response()
        first = backend.generate_writing('कल 10 बजे आना।', 'rewrite', 'formal')
        second = backend.generate_writing('कल 10 बजे आना।', 'rewrite', 'formal')
        self.assertEqual(post.call_count, 1)
        self.assertFalse(first['cached'])
        self.assertTrue(second['cached'])
        self.assertEqual(first['warnings'], [])
        self.assertEqual(post.call_args.args[0], 'http://127.0.0.1:8090/completion')
        self.assertEqual(post.call_args.kwargs['json']['prompt'], [256000, 100, 256001])
        self.assertIn('formal', self.tokenizer.encode.call_args.args[0])

    @patch('writing_backend.requests.post')
    def test_external_provider_settings_cannot_change_model(self, post):
        post.return_value = self.response()
        with patch.dict('os.environ', {'OPENROUTER_MODEL': 'foreign/model', 'OPENROUTER_API_KEY': 'unused-secret'}):
            backend.generate_writing('नमस्ते', 'rewrite', 'natural')
        self.assertEqual(post.call_args.args[0], backend.BASE_URL + '/completion')
        self.assertNotIn('headers', post.call_args.kwargs)

    @patch('writing_backend.requests.post')
    def test_missing_local_model_has_no_fallback(self, post):
        with patch('writing_backend.start_model_server', side_effect=backend.WritingError('Param1 not installed')):
            with self.assertRaisesRegex(backend.WritingError, 'not installed'):
                backend.generate_writing('नमस्ते', 'rewrite', 'formal')
        post.assert_not_called()

    @patch('writing_backend.requests.post')
    def test_changed_numbers_and_links_trigger_review(self, post):
        post.return_value = self.response('कल 12 बजे आइए।')
        result = backend.generate_writing('कल 10 बजे आना। https://example.com', 'rewrite', 'formal')
        self.assertEqual(len(result['warnings']), 2)

    @patch('writing_backend.requests.post')
    def test_truncated_output_not_presented_as_complete(self, post):
        post.return_value = self.response(finish='length')
        with self.assertRaisesRegex(backend.WritingError, 'before finishing'):
            backend.generate_writing('नमस्ते', 'rewrite', 'formal')

    @patch('writing_backend.requests.post')
    def test_raw_exception_is_not_exposed(self, post):
        post.side_effect = requests.ConnectionError('private implementation detail')
        with self.assertRaises(backend.WritingError) as failure:
            backend.generate_writing('नमस्ते', 'rewrite', 'formal')
        self.assertNotIn('private implementation detail', str(failure.exception))

    def test_configuration_is_sovereign_and_local(self):
        config = backend.configuration()
        self.assertEqual(config['provider'], 'bharatgen')
        self.assertFalse(config['remote'])
        self.assertIn('Param-1', config['model'])


if __name__ == '__main__':
    unittest.main()
