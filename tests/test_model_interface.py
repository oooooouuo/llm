"""HTTP protocol unit fixtures only; no external service or experimental outputs."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from model_interface import (UnifiedModelInterface, ConfigurationError, ModelServiceError,
                             configuration, load_env_file, validate_identity)


class Response(io.BytesIO):
    def __init__(self, payload):
        super().__init__(json.dumps(payload).encode())
        self.headers = {'x-request-id': 'unit-request'}


class ModelInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'OPENAI_API_KEY': 'unit-test-key-not-a-real-credential'}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_credential_required_only_on_instantiation(self):
        del os.environ['OPENAI_API_KEY']
        configuration('gpt-4o', require_key=False)
        with self.assertRaises(ConfigurationError):
            UnifiedModelInterface()

    def test_model_family_and_version_validation(self):
        for alias, identifier in [('llama-3.1-70b', 'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo'),
                                  ('deepseek-v3', 'deepseek-ai/DeepSeek-V3-0324'),
                                  ('gpt-4o', 'gpt-4o-2024-08-06')]:
            validate_identity(alias, identifier)
        for alias, identifier in [('llama-3.1-70b', 'unrelated-model'),
                                  ('llama-3.1-70b', 'Llama-3.3-70B-Instruct'),
                                  ('deepseek-v3', 'deepseek-chat'),
                                  ('deepseek-v3', 'DeepSeek-V3.2')]:
            with self.assertRaises(ConfigurationError):
                validate_identity(alias, identifier)

    def test_token_budget_metadata_and_no_secret_in_metadata(self):
        payload = {'model': 'gpt-4o-2024-08-06', 'id': 'unit-response',
                   'choices': [{'message': {'content': '{}'}, 'finish_reason': 'stop'}]}
        with patch('model_interface.build_opener') as opener:
            opener.return_value.open.return_value = Response(payload)
            model = UnifiedModelInterface()
            self.assertEqual(model.generate_response('unit prompt', max_tokens=87), '{}')
            request = opener.return_value.open.call_args.args[0]
            body = json.loads(request.data)
            self.assertEqual(body['max_completion_tokens'], 87)
            self.assertEqual(model.last_call_metadata['returned_model_id'], payload['model'])
            self.assertNotIn(os.environ['OPENAI_API_KEY'], json.dumps(model.last_call_metadata))
            self.assertNotIn(os.environ['OPENAI_API_KEY'], json.dumps(model.describe()))

    def test_wrong_returned_identity_stops_the_run(self):
        with patch('model_interface.build_opener') as opener:
            opener.return_value.open.return_value = Response({'model': 'unrelated-model'})
            with self.assertRaises(ModelServiceError):
                UnifiedModelInterface().generate_response('unit prompt')

    def test_errors_do_not_echo_provider_payload(self):
        error = HTTPError('https://example.invalid', 401, 'contains-private-information', {},
                          io.BytesIO(b'unit-private-body'))
        with patch('model_interface.build_opener') as opener:
            opener.return_value.open.side_effect = error
            with self.assertRaises(ModelServiceError) as caught:
                UnifiedModelInterface().generate_response('unit prompt')
            self.assertNotIn('private', str(caught.exception))
            self.assertIn('401', str(caught.exception))

    def test_local_environment_file_is_not_shell_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('WSD_TEMPERATURE=0.2\nOPENAI_API_KEY=replacement\nUNIT_VALUE="$(not-executed)"\n')
            load_env_file(path)
            self.assertEqual(os.environ['UNIT_VALUE'], '$(not-executed)')
            self.assertNotEqual(os.environ['OPENAI_API_KEY'], 'replacement')

    def test_reject_credentials_in_url_and_insecure_remote_http(self):
        for endpoint in ['http://example.invalid/v1', 'https://user:password@example.invalid/v1']:
            with patch.dict(os.environ, {'WSD_GPT4O_BASE_URL': endpoint}):
                with self.assertRaises(ConfigurationError):
                    configuration('gpt-4o')


if __name__ == '__main__':
    unittest.main()
