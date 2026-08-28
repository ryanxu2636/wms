"""订单状态机单元测试。"""
import pytest

from app.core.state_machine import can_transition, assert_can_transition
from app.core.exceptions import IllegalTransitionError


class TestStateMachine:
    def test_main_flow(self):
        """主流程：待分配→已分配→拣货→复核→打包→出库。"""
        flow = [
            ("unassigned", "assigned"),
            ("assigned", "picking"),
            ("picking", "checked"),
            ("checked", "packed"),
            ("packed", "outbound"),
        ]
        for current, target in flow:
            assert can_transition(current, target), f"{current}→{target} 应允许"

    def test_outbound_is_terminal(self):
        """出库是终态，不可再迁移。"""
        for target in ["assigned", "picking", "checked", "packed", "unassigned"]:
            assert not can_transition("outbound", target), f"outbound→{target} 应禁止"

    def test_exception_states(self):
        """异常态可从待分配/已分配进入。"""
        assert can_transition("unassigned", "intercepted")
        assert can_transition("unassigned", "manual_review")
        assert can_transition("unassigned", "shortage_hold")
        assert can_transition("assigned", "intercepted")
        assert can_transition("assigned", "manual_review")

    def test_shortage_recover(self):
        """缺货挂起补货后可回待分配重新分配。"""
        assert can_transition("shortage_hold", "unassigned")

    def test_illegal_transition_raises(self):
        """非法迁移抛异常。"""
        with pytest.raises(IllegalTransitionError):
            assert_can_transition("outbound", "assigned")

    def test_unknown_status(self):
        """未知状态视为不可迁移。"""
        assert not can_transition("nonexistent", "assigned")
        assert not can_transition("assigned", "nonexistent")
