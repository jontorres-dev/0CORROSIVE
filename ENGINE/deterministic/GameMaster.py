from __future__ import annotations
from typing import Final
from enum import Enum


from .verbs import Verb
from .World import DayPhase, GameClock, Tick, TickStatus,compose_world, make_game_clock

from .warn import PlayerWarning, WhyWarn

# 1. Verb Cost | Block Starts | GameMode
VERB_COST: Final[dict[Verb, int]] = {
    Verb.TALK: 25,
    Verb.MOVE: 25,
    Verb.STOP: 25,
    Verb.TOUCH: 60,
    Verb.ITEM: 45,
    Verb.SEARCH: 45,
}
  ##  1.1.          
BLOCK_STARTS: Final[tuple[int, ...]] = (0, 6, 12, 18)
    # GameMode: current game mode. Owner :::: GameMaster.py
class GameMode(str, Enum):
    EXPLORE = "explore"                   
    
# 2. emit_tick | verb + action_id | send Tick ->  World.py
def emit_tick(verb: Verb, action_id: str) -> Tick:
    return Tick(amount=VERB_COST[verb], reason=verb.value, source_action_id=action_id)

# 3. read_phase: clock read  -> phase of day
def read_phase(clock: GameClock) -> DayPhase:
    if 6 <= clock.hour < 12:
        return DayPhase.MORNING
    if 12 <= clock.hour < 18:
        return DayPhase.AFTERNOON
    if 18 <= clock.hour < 24:
        return DayPhase.EVENING
    return DayPhase.NIGHT

## 3.1 read_mode: returns current GameMode. Single Owner :::: GameMaster.py 
def read_mode() -> GameMode:
    return GameMode.EXPLORE


## 4.  minutes  next block
def minutes_to_next_block(clock: GameClock) -> int:
    now = clock.hour * 60 + clock.minute
    for start in BLOCK_STARTS:
        if start * 60 > now:
            return start * 60 - now
    return 24 * 60 - now  # next is 00:00 tomorrow

## 5. emit ellipse
def emit_ellipse(clock: GameClock, action_id: str) -> Tick:
    return Tick(amount=minutes_to_next_block(clock), reason="ellipse", source_action_id=action_id)

## 5.1 check_phase: clock before + after -> warnings (never raises)
def check_phase(before: GameClock, after: GameClock) -> tuple[PlayerWarning, ...]:
    if read_phase(before) != read_phase(after):
        return (PlayerWarning(reason=WhyWarn.PHASE_CHANGED),)
    return ()




# 6. Tests
def run_game_master_kernel_tests() -> None:
    # every verb has a cost
    for verb in Verb:
        assert verb in VERB_COST, f"missing cost: {verb}"
    # tick carries cost and id
    tick = emit_tick(Verb.TOUCH, "a1")
    assert tick.amount == 60 and tick.source_action_id == "a1"

    # phase borders
    for hour, phase in ((5, DayPhase.NIGHT), (6, DayPhase.MORNING),
                        (11, DayPhase.MORNING), (12, DayPhase.AFTERNOON),
                        (17, DayPhase.AFTERNOON), (18, DayPhase.EVENING),
                        (23, DayPhase.EVENING), (0, DayPhase.NIGHT)):
        assert read_phase(make_game_clock(1, hour, 0)) == phase, f"phase at {hour}h"

    # end to end: GameMaster -> World
    world = compose_world(make_game_clock(1, 11, 30), rooms=("start",), doors=(), player_room="start")
    first = world.apply_tick(emit_tick(Verb.TOUCH, "a2"))
    assert first.status == TickStatus.APPLIED
    assert (first.world.clock.hour, first.world.clock.minute) == (12, 30)
    assert read_phase(first.world.clock) == DayPhase.AFTERNOON
    again = first.world.apply_tick(emit_tick(Verb.TOUCH, "a2"))
    assert again.status == TickStatus.DUPLICATE
    assert again.world.clock == first.world.clock
    # ellipse: minutes -> next block of day
    for hour, minute, expected in ((11, 30, 30), (6, 0, 360), (23, 10, 50), (0, 0, 360)):
        got = minutes_to_next_block(make_game_clock(1, hour, minute))
        assert got == expected, f"ellipse at {hour}:{minute:02d} -> {got}"

    # ellipse end to end = start of block  
    jump = compose_world(make_game_clock(1, 11, 30),  rooms=("start",), doors=(), player_room="start").apply_tick(
        emit_ellipse(make_game_clock(1, 11, 30), "e1"))
    assert jump.status == TickStatus.APPLIED
    assert (jump.world.clock.hour, jump.world.clock.minute) == (12, 0)
    assert read_phase(jump.world.clock) == DayPhase.AFTERNOON
    # 23:10 -> next day 00:00
    night = compose_world(make_game_clock(1, 23, 10), rooms=("start",), doors=(), player_room="start").apply_tick(emit_ellipse(make_game_clock(1, 23, 10), "e2"))
    assert (night.world.clock.day, night.world.clock.hour) == (2, 0)
    assert len(GameMode) == 1
    assert read_mode() is GameMode.EXPLORE
    assert read_mode().value == "explore"
    # warnings: phase change
    start = make_game_clock(1, 11, 30)
    moved = compose_world(start, rooms=("start",), doors=(), player_room="start").apply_tick(emit_tick(Verb.TOUCH, "w1")).world.clock
    assert check_phase(start, moved) == (PlayerWarning(reason=WhyWarn.PHASE_CHANGED),)
    calm = make_game_clock(1, 10, 0)
    talked = compose_world(calm, rooms=("start",), doors=(), player_room="start").apply_tick(emit_tick(Verb.TALK, "w2")).world.clock
    assert check_phase(calm, talked) == ()

    print("GameMaster kernel OK")

if __name__ == "__main__":
    run_game_master_kernel_tests()
