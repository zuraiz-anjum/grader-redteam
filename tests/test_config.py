import pytest

from grader_redteam.config import load


def test_minimal_config(tmp_path):
    cfg_file = tmp_path / "g.toml"
    cfg_file.write_text(
        '[grader]\ncommand = "python g.py {workspace}"\n'
        '[workspace]\ndeliverable = "out.txt"\nreward = "reward.json"\n'
    )
    cfg = load(cfg_file)
    assert cfg.command == ["python", "g.py", "{workspace}"]
    assert cfg.template is None and cfg.secrets == []


def test_missing_command_rejected(tmp_path):
    cfg_file = tmp_path / "g.toml"
    cfg_file.write_text('[workspace]\ndeliverable = "a"\nreward = "b"\n')
    with pytest.raises(ValueError):
        load(cfg_file)


def test_planted_reward_defaults_to_reward(tmp_path):
    cfg_file = tmp_path / "g.toml"
    cfg_file.write_text(
        '[grader]\ncommand = "python g.py"\n'
        '[workspace]\ndeliverable = "a"\nreward = "{private}/r.json"\n'
    )
    assert load(cfg_file).planted_reward == "{private}/r.json"
