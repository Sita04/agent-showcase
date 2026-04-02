"""Tests for DefaultConfig validation and defaults."""

import pytest
from agents.config.default_config import DefaultConfig


class TestDefaultConfig:
    def test_valid_construction(self):
        cfg = DefaultConfig(GOOGLE_CLOUD_PROJECT="my-project")
        assert cfg.GOOGLE_CLOUD_PROJECT == "my-project"
        assert cfg.BUDGET_LIMIT == 100.0
        assert cfg.DEFAULT_VENDOR_ID == "mercari_seller"
        assert cfg.AGENT_MODEL.startswith("vertex_ai/")
        assert cfg.EMBEDDER_MODEL == "text-embedding-005"

    def test_empty_project_raises(self):
        with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT"):
            DefaultConfig(GOOGLE_CLOUD_PROJECT="")

    def test_custom_overrides(self):
        cfg = DefaultConfig(
            GOOGLE_CLOUD_PROJECT="test",
            BUDGET_LIMIT=200.0,
            DEFAULT_VENDOR_ID="custom_vendor",
        )
        assert cfg.BUDGET_LIMIT == 200.0
        assert cfg.DEFAULT_VENDOR_ID == "custom_vendor"
