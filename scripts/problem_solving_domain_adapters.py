#!/usr/bin/env python3
"""Resolve optional domain evidence adapters without changing the general Controller contract."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

import problem_solving_stock_decision_adapter as STOCK


class DomainAdapter(Protocol):
    ADAPTER_ID: str

    def matches(self, request: str) -> bool: ...

    def augment_contract(self, contract: Mapping[str, Any]) -> dict[str, Any]: ...

    def additional_obligations(self, contract: Mapping[str, Any]) -> list[dict[str, Any]]: ...

    def verify(
        self,
        contract: Mapping[str, Any],
        answer: str,
        result: Mapping[str, Any],
    ) -> dict[str, Any]: ...


_ADAPTERS = {STOCK.ADAPTER_ID: STOCK}


def detect_adapter_id(request: str) -> str | None:
    for adapter_id, adapter in _ADAPTERS.items():
        if adapter.matches(request):
            return adapter_id
    return None


def get_adapter(adapter_id: str | None) -> Any | None:
    if not adapter_id:
        return None
    return _ADAPTERS.get(str(adapter_id))


def augment_contract(contract: Mapping[str, Any], adapter_id: str | None) -> dict[str, Any]:
    adapter = get_adapter(adapter_id)
    return adapter.augment_contract(contract) if adapter else dict(contract)


def additional_obligations(
    contract: Mapping[str, Any],
    adapter_id: str | None,
) -> list[dict[str, Any]]:
    adapter = get_adapter(adapter_id)
    return adapter.additional_obligations(contract) if adapter else []
