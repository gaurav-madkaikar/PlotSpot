import pytest

from movie_companion.quiz_answer_support import literal_answer_support


def test_complete_answer_is_matched_after_safe_text_normalization():
    quote='Cobb recruits Eames, a sharp-tongued identity forger.'
    assert literal_answer_support('Eames',quote) is True
    assert literal_answer_support('identity forger',quote) is True


def test_partial_name_does_not_support_a_more_specific_answer():
    quote='Blanc later gathers everyone in the drawing room.'
    assert literal_answer_support('Detective Benoit Blanc',quote) is False


def test_role_description_does_not_support_an_unstated_character_name():
    quote='The young employee becomes the lobby boy at the hotel.'
    assert literal_answer_support('Zero Moustafa',quote) is False


@pytest.mark.parametrize('answer,quote',[(None,'A useful quote.'),('Answer',None)])
def test_non_text_inputs_are_rejected(answer,quote):
    with pytest.raises(ValueError):literal_answer_support(answer,quote)
