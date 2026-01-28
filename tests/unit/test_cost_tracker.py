from src.cost_tracker import CostTracker


class TestGetCostWarnings:
    def test_no_warnings_below_thresholds(self):
        tracker = CostTracker()
        assert tracker.get_cost_warnings(0.05, 0.5) == []

    def test_no_warnings_when_cost_is_none(self):
        tracker = CostTracker()
        assert tracker.get_cost_warnings(None, 5.0) == []

    def test_no_message_warning_when_cost_is_zero(self):
        tracker = CostTracker()
        warnings = tracker.get_cost_warnings(0, 5.0)
        assert all("Last message" not in w for w in warnings)

    def test_yellow_message_warning(self):
        tracker = CostTracker()
        warnings = tracker.get_cost_warnings(0.20, 0.5)
        assert len(warnings) == 1
        assert "🟡" in warnings[0]
        assert "$0.20" in warnings[0]

    def test_red_message_warning(self):
        tracker = CostTracker()
        warnings = tracker.get_cost_warnings(0.30, 0.5)
        assert len(warnings) == 1
        assert "🔴" in warnings[0]

    def test_total_cost_warning(self):
        tracker = CostTracker()
        warnings = tracker.get_cost_warnings(0.05, 1.5)
        assert len(warnings) == 1
        assert "Conversation cost" in warnings[0]
        assert "🟡" in warnings[0]

    def test_red_total_cost_warning(self):
        tracker = CostTracker()
        warnings = tracker.get_cost_warnings(0.05, 3.5)
        assert len(warnings) == 1
        assert "🔴" in warnings[0]

    def test_both_warnings(self):
        tracker = CostTracker()
        warnings = tracker.get_cost_warnings(0.20, 1.5)
        assert len(warnings) == 2


class TestLastWarnedCostRatcheting:
    def test_ratchets_up(self):
        tracker = CostTracker()
        tracker.get_cost_warnings(0.05, 1.5)
        assert tracker.last_warned_cost == 1

    def test_no_repeat_warning_within_threshold(self):
        tracker = CostTracker()
        tracker.get_cost_warnings(0.05, 1.5)
        warnings = tracker.get_cost_warnings(0.05, 1.8)
        assert warnings == []

    def test_warns_again_after_threshold(self):
        tracker = CostTracker()
        tracker.get_cost_warnings(0.05, 1.5)
        warnings = tracker.get_cost_warnings(0.05, 2.5)
        assert len(warnings) == 1

    def test_reset(self):
        tracker = CostTracker()
        tracker.get_cost_warnings(0.05, 1.5)
        tracker.reset()
        assert tracker.last_warned_cost == 0
