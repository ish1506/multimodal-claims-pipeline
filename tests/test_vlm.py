from claim_review.vlm import completion_token_limit_param, supports_custom_temperature


def test_gpt5_family_uses_max_completion_tokens():
    assert completion_token_limit_param("gpt-5.4-mini") == "max_completion_tokens"
    assert completion_token_limit_param("gpt-5.4-nano") == "max_completion_tokens"
    assert completion_token_limit_param("gpt-5.5") == "max_completion_tokens"


def test_current_baseline_keeps_legacy_max_tokens():
    assert completion_token_limit_param("gpt-4.1-mini") == "max_tokens"


def test_gpt5_family_uses_default_temperature_only():
    assert not supports_custom_temperature("gpt-5.5")
    assert not supports_custom_temperature("gpt-5.4-mini")


def test_current_baseline_supports_custom_temperature():
    assert supports_custom_temperature("gpt-4.1-mini")
