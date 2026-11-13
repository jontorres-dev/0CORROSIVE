from enum import Enum
from pathlib import Path
import hashlib
import tempfile
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from .World import World, Tick, TickStatus, TickApplication, compose_world, make_game_clock


## 0. Classes WhySaveFail, RunEnd, SaveError exception
class WhySaveFail(str, Enum):
    SLOT_EXISTS = "slot_exists"
    SLOT_NOT_FOUND = "slot_not_found"
    WORLD_MISMATCH = "world_mismatch"

class RunEnd(str, Enum):
    DEATH = "death"
    GAME_OVER = "game_over"
    ENDING = "ending"

class SaveError(Exception):
    def __init__(self, reason: WhySaveFail) -> None:
        super().__init__(reason.value)
        self.reason = reason

## 1. Save Slot -> nests player id and playtrough id
class SaveSlot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    
    player_id: str = Field(..., min_length=1, pattern=r"^[A-Za-z0-9-]+$")
    playthrough_id: str = Field(..., min_length=1, pattern=r"^[A-Za-z0-9-]+$")
## 1.1 Snapshot -> World plus fingerprint
class Snapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    world_id: str = Field(..., min_length=1)
    world: World

## 2. Save paths -> builds snapshot and log file names
def save_paths(slot: SaveSlot, data_dir: Path) -> tuple[Path, Path]:
    base = f"{slot.player_id}_{slot.playthrough_id}"
    return (data_dir / f"{base}_snapshot.json", data_dir / f"{base}_log.jsonl")

## 3. Write snapshot -> saves current World as JSON
def write_snapshot(world: World, path: Path) -> None:
    snapshot = Snapshot(world_id=world_fingerprint(world), world=world)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(snapshot.model_dump_json(), encoding="utf-8")
    temp_path.replace(path)

## 4. Read snapshot -> rebuilds World from JSON
def read_snapshot(path: Path) -> World:
    try:
        snapshot = Snapshot.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError:
        raise SaveError(WhySaveFail.WORLD_MISMATCH)
    if world_fingerprint(snapshot.world) != snapshot.world_id:
        raise SaveError(WhySaveFail.WORLD_MISMATCH)
    return snapshot.world

## 5. Append event -> adds one applied tick as line in the log
def append_event(tick: Tick, path: Path) -> None:
    with path.open("a", encoding="utf-8") as log:
        log.write(tick.model_dump_json() + "\n")

## 6. Read events -> rebuilds the ticks from log in order
def read_events(path: Path) -> tuple[Tick, ...]:
    if not path.exists():
        return ()
    try:
        return tuple(Tick.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except ValidationError:
        raise SaveError(WhySaveFail.WORLD_MISMATCH)    

## 7. World fingerprint -> deterministic id built from current World data
def world_fingerprint(world: World) -> str:
    return hashlib.sha256(world.model_dump_json().encode("utf-8")).hexdigest()

## 8. New Game through SLOT_EXISTS
def new_game(slot: SaveSlot, world: World, data_dir: Path) -> World:
    snapshot_path, log_path = save_paths(slot, data_dir)
    if snapshot_path.exists():
        raise SaveError(WhySaveFail.SLOT_EXISTS)
    log_path.write_text("", encoding="utf-8")
    write_snapshot(world, snapshot_path)
    return world

## 9. Reads snapshot, renders log from path -> SLOT_NOT_FOUND
def load_game(slot: SaveSlot, data_dir: Path) -> World:
    snapshot_path, log_path = save_paths(slot, data_dir)
    if not snapshot_path.exists():
        raise SaveError(WhySaveFail.SLOT_NOT_FOUND)
    world = read_snapshot(snapshot_path)
    for tick in read_events(log_path):     
        application = world.apply_tick(tick)
        if application.status is TickStatus.CONFLICT:
            raise SaveError(WhySaveFail.WORLD_MISMATCH)
        world = application.world
    return world

## 10. Auto-save function: record_tick
def record_tick(slot: SaveSlot, tick: Tick, application: TickApplication, data_dir: Path, snapshot_every: int = 1) -> bool:
    if snapshot_every < 1:
        raise ValueError("snapshot_every must be >= 1")        
    snapshot_path, log_path = save_paths(slot, data_dir)
    if not snapshot_path.exists():
        raise SaveError(WhySaveFail.SLOT_NOT_FOUND)
    if application.status is not TickStatus.APPLIED:
        return False
    if application.world.applied_ticks[-1] != tick:
        raise SaveError(WhySaveFail.WORLD_MISMATCH)
    if load_game(slot, data_dir).apply_tick(tick).world != application.world:
        raise SaveError(WhySaveFail.WORLD_MISMATCH)    
    append_event(tick, log_path)
    if len(read_events(log_path)) >= snapshot_every:
        write_snapshot(application.world, snapshot_path)
        log_path.write_text("", encoding="utf-8")
    return True

## 11. Lists saves available
def list_saves(player_id: str, data_dir: Path) -> tuple[SaveSlot, ...]:
    try:
        SaveSlot(player_id=player_id, playthrough_id="probe")
    except ValidationError:
        return ()
    prefix = f"{player_id}_"
    suffix = "_snapshot.json"
    slots = []
    for path in sorted(data_dir.glob(f"{prefix}*{suffix}")):
        try:
            slots.append(SaveSlot(player_id=player_id, playthrough_id=path.name[len(prefix):-len(suffix)]))
        except ValidationError:
            continue
    return tuple(slots)

## 12. Ending game function
def end_game(slot: SaveSlot, reason: RunEnd, data_dir: Path) -> RunEnd:
    snapshot_path, log_path = save_paths(slot, data_dir)
    if not snapshot_path.exists():
        raise SaveError(WhySaveFail.SLOT_NOT_FOUND)
    snapshot_path.unlink()
    log_path.unlink(missing_ok=True)
    return reason

## 13. Persistence kernel tests
def run_persistence_kernel_tests() -> None:
    world = compose_world(make_game_clock(1, 10, 0), ("hall",), (), "hall")
    tick_a = Tick(amount=60, reason="wait", source_action_id="a1")
    tick_b = Tick(amount=10, reason="wait", source_action_id="a2")
    tick_c = Tick(amount=5, reason="wait", source_action_id="a3")
    jon = SaveSlot(player_id="jon", playthrough_id="run")

    def expect_fail(reason: WhySaveFail, call) -> None:
        try:
            call()
        except SaveError as error:
            assert error.reason is reason
            return
        raise AssertionError(f"expected {reason.value}")

    with tempfile.TemporaryDirectory() as temp:
        data_dir = Path(temp)
        snapshot_path, log_path = save_paths(jon, data_dir)

        # 1. Round trip
        new_game(jon, world, data_dir)
        assert load_game(jon, data_dir) == world

        # 2. SLOT_EXISTS and SLOT_NOT_FOUND
        ghost = SaveSlot(player_id="ghost", playthrough_id="run")
        expect_fail(WhySaveFail.SLOT_EXISTS, lambda: new_game(jon, world, data_dir))
        expect_fail(WhySaveFail.SLOT_NOT_FOUND, lambda: load_game(ghost, data_dir))
        expect_fail(WhySaveFail.SLOT_NOT_FOUND, lambda: record_tick(ghost, tick_a, world.apply_tick(tick_a), data_dir))

        # 3. record_tick APPLIED and DUPLICATE
        applied = world.apply_tick(tick_a)
        assert record_tick(jon, tick_a, applied, data_dir) is True
        duplicate = applied.world.apply_tick(tick_a)
        assert duplicate.status is TickStatus.DUPLICATE
        assert record_tick(jon, tick_a, duplicate, data_dir) is False
        assert load_game(jon, data_dir) == applied.world

        # 4. Wrong world
        expect_fail(WhySaveFail.WORLD_MISMATCH, lambda: record_tick(jon, tick_c, applied.world.apply_tick(tick_b), data_dir))
        other = compose_world(make_game_clock(5, 3, 0), ("cellar",), (), "cellar")
        expect_fail(WhySaveFail.WORLD_MISMATCH, lambda: record_tick(jon, tick_b, other.apply_tick(tick_b), data_dir))
        end_game(jon, RunEnd.DEATH, data_dir)

        # 5. snapshot_every
        new_game(jon, world, data_dir)
        first = world.apply_tick(tick_a)
        record_tick(jon, tick_a, first, data_dir, snapshot_every=1)
        assert log_path.read_text(encoding="utf-8") == ""
        second = first.world.apply_tick(tick_b)
        record_tick(jon, tick_b, second, data_dir, snapshot_every=3)
        assert len(read_events(log_path)) == 1
        third = second.world.apply_tick(tick_c)
        record_tick(jon, tick_c, third, data_dir, snapshot_every=2)
        assert log_path.read_text(encoding="utf-8") == ""
        assert read_snapshot(snapshot_path) == third.world
        try:
            record_tick(jon, tick_c, third, data_dir, snapshot_every=0)
            raise AssertionError("expected ValueError")
        except ValueError:
            pass
        end_game(jon, RunEnd.DEATH, data_dir)

        # 6. Replay and crash recovery
        new_game(jon, world, data_dir)
        step = world.apply_tick(tick_a)
        record_tick(jon, tick_a, step, data_dir, snapshot_every=5)
        step = step.world.apply_tick(tick_b)
        record_tick(jon, tick_b, step, data_dir, snapshot_every=5)
        loaded = load_game(jon, data_dir)
        assert (loaded.clock.hour, loaded.clock.minute) == (11, 10)
        write_snapshot(loaded, snapshot_path)
        assert load_game(jon, data_dir) == loaded

        # 7. Corrupted files
        log_path.write_text('{"amount":60,"rea', encoding="utf-8")
        expect_fail(WhySaveFail.WORLD_MISMATCH, lambda: load_game(jon, data_dir))
        conflict = Tick(amount=99, reason="wait", source_action_id="a1")
        log_path.write_text(conflict.model_dump_json() + "\n", encoding="utf-8")
        expect_fail(WhySaveFail.WORLD_MISMATCH, lambda: load_game(jon, data_dir))
        log_path.write_text("", encoding="utf-8")
        snapshot_path.write_text(snapshot_path.read_text(encoding="utf-8").replace('"hall"', '"vault"'), encoding="utf-8")
        expect_fail(WhySaveFail.WORLD_MISMATCH, lambda: load_game(jon, data_dir))
        snapshot_path.write_text("{", encoding="utf-8")
        expect_fail(WhySaveFail.WORLD_MISMATCH, lambda: load_game(jon, data_dir))
        end_game(jon, RunEnd.DEATH, data_dir)

        # 8. Orphan log
        log_path.write_text(tick_a.model_dump_json() + "\n", encoding="utf-8")
        new_game(jon, world, data_dir)
        assert load_game(jon, data_dir) == world

        # 9. list_saves
        new_game(SaveSlot(player_id="jon", playthrough_id="run2"), world, data_dir)
        new_game(SaveSlot(player_id="jon-x", playthrough_id="run"), world, data_dir)
        (data_dir / "jon_a.b_snapshot.json").write_text("x", encoding="utf-8")
        assert sorted(slot.playthrough_id for slot in list_saves("jon", data_dir)) == ["run", "run2"]
        assert list_saves("*", data_dir) == ()
        assert list_saves("", data_dir) == ()
        assert list_saves("nobody", data_dir) == ()

        # 10. RunEnd deletes the save, same playthrough_id restarts
        for reason in RunEnd:
            assert end_game(jon, reason, data_dir) is reason
            assert not snapshot_path.exists() and not log_path.exists()
            new_game(jon, world, data_dir)

        # 11. Dangerous ids
        for bad in ("../x", "a_b", "", "a/b", "a b"):
            for fields in ({"player_id": bad, "playthrough_id": "run"}, {"player_id": "jon", "playthrough_id": bad}):
                try:
                    SaveSlot(**fields)
                    raise AssertionError(f"accepted {bad!r}")
                except ValidationError:
                    pass

        # 12. Players are isolated
        ana = SaveSlot(player_id="ana", playthrough_id="run")
        new_game(ana, other, data_dir)
        assert load_game(ana, data_dir) == other
        assert load_game(jon, data_dir) == world
        end_game(ana, RunEnd.GAME_OVER, data_dir)
        assert load_game(jon, data_dir) == world

        # 13. end_game without save
        expect_fail(WhySaveFail.SLOT_NOT_FOUND, lambda: end_game(ana, RunEnd.DEATH, data_dir))

        # 14. Load without log
        log_path.unlink()
        assert load_game(jon, data_dir) == world

        # 15. No .tmp left behind
        assert not list(data_dir.glob("*.tmp"))

        # 16. world_id matches and changes
        stored = Snapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8"))
        assert stored.world_id == world_fingerprint(world)
        assert world_fingerprint(world.apply_tick(tick_a).world) != stored.world_id

    print("Persistence kernel OK")


if __name__ == "__main__":
    run_persistence_kernel_tests()

