from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from .World import GameClock, DayPhase, TickStatus, TickApplication, compose_world, make_game_clock
from .GameMaster import GameMode, read_phase, read_mode, check_phase, emit_tick
from .verbs import Verb
from .warn import PlayerWarning, WhyWarn
from .glance import RoomGlance, read_glance


## 1. Context Class Model to Narration: time of the day, game mode and warnings
class NarrationContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    clock: GameClock
    phase: DayPhase
    mode: GameMode
    status: TickStatus
    warnings: tuple[PlayerWarning, ...]
    glance: RoomGlance

## 2. Function to compose Context
def build_context(before: GameClock, after: GameClock, application: TickApplication) -> NarrationContext: 
    return NarrationContext(
        clock=after,
        phase=read_phase(after),
        mode=read_mode(),
        status=application.status,
        warnings=check_phase(before,after),
        glance=read_glance(application.world)
    )


def run_context_kernel_tests() -> None:
    start = make_game_clock(1, 11, 30)
    first = compose_world(start, rooms=("start",), doors=(), player_room="start").apply_tick(emit_tick(Verb.TOUCH, "c1"))
    ctx = build_context(start, first.world.clock, first)
    assert ctx.clock == make_game_clock(1, 12, 30)
    assert ctx.phase == DayPhase.AFTERNOON
    assert ctx.mode == GameMode.EXPLORE
    assert ctx.status == TickStatus.APPLIED
    assert ctx.warnings == (PlayerWarning(reason=WhyWarn.PHASE_CHANGED),)

    assert ctx.glance.room_id == "start"

    calm = make_game_clock(1, 10, 0)
    talked = compose_world(calm, rooms=("start",), doors=(), player_room="start").apply_tick(emit_tick(Verb.TALK, "c2"))
    assert build_context(calm, talked.world.clock, talked).warnings == ()

    again = first.world.apply_tick(emit_tick(Verb.TOUCH, "c1"))
    dup = build_context(first.world.clock, again.world.clock, again)
    assert dup.status == TickStatus.DUPLICATE

    try:
        ctx.mode = GameMode.EXPLORE
        raise AssertionError("context must be frozen")
    except ValueError:
        pass

    print("Context kernel OK")


if __name__ == "__main__":
    run_context_kernel_tests()



