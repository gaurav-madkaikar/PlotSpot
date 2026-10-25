from movie_companion.quiz_question_shape import distinctly_tested,recognized_wording,relation

def test_explicit_different_properties_and_disjoint_color_objects():
    assert distinctly_tested("How old is Louise's daughter when she dies?","What is Louise's profession?")
    assert distinctly_tested("What color is the captain's uniform?","What color is the spacecraft?")
    assert distinctly_tested('Where is the vault located?','Who opens the vault?')

def test_unknown_aliases_or_same_reason_do_not_force_novelty():
    assert not distinctly_tested('What color is Endurance?','What color is the spacecraft?')
    assert not distinctly_tested('What future need motivates the aliens?','Why do the aliens offer help?')
    assert not distinctly_tested('What happens next?','Where is the vault?')
    assert not distinctly_tested('What color is the spacecraft uniform?','What color is the uniform?')

def test_spelled_numbers_and_future_reasons_are_valid_answer_types():
    assert recognized_wording("How old is Louise's daughter when she dies?",'Twelve')
    assert recognized_wording('Why do the aliens offer help to humans?','They will need human help later')
    assert recognized_wording('How does Mira open the door?','By turning the key')
    assert not recognized_wording('How old is she?','Twelve')
    assert not recognized_wording('How does Mira open the door?','The clock')
