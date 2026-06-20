from claim_review.usage import UsageCollector, UsageSample


def test_usage_collector_summarizes_observed_api_usage():
    collector = UsageCollector()
    collector.record(
        UsageSample(
            row_index=0,
            prompt_config="rubric_v1",
            model="test-model",
            image_count=2,
            prompt_tokens=1000,
            completion_tokens=200,
            total_tokens=1200,
        )
    )
    collector.record(
        UsageSample(
            row_index=1,
            prompt_config="rubric_v1",
            model="test-model",
            image_count=1,
            prompt_tokens=800,
            completion_tokens=100,
            total_tokens=900,
        )
    )

    summary = collector.summary()

    assert summary is not None
    assert summary["calls"] == 2
    assert summary["images"] == 3
    assert summary["prompt_tokens_per_call"] == 900
    assert summary["completion_tokens_per_call"] == 150
    assert summary["total_tokens_per_call"] == 1050
    assert summary["prompt_tokens_per_image"] == 600
