from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field
from enum import Enum


#1. WhyWarn: reasons for PlayerWarning

class WhyWarn(str, Enum):
    PHASE_CHANGED = "phase_changed"

# 2. PlayerWarning: reason into narrative
class PlayerWarning(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    reason: WhyWarn


# 3. Tests
def run_warn_kernel_tests() -> None:
    assert len(WhyWarn) == 1
    w = PlayerWarning(reason=WhyWarn.PHASE_CHANGED)
    assert w.reason is WhyWarn.PHASE_CHANGED
    # strict: plain string is refused
    try:
        PlayerWarning(reason="phase_changed")
    except ValueError:
        pass
    else:
        raise AssertionError("strict should refuse plain string")
    print("Warn kernel OK")


if __name__ == "__main__":
    run_warn_kernel_tests()
