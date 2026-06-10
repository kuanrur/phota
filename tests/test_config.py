import os, stat
from phota import config


def test_save_and_read_ai_config():
    config.save_ai_config('anthropic', api_key='sk-test', model='claude-x')
    cfg = config.ai_config()
    assert cfg['provider'] == 'anthropic'
    assert cfg['api_key'] == 'sk-test'
    assert cfg['model'] == 'claude-x'


def test_config_file_mode_600():
    config.save_ai_config('openai', api_key='sk')
    mode = stat.S_IMODE(os.stat(config.config_path()).st_mode)
    assert mode == 0o600


def test_public_status_omits_key():
    config.save_ai_config('anthropic', api_key='secret')
    s = config.public_ai_status()
    assert s['configured'] is True
    assert s['provider'] == 'anthropic'
    assert 'api_key' not in s and 'secret' not in str(s)


def test_missing_config_is_none():
    assert config.ai_config() is None
    assert config.public_ai_status()['configured'] is False
