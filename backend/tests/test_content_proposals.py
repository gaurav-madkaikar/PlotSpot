import pytest
from pydantic import ValidationError

from movie_companion.content_proposals import ContentProposals, ProposalEvidence, check_proposals, validate_evidence

STORY = 'Cobb is promised a return home to his children after completing the mission.'
BACKGROUND = 'The crew constructed a rotating corridor set for the gravity sequence.'


def evidence():
    return [ProposalEvidence(passage_id='P1', purpose='story', text=STORY),
            ProposalEvidence(passage_id='P2', purpose='background', text=BACKGROUND)]


def payload():
    return {'facts':[{'title':'A moving corridor', 'text':BACKGROUND, 'passage_id':'P2', 'evidence_quote':BACKGROUND}],
            'questions':[{'question':'What is Cobb promised for completing the mission?',
                          'options':['A return to his children','A new ship','A royal title','A university post'],
                          'correct_index':0,'passage_id':'P1','evidence_quote':STORY}]}


def test_empty_proposals_allow_abstention_and_supported_drafts_still_need_review():
    assert check_proposals(ContentProposals(facts=[],questions=[]),evidence()) == []
    findings = check_proposals(ContentProposals.model_validate(payload()),evidence())
    assert all(f['support_checks_passed'] and f['semantic_review_required'] for f in findings)


@pytest.mark.parametrize('change', ['unknown', 'purpose', 'quote', 'duplicates', 'options'])
def test_invalid_source_links_or_duplicate_outputs_are_reported(change):
    data = payload()
    if change == 'unknown': data['facts'][0]['passage_id'] = 'P9'
    elif change == 'purpose': data['facts'][0]['passage_id'] = 'P1'
    elif change == 'quote': data['facts'][0]['evidence_quote'] = 'This sentence does not occur in the supplied source.'
    elif change == 'duplicates': data['facts'].append(data['facts'][0].copy())
    else: data['questions'][0]['options'][1] = data['questions'][0]['options'][0]
    assert any(not f['support_checks_passed'] for f in check_proposals(ContentProposals.model_validate(data),evidence()))


@pytest.mark.parametrize('change', ['extra-action', 'string-index', 'bool-index', 'bad-index', 'too-many', 'wrong-alias'])
def test_schema_rejects_unexpected_actions_and_invalid_shapes(change):
    data = payload()
    if change == 'extra-action': data['tool_call'] = {'command':'delete files'}
    elif change == 'string-index': data['questions'][0]['correct_index'] = '0'
    elif change == 'bool-index': data['questions'][0]['correct_index'] = False
    elif change == 'bad-index': data['questions'][0]['correct_index'] = 4
    elif change == 'too-many': data['facts'] *= 4
    else: data['facts'][0]['passage_id'] = 'https://evil.example'
    with pytest.raises(ValidationError): ContentProposals.model_validate(data)


def test_duplicate_evidence_ids_and_excess_context_are_rejected():
    with pytest.raises(ValueError): validate_evidence([evidence()[0],evidence()[0]])
    with pytest.raises(ValueError): validate_evidence(evidence()*5)
    with pytest.raises(ValueError): validate_evidence([])


def test_quote_membership_does_not_prove_the_correct_answer():
    data = payload()
    data['questions'][0]['correct_index'] = 1  # unsupported answer with a real quote
    findings = check_proposals(ContentProposals.model_validate(data),evidence())
    assert findings[1]['support_checks_passed']
    assert findings[1]['semantic_review_required']  # separate quality evaluation is essential


@pytest.mark.parametrize('question', [
    'Which actor portrays Heywood in the film?',
    "When was Stephen King's novella published?",
    'What did the reviewer say about the movie?',
])
def test_clear_credit_source_material_and_review_questions_are_outside_story_quiz(question):
    data = payload()
    data['questions'][0]['question'] = question
    finding = check_proposals(ContentProposals.model_validate(data), evidence())[1]
    assert finding['problems'] == ['outside_story_quiz_scope']


@pytest.mark.parametrize(('title','text'), [
    ('Running Time', 'The film has a running time of 142 minutes.'),
    ('Prison Term', 'The protagonist spends nineteen years behind prison walls.'),
    ('Budget', 'The reported production budget is 25 million US dollars.'),
    ('Revenue', 'The movie earned revenue of 30 million US dollars.'),
])
def test_clear_metadata_and_plot_details_are_outside_background_facts(title,text):
    data = payload()
    data['facts'][0].update(title=title,text=text)
    finding = check_proposals(ContentProposals.model_validate(data), evidence())[0]
    assert 'outside_background_fact_scope' in finding['problems']


@pytest.mark.parametrize(('title','text'), [
    ('Inflated Budget Practices', 'Studios inflate movie budgets with corporate overheads.'),
    ('Cinematographer Credit', 'Roger Deakins handled the camera work for the film.'),
    ('Box Office Performance', 'The film required critical praise to sustain its box office earnings.'),
    ('AMC Century City Review', 'The film was reviewed at AMC Century City in August.'),
])
def test_generic_opinion_and_plain_credit_facts_are_low_value(title,text):
    data = payload()
    data['facts'][0].update(title=title,text=text)
    finding = check_proposals(ContentProposals.model_validate(data), evidence())[0]
    assert set(finding['problems']) & {'low_value_background_fact','outside_background_fact_scope'}
