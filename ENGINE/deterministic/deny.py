from enum import Enum


class WhyDeny(str, Enum):
    TARGET_NOT_FOUND = "target_not_found"
    NO_CONSENT = "no_consent"


class ActionDenied(ValueError):
    def __init__(self, reason: WhyDeny) -> None:
        self.reason = reason
        super().__init__(reason.value)


def run_errors_kernel_tests() -> None:
    # 1. reason travels inside the error
    try:
        raise ActionDenied(WhyDeny.NO_CONSENT)
    except ActionDenied as e:
        assert e.reason is WhyDeny.NO_CONSENT

    # 2. it is still a ValueError
    assert issubclass(ActionDenied, ValueError)

    # 3. exact size
    assert len(WhyDeny) == 2

    print(" -Deny- errors kernel: =OK=")


if __name__ == "__main__":
    run_errors_kernel_tests()
