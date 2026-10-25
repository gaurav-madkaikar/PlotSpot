from movie_companion.discussion_context import SupportOption
from movie_companion.discussion_relation_context import supplemental_option


def test_missing_answer_details_recover_only_an_existing_offered_sentence():
    quotes=['Cole learns the language changes her perception of time.']
    direct='Her visions are premonitions; her daughter will be born in the future.'
    options=[SupportOption(direct,('direct',)),SupportOption('The captain leaves to warn the crew.',('irrelevant',))]
    assert supplemental_option('Her visions are premonitions and her daughter will be born in the future.',options,quotes)==options[0]


def test_no_guess_for_missing_terms_not_present_in_evidence():
    option=SupportOption('Cole learns a language from visitors.',('one',))
    assert supplemental_option('A secret diary reveals her hidden motive.',[option],[option.text]) is None


def test_one_matching_term_cannot_add_speculative_context():
    option=SupportOption('The captain hides a diary from visitors.',('one',))
    assert supplemental_option('A secret diary.',[option],['The captain leaves the ship.']) is None


def test_selected_or_identity_sentence_is_not_duplicated():
    text='Her visions are premonitions of future events.'
    option=SupportOption(text,('one',))
    assert supplemental_option(text,[option],[text]) is None
    assert supplemental_option(text,[SupportOption(text,('one',),True)],[]) is None
