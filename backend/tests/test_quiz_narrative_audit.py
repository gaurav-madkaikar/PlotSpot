from movie_companion.quiz_narrative_audit import audit_questions,render_markdown


def test_audit_flags_review_candidates_without_making_publication_decisions():
    report=audit_questions([{'movie_id':1,'title':'Fixture','questions':[
        {'id':'q1','question':'How many years does the journey last?'},
        {'id':'q2','question':'Why does the hero abandon the mission?'},
    ]}])
    assert report['status']=='advisory' and report['question_count']==2
    assert report['flagged_count']==1
    assert report['items'][0]['review_priority']=='review'
    assert report['items'][1]['review_priority']=='unflagged'
    assert 'cannot delete' in ' '.join(report['limitations'])
    markdown=render_markdown(report)
    assert 'How many years' in markdown and 'Why does the hero' not in markdown
