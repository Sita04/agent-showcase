"""Tests for the Mock Order Management System MCP server functions."""

from mock_oms_mcp.server import check_budget, create_purchase_order


class TestCheckBudget:
    def test_amount_within_budget(self):
        result = check_budget(50.0, "office_supplies")
        assert result == {"approved": True, "remaining": 50.0}

    def test_amount_at_limit(self):
        result = check_budget(100.0, "collectibles")
        assert result == {"approved": True, "remaining": 0.0}

    def test_amount_exceeds_budget(self):
        result = check_budget(150.0, "marketing")
        assert result == {"approved": False, "reason": "Exceeds budget of $100.0"}

    def test_zero_amount(self):
        result = check_budget(0.0, "any")
        assert result == {"approved": True, "remaining": 100.0}

    def test_negative_amount(self):
        result = check_budget(-10.0, "any")
        assert result["approved"] is True


class TestCreatePurchaseOrder:
    def test_default_vendor(self):
        result = create_purchase_order("P1", 5)
        assert result["status"] == "success"
        assert result["po_id"] == "PO-P1-5"
        assert "mercari_seller" in result["message"]
        assert "5 units" in result["message"]

    def test_custom_vendor(self):
        result = create_purchase_order("P1", 5, "custom_vendor")
        assert result["status"] == "success"
        assert "custom_vendor" in result["message"]

    def test_po_id_format(self):
        result = create_purchase_order("ABC-123", 1)
        assert result["po_id"] == "PO-ABC-123-1"
