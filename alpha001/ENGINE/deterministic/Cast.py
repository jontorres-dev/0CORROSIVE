from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# Cast: receives notifications of approved Effects. Progress never writes here.
class Cast(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    notifications: tuple[str, ...] = ()


def notify_cast(cast: Cast, effect_id: str) -> Cast:
    """Return a new Cast with the notification added. Idempotent if already present."""
    if effect_id in cast.notifications:
        return cast
    return Cast(notifications=(*cast.notifications, effect_id))


def run_cast_kernel_tests() -> None:
    cast = Cast()
    assert cast.notifications == ()

    notified = notify_cast(cast, "e1")
    assert notified.notifications == ("e1",)

    # idempotent
    again = notify_cast(notified, "e1")
    assert again.notifications == notified.notifications
    assert again is notified or again.notifications == notified.notifications

    second = notify_cast(notified, "e2")
    assert second.notifications == ("e1", "e2")

    print("Cast kernel OK")


if __name__ == "__main__":
    run_cast_kernel_tests()
