import json

import phota.providers as providers
from phota.providers import get_provider, AnthropicProvider, OpenAIProvider, LocalOpenAIProvider
from tests.fixtures import make_jpeg

CANNED = {'caption': 'a cat on a sofa', 'tags': ['cat', 'sofa'], 'subjects': ['cat'], 'aesthetic_score': 0.8}


def test_get_provider_selects_by_name():
    assert isinstance(get_provider({'provider': 'anthropic', 'api_key': 'k'}), AnthropicProvider)
    assert isinstance(get_provider({'provider': 'openai', 'api_key': 'k'}), OpenAIProvider)
    assert isinstance(get_provider({'provider': 'local', 'base_url': 'http://x/v1', 'model': 'llava'}), LocalOpenAIProvider)
    assert get_provider(None) is None
    assert get_provider({}) is None


def test_anthropic_posts_and_parses(photo_dir, monkeypatch):
    cap = {}
    def fake_post(url, headers, payload):
        cap['url'] = url; cap['payload'] = payload; cap['headers'] = headers
        return {'content': [{'type': 'text', 'text': json.dumps(CANNED)}]}
    monkeypatch.setattr(providers, '_post_json', fake_post)
    p = make_jpeg(photo_dir / 'a.jpg')
    out = AnthropicProvider(api_key='k', model='claude-x').analyze_image(str(p))
    assert out['caption'] == 'a cat on a sofa' and out['tags'] == ['cat', 'sofa']
    assert 'anthropic.com' in cap['url'] and 'messages' in cap['payload']
    assert cap['headers'].get('x-api-key') == 'k'


def test_openai_posts_and_parses(photo_dir, monkeypatch):
    def fake_post(url, headers, payload):
        return {'choices': [{'message': {'content': json.dumps(CANNED)}}]}
    monkeypatch.setattr(providers, '_post_json', fake_post)
    p = make_jpeg(photo_dir / 'a.jpg')
    assert OpenAIProvider(api_key='k').analyze_image(str(p))['aesthetic_score'] == 0.8


def test_local_uses_base_url(photo_dir, monkeypatch):
    cap = {}
    def fake_post(url, headers, payload):
        cap['url'] = url
        return {'choices': [{'message': {'content': json.dumps(CANNED)}}]}
    monkeypatch.setattr(providers, '_post_json', fake_post)
    p = make_jpeg(photo_dir / 'a.jpg')
    out = LocalOpenAIProvider(base_url='http://localhost:1234/v1', model='llava').analyze_image(str(p))
    assert out['tags'] == ['cat', 'sofa'] and cap['url'].startswith('http://localhost:1234/v1')


def test_analyze_error_returns_none(photo_dir, monkeypatch):
    def boom(url, headers, payload):
        raise RuntimeError('network down')
    monkeypatch.setattr(providers, '_post_json', boom)
    p = make_jpeg(photo_dir / 'a.jpg')
    assert AnthropicProvider(api_key='k').analyze_image(str(p)) is None


def test_unreadable_image_returns_none():
    assert AnthropicProvider(api_key='k').analyze_image('/no/such.jpg') is None
