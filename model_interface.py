"""Credential-safe OpenAI-compatible HTTP adapters for the retained model groups."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class ConfigurationError(ValueError):
    pass


class ModelServiceError(RuntimeError):
    pass


# Expected identities are validated separately from experimental aliases.
MODEL_DEFAULTS = {
    'gpt-4o': ('WSD_GPT4O', 'OPENAI_API_KEY', 'https://api.openai.com/v1', 'gpt-4o', 'max_completion_tokens'),
    'llama-3.1-70b': ('WSD_LLAMA', 'TOGETHER_API_KEY', 'https://api.together.xyz/v1',
                      'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo', 'max_tokens'),
    'deepseek-v3': ('WSD_DEEPSEEK', 'SILICONFLOW_API_KEY', 'https://api.siliconflow.cn/v1',
                    'deepseek-ai/DeepSeek-V3', 'max_tokens'),
}


def load_env_file(path='.env'):
    """Read simple KEY=VALUE lines without executing shell commands or overwriting env."""
    path = Path(path)
    if not path.is_file():
        return
    for number, raw in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            raise ConfigurationError(f'Invalid environment file entry at line {number}')
        key, value = line.split('=', 1)
        key, value = key.strip(), value.strip()
        if not re.fullmatch(r'[A-Z_][A-Z0-9_]*', key):
            raise ConfigurationError(f'Invalid environment variable name at line {number}')
        if value[:1] in {'"', "'"}:
            if len(value) < 2 or value[-1] != value[0]:
                raise ConfigurationError(f'Unbalanced quotes at environment line {number}')
            value = value[1:-1]
        os.environ.setdefault(key, value)


def validate_identity(alias, model_id):
    if not isinstance(model_id, str):
        raise ConfigurationError(f'{alias}: invalid model identifier')
    leaf = model_id.rsplit('/', 1)[-1]
    patterns = {
        'gpt-4o': r'gpt-4o(?:-\d{4}-\d{2}-\d{2})?',
        'llama-3.1-70b': r'(?:meta-)?llama-3\.1-70b(?:-instruct)?(?:-turbo)?',
        'deepseek-v3': r'deepseek-v3(?:-(?:0324|1226|\d{8}))?',
    }
    if alias not in patterns or not re.fullmatch(patterns[alias], leaf, re.I):
        raise ConfigurationError(f'{alias}: request/response model identity does not match the experimental group')


@dataclass(frozen=True)
class ModelConfig:
    alias: str
    model_id: str
    base_url: str
    key_variable: str
    token_parameter: str
    temperature: float
    timeout: float
    retries: int


def configuration(alias, require_key=True):
    if alias not in MODEL_DEFAULTS:
        raise ConfigurationError('Unsupported experimental model group')
    prefix, key_name, url, model_id, token_parameter = MODEL_DEFAULTS[alias]
    model_id = os.environ.get(prefix + '_MODEL_ID', model_id).strip()
    url = os.environ.get(prefix + '_BASE_URL', url).strip().rstrip('/')
    validate_identity(alias, model_id)
    parsed = urlsplit(url)
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
            or not (parsed.scheme == 'https' or
                    parsed.scheme == 'http' and parsed.hostname in {'localhost', '127.0.0.1', '::1'})):
        raise ConfigurationError(f'{alias}: endpoint requires HTTPS (HTTP allowed only on loopback), without URL credentials/query')
    try:
        temperature = float(os.environ.get('WSD_TEMPERATURE', '0'))
        timeout = float(os.environ.get('WSD_TIMEOUT', '120'))
        retries = int(os.environ.get('WSD_RETRIES', '0'))
        if not math.isfinite(temperature) or not 0 <= temperature <= 2:
            raise ValueError
        if not math.isfinite(timeout) or timeout <= 0 or not 0 <= retries <= 5:
            raise ValueError
    except ValueError:
        raise ConfigurationError('Invalid temperature, timeout, or retry configuration') from None
    if require_key and not os.environ.get(key_name, '').strip():
        raise ConfigurationError(f'{alias}: set {key_name} in environment or local .env')
    return ModelConfig(alias, model_id, url, key_name, token_parameter, temperature, timeout, retries)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class UnifiedModelInterface:
    """No SDK import, model download, network call or credential lookup at import time."""
    def __init__(self, model_name='gpt-4o'):
        self.config = configuration(model_name)
        self._key = os.environ[self.config.key_variable].strip()
        self.last_call_metadata = {}

    def describe(self):
        return asdict(self.config)

    def generate_response(self, prompt, max_tokens=1024):
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens < 1:
            raise ValueError('max_tokens must be a positive integer')
        body = {'model': self.config.model_id,
                'messages': [{'role': 'system', 'content': 'You are a multilingual Word Sense Disambiguation expert.'},
                             {'role': 'user', 'content': prompt}],
                'temperature': self.config.temperature, 'stream': False,
                self.config.token_parameter: max_tokens}
        encoded = json.dumps(body, ensure_ascii=False).encode('utf-8')
        request = Request(self.config.base_url + '/chat/completions', data=encoded,
                          headers={'Authorization': 'Bearer ' + self._key,
                                   'Content-Type': 'application/json'}, method='POST')
        for attempt in range(self.config.retries + 1):
            try:
                with build_opener(_NoRedirect()).open(request, timeout=self.config.timeout) as response:
                    payload = json.loads(response.read())
                    header_request_id = response.headers.get('x-request-id')
            except HTTPError as exc:
                status = exc.code
                exc.close()
                if (status == 429 or status == 408 or status >= 500) and attempt < self.config.retries:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                # Never echo provider bodies, URLs, prompts, exception text or credentials.
                raise ModelServiceError(f'{self.config.alias}: HTTP {status}; run aborted') from None
            except (URLError, OSError, TimeoutError):
                if attempt < self.config.retries:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                raise ModelServiceError(f'{self.config.alias}: connection failed; run aborted') from None
            except (ValueError, UnicodeError):
                raise ModelServiceError(f'{self.config.alias}: invalid response JSON') from None
            if not isinstance(payload, dict):
                raise ModelServiceError(f'{self.config.alias}: invalid response structure')
            returned_model = payload.get('model')
            if returned_model:
                try:
                    validate_identity(self.config.alias, returned_model)
                except ConfigurationError:
                    raise ModelServiceError(f'{self.config.alias}: provider returned an incompatible model identity') from None
            try:
                choice = payload['choices'][0]
                content = choice['message']['content']
                if content is None:
                    content = ''
                if not isinstance(content, str):
                    raise TypeError
            except (KeyError, IndexError, TypeError):
                raise ModelServiceError(f'{self.config.alias}: invalid response structure') from None
            self.last_call_metadata = {
                'requested_model_id': self.config.model_id, 'returned_model_id': returned_model,
                'response_id': payload.get('id'), 'request_id': header_request_id,
                'system_fingerprint': payload.get('system_fingerprint'),
                'usage': payload.get('usage'), 'finish_reason': choice.get('finish_reason'),
                'attempts': attempt + 1, 'temperature': self.config.temperature,
                'token_parameter': self.config.token_parameter, 'token_limit': max_tokens,
                'response_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
                'received_at_utc': datetime.now(timezone.utc).isoformat(),
            }
            return content.strip()
        raise ModelServiceError('Unreachable retry state')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', nargs='+', choices=list(MODEL_DEFAULTS), default=list(MODEL_DEFAULTS))
    args = parser.parse_args()
    load_env_file()
    errors = []
    for alias in args.models:
        try:
            config = configuration(alias)
            print(json.dumps(asdict(config), ensure_ascii=False))
        except ConfigurationError as exc:
            errors.append(str(exc))
    for error in errors:
        print(error)
    return 2 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
