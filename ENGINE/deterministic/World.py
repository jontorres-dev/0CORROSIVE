from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Final
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .door import Door, try_move, other_side
from .deny import ActionDenied, WhyDeny



# # Time Clock # # 

DEFAULT_TICK_UNIT: Final[str] = "minute"
EPOCH: Final[datetime] = datetime(2000, 1, 1)  # day 1, 00:00


# Clock:  @Tick  (TickStatus)   @TickApplication       @GameClock  &&& 
                                                ### Day Phase
class Clock(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    day: int = Field(default=1, ge=1)
    hour: int = Field(default=0, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    second: int = Field(default=0, ge=0, le=59)

    def tick(self, seconds: int = 1) -> Clock:
        now = EPOCH + timedelta(
            days=self.day - 1,
            hours=self.hour,
            minutes=self.minute,
            seconds=self.second,
        )
        now += timedelta(seconds=seconds)
        return Clock(
            day=(now.date() - EPOCH.date()).days + 1,
            hour=now.hour,
            minute=now.minute,
            second=now.second,
        )


# GameClock: day, hour, minute. CHECK is_valid_clock_state 
class GameClock(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    day: int = Field(..., ge=1)
    hour: int = Field(..., ge=0, le=23)
    minute: int = Field(..., ge=0, le=59)
    tick_unit: str = Field(default=DEFAULT_TICK_UNIT, min_length=1)


def is_valid_clock_state(day: object, hour: object, minute: object) -> bool:
    if type(day) is not int or type(hour) is not int or type(minute) is not int:
        return False
    return (
        day >= 1
        and 0 <= hour <= 23
        and 0 <= minute <= 59
    )


# Tick: time advance steps. 
class Tick(BaseModel):    
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    amount: int = Field(..., ge=1)
    reason: str
    source_action_id: str = Field(..., min_length=1)
    door_id: str | None = None


# TickStatus: read
class TickStatus(str, Enum):
    APPLIED = "applied"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"


# World: counts Tick, clock is GameClock. &&&  # .apply_tick
class World(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    clock: GameClock
    applied_ticks: tuple[Tick, ...] = ()
    rooms: tuple[str, ...]
    doors: tuple[Door, ...]
    player_room: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _coherent(self) -> World:
        if len(set(self.rooms)) != len(self.rooms):
            raise ValueError("duplicate room")
        if self.player_room not in self.rooms:
            raise ValueError("player_room not in rooms")
        door_ids = [d.id for d in self.doors]
        if len(set(door_ids)) != len(door_ids):
            raise ValueError("duplicate door id")
        for door in self.doors:
            if door.rooms[0] not in self.rooms or door.rooms[1] not in self.rooms:
                raise ValueError(f"door {door.id} leads to unknown room")
        return self    

    def read_clock(self) -> GameClock:
        return self.clock

    def apply_tick(self, tick: Tick) -> TickApplication:
        for applied in self.applied_ticks:
            if applied.source_action_id != tick.source_action_id:
                continue
            if applied.amount == tick.amount and applied.reason == tick.reason and applied.door_id == tick.door_id:
                return TickApplication(status=TickStatus.DUPLICATE, world=self)
            return TickApplication(status=TickStatus.CONFLICT, world=self)
        room = self.player_room
        if tick.door_id is not None:
            door = next((d for d in self.doors if d.id == tick.door_id and room in d.rooms), None)
            if door is None:
                raise ActionDenied(WhyDeny.TARGET_NOT_FOUND)
            try_move(door, ())  # no inventory yet: locked always denies
            room = other_side(door, room)
        advanced = World(
            clock=advance_clock(self.clock, tick.amount),
            applied_ticks=(*self.applied_ticks, tick),
            rooms=self.rooms,
            doors=self.doors,
            player_room=room
        )
        return TickApplication(status=TickStatus.APPLIED, world=advanced)


# status + World  &&  boot world 
class TickApplication(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    status: TickStatus
    world: World


def compose_world(
    clock: GameClock,
    rooms: tuple[str, ...],
    doors: tuple[Door, ...],
    player_room: str,
) -> World:
    return World(clock=clock, rooms=rooms, doors=doors, player_room=player_room)


# boot game clock
# clock  state
def make_game_clock(
    day: int,
    hour: int,
    minute: int,
    tick_unit: str = DEFAULT_TICK_UNIT,
) -> GameClock:
    return GameClock(day=day, hour=hour, minute=minute, tick_unit=tick_unit)


class DayPhase(str, Enum):
    MORNING = "morning"      # 06:00-11:59
    AFTERNOON = "afternoon"  # 12:00-17:59
    EVENING = "evening"      # 18:00-23:59
    NIGHT = "night"          # 00:00-05:59


def read_clock_state(clock: GameClock) -> tuple[int, int, int]:
    return (clock.day, clock.hour, clock.minute)


def advance_clock(clock: GameClock, minutes: int) -> GameClock:
    now = EPOCH + timedelta(
        days=clock.day - 1, hours=clock.hour, minutes=clock.minute
    )
    now += timedelta(minutes=minutes)
    return GameClock(
        day=(now.date() - EPOCH.date()).days + 1,
        hour=now.hour,
        minute=now.minute,
        tick_unit=clock.tick_unit,
    )

# teste
def run_tick_kernel_tests() -> None:
    world = compose_world(make_game_clock(3, 14, 0), rooms=("start",), doors=(), player_room="start")
    first = Tick(amount=15, reason="touch", source_action_id="a1")

    applied = world.apply_tick(first)
    assert applied.status is TickStatus.APPLIED
    assert read_clock_state(world.clock) == (3, 14, 0)
    assert world.applied_ticks == ()
    assert read_clock_state(applied.world.clock) == (3, 14, 15)
    assert applied.world.applied_ticks == (first,)

    repeated = applied.world.apply_tick(
        Tick(amount=15, reason="touch", source_action_id="a1")
    )
    assert repeated.status is TickStatus.DUPLICATE
    assert repeated.world is applied.world
    assert read_clock_state(repeated.world.clock) == (3, 14, 15)
    assert repeated.world.applied_ticks == (first,)

    for reused in (
        Tick(amount=20, reason="touch", source_action_id="a1"),
        Tick(amount=15, reason="talk", source_action_id="a1"),
    ):
        conflict = applied.world.apply_tick(reused)
        assert conflict.status is TickStatus.CONFLICT
        assert conflict.world is applied.world
        assert read_clock_state(conflict.world.clock) == (3, 14, 15)
        assert conflict.world.applied_ticks == (first,)

    second = Tick(amount=20, reason="item", source_action_id="a2")
    both = applied.world.apply_tick(second)
    assert both.status is TickStatus.APPLIED
    assert read_clock_state(both.world.clock) == (3, 14, 35)
    assert both.world.applied_ticks == (first, second)

    late = compose_world(make_game_clock(3, 23, 50), rooms=("start",), doors=(), player_room="start")
    rolled = late.apply_tick(Tick(amount=20, reason="item", source_action_id="a3"))
    assert rolled.status is TickStatus.APPLIED
    assert read_clock_state(rolled.world.clock) == (4, 0, 10)

    for payload in (
        {"amount": 0, "reason": "talk", "source_action_id": "x"},
        {"amount": -10, "reason": "talk", "source_action_id": "x"},
        {"amount": True, "reason": "talk", "source_action_id": "x"},
        {"amount": "10", "reason": "talk", "source_action_id": "x"},
        {"amount": 10, "reason": "talk", "source_action_id": ""},
        {"amount": 10, "reason": "talk"},
        {"amount": 10, "reason": "talk", "source_action_id": "x", "extra": 1},
    ):
        try:
            Tick(**payload)  # type: ignore[arg-type]
        except ValidationError:
            continue
        raise AssertionError(f"expected invalid Tick: {payload}")
def run_clock_kernel_tests() -> None:
    start = Clock()
    assert (start.day, start.hour, start.minute, start.second) == (1, 0, 0, 0)

    one = start.tick()
    assert (one.day, one.hour, one.minute, one.second) == (1, 0, 0, 1)
    assert start.second == 0  # frozen: tick returns a new Clock

    five_min = Clock(day=1, hour=11, minute=58).tick(5 * 60)
    assert (five_min.day, five_min.hour, five_min.minute) == (1, 12, 3)

    midnight = Clock(day=1, hour=23, minute=59, second=59).tick()
    assert (midnight.day, midnight.hour, midnight.minute, midnight.second) == (2, 0, 0, 0)


def run_clock_state_kernel_tests() -> None:
    assert is_valid_clock_state(1, 12, 30) is True
    for day, hour, minute in ((1, 25, 0), (1, 12, 60), (0, 12, 0), (1, -1, 0)):
        assert is_valid_clock_state(day, hour, minute) is False
        try:
            make_game_clock(day, hour, minute)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError: {(day, hour, minute)}")

def run_world_kernel_tests() -> None:
    clock = make_game_clock(1, 9, 0)
    good = (Door(id="d1", rooms=("hall", "garden")),)
    compose_world(clock, ("hall", "garden"), good, "hall")
    for rooms, doors, player in (
        (("hall", "hall"), (), "hall"),
        (("hall",), (), "cellar"),
        (("hall", "garden"), good + good, "hall"),
        (("hall",), good, "hall"),
    ):
        try:
            compose_world(clock, rooms, doors, player)
            raise AssertionError(f"accepted {rooms} {player}")
        except ValueError:
            pass


if __name__ == "__main__":
    run_clock_kernel_tests()
    print("Clock kernel tests: OK")
    run_tick_kernel_tests()
    print("Tick application kernel tests: OK")
    run_clock_state_kernel_tests()
    print("Clock state kernel tests: OK")
    run_world_kernel_tests()
    print("World kernel tests: OK")

