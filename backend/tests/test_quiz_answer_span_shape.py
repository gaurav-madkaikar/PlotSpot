from movie_companion.quiz_answer_span_shape import (
    answer_shape_score,
    answer_span_problems,
    parse_brief_constraints,
)


def test_explicit_duration_constraint_blocks_quantities_only_when_requested():
    brief = "Test why the journey is costly; omit the exact duration."
    assert parse_brief_constraints(brief).omit_quantities
    assert "forbidden_quantity" in answer_span_problems(
        "the next three years", brief=brief
    )
    assert "forbidden_quantity" not in answer_span_problems(
        "enormous time due to dilation", brief=brief
    )


def test_unrecognized_brief_does_not_infer_quantity_exclusion():
    brief = "Test how three years of running change Forrest."
    assert not parse_brief_constraints(brief).omit_quantities
    assert "forbidden_quantity" not in answer_span_problems(
        "the next three years", brief=brief
    )


def test_answer_shape_rejects_fragments_and_keeps_standalone_phrases():
    brief = "Replace with why he buys the boat: to fulfil his promise."
    assert "leading_connector" in answer_span_problems(
        "but the maneuver costs time", brief=brief
    )
    assert "leading_relative" in answer_span_problems(
        "who later joins Fight Club", brief=brief
    )
    assert "trailing_fragment" in answer_span_problems(
        "fulfilling Bubba's", brief=brief
    )
    assert answer_span_problems("fulfilling Bubba's dream", brief=brief) == []


def test_name_avoidance_rejects_identity_only_but_keeps_narrative_role():
    brief = "Test the ship's narrative role rather than its name."
    constraints = parse_brief_constraints(brief)
    assert constraints.avoid_identity_only
    assert "identity_only" in answer_span_problems(
        "The Nebuchadnezzar", brief=brief
    )
    assert "identity_only" not in answer_span_problems(
        "the crew's base against the machines", brief=brief
    )


def test_shape_score_prefers_concise_standalone_answer():
    assert answer_shape_score("fulfilling Bubba's dream") > answer_shape_score(
        "Forrest returns to Alabama and buys a shrimping boat fulfilling Bubba's dream"
    )
