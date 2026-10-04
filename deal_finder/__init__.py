"""ai-deal-finder V1 public package."""

from . import consent, decision, discovery, evidence, judgment, landed_cost, runtime, similar_contract
from .runtime import authorize_cart_test, build_jev_request, evaluate

__all__ = [
    "authorize_cart_test",
    "build_jev_request",
    "consent",
    "decision",
    "discovery",
    "evaluate",
    "evidence",
    "judgment",
    "landed_cost",
    "runtime",
    "similar_contract",
]

__version__ = "1.0.0"
