from typing import Literal


PolicyMode = Literal["allowed", "blocked", "manual_link"]

FitLabel = Literal[
    "Strong fit",
    "Possible fit",
    "Mismatch risk",
    "Filtered out",
]

RulesOutcome = Literal["pass", "soft_pass", "reject"]

JobDecision = Literal["saved", "hidden"]

FrictionEventType = Literal[
    "policy_blocked",
    "captcha_or_login",
    "rate_limited",
    "blocked_response",
    "layout_changed",
    "empty_suspicious",
    "manual_review_needed",
    "timeout",
]
