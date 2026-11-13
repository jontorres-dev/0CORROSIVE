from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .deny import ActionDenied, WhyDeny

# Door 
class Door(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    
    id: str = Field(..., min_length=1)
    locked: bool = False
    key_id: str | None = None
    rooms: tuple[str, str]

# try_move  . Door |  ActionDenied 
def try_move(door: Door, inventory: tuple[str, ...]) -> Door:
    if not door.locked:
        return door
    if door.key_id is not None and door.key_id in inventory:
        return door.model_copy(update={"locked": False})
    raise ActionDenied(WhyDeny.LOCKED)

# teste
def run_door_kernel_tests() -> None:
    # 1. open door passes, nothing changes
    open_door = Door(id="hall", rooms=("hall", "garden"))
    assert try_move(open_door, ()) is open_door

    # 2. locked + key: new door unlocked, original stays locked
    locked = Door(id="cellar", rooms=("hall", "cellar"), locked=True, key_id="old key")
    opened = try_move(locked, ("candle", "old key"))
    assert opened.locked is False
    assert locked.locked is True

    # 3. locked, no key: denied with LOCKED
    try:
        try_move(locked, ("candle",))
        raise AssertionError("should be denied")
    except ActionDenied as e:
        assert e.reason is WhyDeny.LOCKED

    print("Door kernel tests: OK")


if __name__ == "__main__":
    run_door_kernel_tests()
