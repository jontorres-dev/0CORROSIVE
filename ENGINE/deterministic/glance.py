from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from .World import GameClock, World, compose_world, make_game_clock 
from .door import Door, other_side

## 1. Exit: class
class Exit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    
    door_id: str
    leads_to: str

## 2. RoomGlance: class
class RoomGlance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    room_id: str
    exits: tuple[Exit, ...]
    clock: GameClock

## 3. read_glance: world -> what the player sees in current room
def read_glance(world: World) -> RoomGlance:
    room = world.player_room
    exits = tuple(
        Exit(
            door_id=door.id,
            leads_to=other_side(door, room),
        )
        for door in world.doors
        if room in door.rooms
    )
    return RoomGlance(room_id=room, exits=exits, clock=world.clock)



## 4. Tests
def run_glance_kernel_tests() -> None:
    clock = make_game_clock(1, 9, 0)
    doors = (
        Door(id="cellar_door", rooms=("hall", "cellar"), locked=True, key_id="old key"),
        Door(id="garden_door", rooms=("garden", "hall")),
        Door(id="back_door", rooms=("cellar", "garden")),
    )
    world = compose_world(clock, rooms=("hall", "cellar", "garden"), doors=doors, player_room="hall")
    glance = read_glance(world)

    # 1. room and clock come from the world
    assert glance.room_id == "hall"
    assert glance.clock == clock

    # 2. only doors touching the room, leading to the other side
    assert glance.exits == (
        Exit(door_id="cellar_door", leads_to="cellar"),
        Exit(door_id="garden_door", leads_to="garden"),
    )

    # 3. the lock stays hidden
    assert "locked" not in Exit.model_fields
    assert "key_id" not in Exit.model_fields

    # 4. room with no doors has no exits
    lonely = compose_world(clock, rooms=("start",), doors=(), player_room="start")
    assert read_glance(lonely).exits == ()

    print("Glance kernel OK")


if __name__ == "__main__":
    run_glance_kernel_tests()
