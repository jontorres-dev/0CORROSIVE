from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .deny import ActionDenied, WhyDeny
from .World import GameClock, make_game_clock


# Relation: the mold. "A — predicate — B".
class Relation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    id: str = Field(..., min_length=1)
    subject: str = Field(..., min_length=1)
    predicate: str = Field(..., min_length=1)
    object: str = Field(..., min_length=1)


# Flag: the consolidated fact. Born when a Relation is satisfied and the GameMaster confirms.
class Flag(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    id: str = Field(..., min_length=1)
    source_action_id: str = Field(..., min_length=1)
    relation_id: str = Field(..., min_length=1)


# Playthrough: Stage 2 axis. Owns Relations and the Flags that consolidate them.
class Playthrough(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    relations: tuple[Relation, ...] = ()
    flags: tuple[Flag, ...] = ()


# Condition: minimum condition declared by the Module author.
# Linked to a Relation; met when a Flag consolidating that Relation exists.
class Condition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    id: str = Field(..., min_length=1)
    required_relation_id: str = Field(..., min_length=1)


# Effect: possible effect declared by the Module author.
# Progress proposes it when the matching Condition is met.
# kind="ENDING" or kind="GAME_OVER" marks a special end-of-run Effect.
class Effect(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    id: str = Field(..., min_length=1)
    required_relation_id: str = Field(..., min_length=1)
    payload: str = Field(..., min_length=1)
    kind: str | None = None


# EffectProposal: what Progress emits. Pure observation; never writes.
class EffectProposal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    effect_id: str = Field(..., min_length=1)
    required_relation_id: str = Field(..., min_length=1)
    payload: str = Field(..., min_length=1)


# EffectDecision: GameMaster verdict on a proposal. Carries the reason.
class EffectDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    proposal: EffectProposal
    approved: bool
    reason: str = Field(..., min_length=1)


# RunEndResult: result of the separate end-of-run path.
class RunEndResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    kind: str = Field(..., min_length=1)
    effect_id: str = Field(..., min_length=1)


def create_flag(
    playthrough: Playthrough,
    source_action_id: str,
    flag_id: str,
    relation_id: str,
    gm_confirmed_plausible: bool,
) -> Flag | None:
    """Return a Flag only when:
    - the Relation exists in this Playthrough,
    - that Relation has not yet been consolidated into a Flag,
    - the GameMaster confirmed it is plausible.
    Otherwise return None. Never creates a pending Flag.
    """
    relation = next((r for r in playthrough.relations if r.id == relation_id), None)
    if relation is None:
        return None
    if any(f.relation_id == relation_id for f in playthrough.flags):
        return None
    if not gm_confirmed_plausible:
        return None
    return Flag(id=flag_id, source_action_id=source_action_id, relation_id=relation_id)


def consolidate_flag(playthrough: Playthrough, flag: Flag) -> Playthrough:
    """Return a new Playthrough with the Flag added. Idempotent if already present."""
    if any(f.id == flag.id for f in playthrough.flags):
        return playthrough
    return Playthrough(relations=playthrough.relations, flags=(*playthrough.flags, flag))


def has_flag(playthrough: Playthrough, flag_id: str) -> bool:
    """Pure query: does this Playthrough already hold the given Flag?"""
    return any(f.id == flag_id for f in playthrough.flags)


def flags_from_action(playthrough: Playthrough, source_action_id: str) -> tuple[Flag, ...]:
    """Pure query: Flags consolidated from a given action."""
    return tuple(f for f in playthrough.flags if f.source_action_id == source_action_id)


def Setting(playthrough: Playthrough, clock: GameClock) -> dict:
    """Read-only snapshot of Playthrough + clock for upper layers."""
    return {
        "relations": playthrough.relations,
        "flags": playthrough.flags,
        "clock": clock,
    }


def require_flag(playthrough: Playthrough, required_flag_id: str) -> None:
    """Veto any effect that depends on a Flag that does not exist."""
    if not has_flag(playthrough, required_flag_id):
        raise ActionDenied(WhyDeny.NO_FLAG)


def is_condition_met(playthrough: Playthrough, condition: Condition) -> bool:
    """Pure query: is there a consolidated Flag for this Condition's Relation?"""
    return any(f.relation_id == condition.required_relation_id for f in playthrough.flags)


SPECIAL_END_KINDS = frozenset({"ENDING", "GAME_OVER"})


def propose_effects(
    playthrough: Playthrough,
    conditions: tuple[Condition, ...],
    effects: tuple[Effect, ...],
    applied_effect_ids: tuple[str, ...],
) -> tuple[EffectProposal, ...]:
    """Progress observes consolidated Flags and Module declarations.
    Returns proposals only for met Conditions whose Effect is not yet applied.
    Never writes to Playthrough, World, or Cast.
    """
    proposals: list[EffectProposal] = []
    for effect in effects:
        if effect.kind in SPECIAL_END_KINDS:
            continue
        if effect.id in applied_effect_ids:
            continue
        matching = next(
            (c for c in conditions if c.required_relation_id == effect.required_relation_id),
            None,
        )
        if matching is None:
            continue
        if is_condition_met(playthrough, matching):
            proposals.append(
                EffectProposal(
                    effect_id=effect.id,
                    required_relation_id=effect.required_relation_id,
                    payload=effect.payload,
                )
            )
    return tuple(proposals)


def validate_effect(proposal: EffectProposal, playthrough: Playthrough) -> EffectDecision:
    """GameMaster validation. Approves only when a Flag consolidates the required Relation.
    Same path for any proposal, forced or not.
    """
    met = any(f.relation_id == proposal.required_relation_id for f in playthrough.flags)
    if met:
        return EffectDecision(proposal=proposal, approved=True, reason="flag_consolidated")
    return EffectDecision(proposal=proposal, approved=False, reason="no_flag")


def evaluate_run_end(
    playthrough: Playthrough,
    effects: tuple[Effect, ...],
    applied_effect_ids: tuple[str, ...],
) -> RunEndResult | None:
    """Separate end-of-run path. Does not call propose/validate/commit.
    Returns a result only when a special-kind Effect exists, its Flag is consolidated,
    and it has not yet been applied as an end. Otherwise returns None.
    """
    for effect in effects:
        if effect.kind not in SPECIAL_END_KINDS:
            continue
        if effect.id in applied_effect_ids:
            continue
        if any(f.relation_id == effect.required_relation_id for f in playthrough.flags):
            return RunEndResult(kind=effect.kind, effect_id=effect.id)
    return None


def run_playthrough_kernel_tests() -> None:
    rel = Relation(id="r1", subject="Fulano", predicate="PISOU", object="ratoeira")
    pt = Playthrough(relations=(rel,))

    # matches open Relation + GM confirms → Flag
    flag = create_flag(pt, "act1", "flag_pisou", "r1", gm_confirmed_plausible=True)
    assert flag is not None
    assert flag.relation_id == "r1"

    # Relation does not exist → None
    assert create_flag(pt, "act2", "x", "r99", True) is None

    # GM refuses → None
    assert create_flag(pt, "act3", "y", "r1", False) is None

    # consolidate
    pt2 = consolidate_flag(pt, flag)
    assert has_flag(pt2, "flag_pisou") is True

    # already consolidated → None
    assert create_flag(pt2, "act4", "z", "r1", True) is None

    # idempotent consolidate
    pt3 = consolidate_flag(pt2, flag)
    assert pt3.flags == pt2.flags

    # veto without Flag
    try:
        require_flag(pt, "flag_pisou")
        raise AssertionError("should have vetoed")
    except ActionDenied as e:
        assert e.reason is WhyDeny.NO_FLAG

    require_flag(pt2, "flag_pisou")

    # flags_from_action
    assert flags_from_action(pt2, "act1") == (flag,)
    assert flags_from_action(pt2, "act99") == ()

    # Setting
    clock = make_game_clock(1, 9, 0)
    s = Setting(pt2, clock)
    assert s["flags"] == (flag,)
    assert s["relations"] == (rel,)
    assert s["clock"] == clock

    # replay
    again = create_flag(pt, "act1", "flag_pisou", "r1", True)
    assert again == flag

    # --- RECOEF minimal acceptance ---
    # Module: 1 Relation + 1 Condition + 1 Effect
    cond = Condition(id="c1", required_relation_id="r1")
    eff = Effect(id="e1", required_relation_id="r1", payload="ratoeira_ativada")
    conditions = (cond,)
    effects = (eff,)

    # 1. without Flag: propose empty; forced Proposal goes through GameMaster and is vetoed
    proposals_none = propose_effects(pt, conditions, effects, ())
    assert proposals_none == ()

    forced = EffectProposal(effect_id="e1", required_relation_id="r1", payload="ratoeira_ativada")
    decision_veto = validate_effect(forced, pt)
    assert decision_veto.approved is False
    assert decision_veto.reason == "no_flag"
    # Playthrough unchanged
    assert pt.flags == ()
    assert pt.relations == (rel,)

    # 2. consolidate Flag → propose → validate approves → commit
    from .GameMaster import commit_approved_effect
    from .Cast import Cast
    from .World import compose_world

    pt_with_flag = consolidate_flag(pt, flag)
    proposals = propose_effects(pt_with_flag, conditions, effects, ())
    assert len(proposals) == 1
    assert proposals[0].effect_id == "e1"

    decision_ok = validate_effect(proposals[0], pt_with_flag)
    assert decision_ok.approved is True
    assert decision_ok.reason == "flag_consolidated"

    world0 = compose_world(make_game_clock(1, 9, 0), rooms=("start",), doors=(), player_room="start")
    cast0 = Cast()
    world1, cast1 = commit_approved_effect(world0, cast0, decision_ok)
    assert "e1" in world1.applied_effects
    assert "e1" in cast1.notifications
    # Playthrough unchanged by the effect
    assert pt_with_flag.flags == (flag,)
    assert pt_with_flag.relations == (rel,)

    # 3. replay: same state → same proposals; no new Flag or Relation; commit is no-op
    proposals_again = propose_effects(pt_with_flag, conditions, effects, world1.applied_effects)
    assert proposals_again == ()
    world2, cast2 = commit_approved_effect(world1, cast1, decision_ok)
    assert world2.applied_effects == world1.applied_effects
    assert cast2.notifications == cast1.notifications
    assert pt_with_flag.flags == (flag,)
    assert pt_with_flag.relations == (rel,)

    # 4. forced no-flag path already checked; also confirm commit is no-op on veto
    world_veto, cast_veto = commit_approved_effect(world0, cast0, decision_veto)
    assert world_veto.applied_effects == world0.applied_effects
    assert cast_veto.notifications == cast0.notifications
    assert pt.flags == ()
    assert pt.relations == (rel,)

    # determinism: two independent runs from same initial produce same World/Cast
    world_a, cast_a = commit_approved_effect(world0, cast0, decision_ok)
    world_b, cast_b = commit_approved_effect(world0, cast0, decision_ok)
    assert world_a.applied_effects == world_b.applied_effects
    assert cast_a.notifications == cast_b.notifications

    # --- Incremento 3: optional ENDING / GAME_OVER ---
    from .GameMaster import record_run_end

    # Case 2: Module without special Effect → no end
    no_end = evaluate_run_end(pt_with_flag, effects, world1.applied_effects)
    assert no_end is None

    # Case 1: Module with special Effect + Condition met → end result
    ending_eff = Effect(
        id="end1",
        required_relation_id="r1",
        payload="run_ends",
        kind="ENDING",
    )
    effects_with_end = (eff, ending_eff)
    end_result = evaluate_run_end(pt_with_flag, effects_with_end, world1.applied_effects)
    assert end_result is not None
    assert end_result.kind == "ENDING"
    assert end_result.effect_id == "end1"

    # Normal Effects still proposed (not aborted by end path)
    normal_proposals = propose_effects(pt_with_flag, conditions, effects_with_end, world1.applied_effects)
    assert normal_proposals == ()  # e1 already applied; end is not proposed by normal path

    # Fresh world for end recording
    world_end0 = compose_world(make_game_clock(1, 9, 0), rooms=("start",), doors=(), player_room="start")
    # First commit a normal effect, then record end
    world_norm, _ = commit_approved_effect(world_end0, Cast(), decision_ok)
    assert "e1" in world_norm.applied_effects
    world_ended = record_run_end(world_norm, end_result)
    assert world_ended.run_end == "ENDING"
    assert "end1" in world_ended.applied_effects

    # Replay: re-evaluate after recorded → None (already applied as end); World unchanged
    end_again = evaluate_run_end(pt_with_flag, effects_with_end, world_ended.applied_effects)
    assert end_again is None
    world_ended2 = record_run_end(world_ended, end_result)
    assert world_ended2.run_end == world_ended.run_end
    assert world_ended2.applied_effects == world_ended.applied_effects

    # Both cases coexist; normal cycle still works independently
    assert evaluate_run_end(pt_with_flag, effects, ()) is None
    assert evaluate_run_end(pt, effects_with_end, ()) is None  # no Flag → no end

    print("Playthrough / Flag kernel OK")


if __name__ == "__main__":
    run_playthrough_kernel_tests()
