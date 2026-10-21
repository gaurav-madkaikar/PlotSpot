"""Reviewed starter content, compiled once against a real source snapshot."""
from .source_sections import routed_chunks
from .evidence_store import SourceDocument
from .movie_questions import QuestionCitation
from .movie_quiz import BANK, MovieQuiz, QuizItem
from .movie_facts import PRODUCTION, MovieFacts, MovieFact

CONTENT_VERSION = "interstellar-sections-v3"

STORY_EXTRA = (
    dict(id="wormhole-location", kind="plot", question="Where is the wormhole that opens humanity's route to another galaxy?", options=["Near Mars", "Near Saturn", "Inside the Sun", "Beyond Pluto"], correct_index=1, fact="saturn", source_phrase="a wormhole appeared near saturn", explanation="The wormhole appears near Saturn, opening a route to another galaxy."),
    dict(id="ship-name", kind="plot", question="What is the name of the spacecraft Cooper pilots through the wormhole?", options=["Lazarus", "Discovery", "Endurance", "Gargantua"], correct_index=2, fact="endurance", source_phrase="pilot the endurance spacecraft", explanation="Cooper pilots the Endurance. Gargantua is the black hole, while Lazarus names the earlier expedition."),
    dict(id="scouts", kind="plot", question="Which expedition sent volunteers ahead to investigate potentially habitable planets?", options=["The Lazarus expedition", "The Apollo expedition", "The Endurance expedition", "The Voyager expedition"], correct_index=0, fact="lazarus", source_phrase="volunteers of the lazarus expedition", explanation="The Lazarus expedition sends volunteers ahead to evaluate the planets before Cooper's mission."),
    dict(id="lost-years", kind="plot", question="After Miller's planet, how much time has passed for the people aboard Endurance?", options=["Two years", "Seven years", "Fifty-one years", "Twenty-three years"], correct_index=3, fact="23 years", source_phrase="23 years have elapsed on the endurance", explanation="Twenty-three years pass on the Endurance while Cooper and Brand experience a much shorter visit to Miller's planet."),
    dict(id="missing-measurements", kind="plot", question="What crucial information was missing from Professor Brand's gravity-equation solution?", options=["The age of Saturn", "Measurements from inside a black hole", "Mann's weather reports", "The number of embryos"], correct_index=1, fact="black hole", source_phrase="without measurements from inside a black hole", explanation="Professor Brand cannot complete the solution without measurements from inside a black hole. This missing evidence is central to the mission's dilemma."),
    dict(id="cooper-detaches", kind="plot", question="Why do Cooper and TARS detach their craft during the slingshot around Gargantua?", options=["To return directly to Earth", "To rescue Mann", "To lighten Endurance so Brand can reach Edmunds' planet", "To repair the wormhole"], correct_index=2, fact="lighten", source_phrase="to lighten the endurance", explanation="They detach to lighten the Endurance, giving Brand and CASE the chance to reach Edmunds' planet."),
    dict(id="murph-ghost", kind="ending", question="Whose identity is revealed behind Murph's mysterious 'ghost'?", options=["Cooper", "Professor Brand", "Mann", "Romilly"], correct_index=0, fact="cooper", source_phrase="he had always been murph's", explanation="Inside the tesseract, Cooper realizes that he himself was the presence Murph called her ghost."),
)
FACT_EXTRA = (
    dict(id="score-without-script", title="A score that began with a father and child", text="Nolan initially gave Hans Zimmer a single page about a father leaving his child for work, rather than the screenplay or plot details. That connection shaped the soundtrack’s early development.", fact="single page", source_phrase="a single page that told the story of a father leaving his child for work"),
    dict(id="robot-performer", title="The performer hidden behind the robots", text="Bill Irwin voiced and physically controlled the robots during filming, and his image was digitally removed. Josh Stewart later replaced his voice for CASE.", fact="bill irwin", source_phrase="bill irwin voiced and physically controlled both robots"),
    dict(id="projected-space", title="Space imagery the actors could actually see", text="Visual effects were created ahead of filming so digital projectors could display them behind the actors, instead of having them perform in front of green screens.", fact="projectors", source_phrase="allowing digital projectors to display them behind the actors"),
)
EXPLANATIONS = {
    "dust-coordinates": "Cooper reads the dust patterns as binary coordinates. They lead him and Murph to a secret NASA facility headed by Professor Brand.",
    "mann-motive": "Mann falsifies his planet's data because he hopes someone will come to rescue him; his apparent promise of a habitable world is a deception.",
    "watch-message": "Cooper uses Morse code through the second hand of Murph's wristwatch to transmit the data TARS collected. Murph uses it to complete the gravity-equation solution.",
}


def compile_collection(source: SourceDocument):
    """Evidence-checked curated content; no inferred or generated facts are added."""
    if source.movie_id != 157336:
        from .reviewed_content import compile_reviewed_collection
        return compile_reviewed_collection(source)
    if not source.sections:
        raise ValueError("New preparation requires section-aware evidence; fetch Wikipedia again instead of using an older flattened snapshot")
    story_chunks = routed_chunks(source, purpose="story")
    background_chunks = routed_chunks(source, purpose="background")

    def citation(entry, *, purpose):
        chunks = story_chunks if purpose == "story" else background_chunks
        matches = [c for c in chunks if entry["source_phrase"] in c.text.casefold() and entry["fact"] in c.text.casefold()]
        if not matches:
            raise ValueError(f"Missing supporting source statement: {entry['id']}")
        chunk = matches[0]
        # Stable IDs refer to the source revision and extraction offsets.
        import hashlib
        identifier = hashlib.sha256((source.revision + str(chunk.start)).encode()).hexdigest()[:32]
        return [QuestionCitation(passage_id=identifier, source_label=source.source_label, source_ref=source.source_ref, revision=source.revision, excerpt=chunk.text)]

    stories = [*BANK[:3], *STORY_EXTRA, BANK[3]]
    quiz = MovieQuiz(status="ready", message="Saved story collection: ten questions and an unscored reflection.", items=[
        QuizItem(id=e["id"], kind=e["kind"], question=e["question"], options=e["options"], correct_index=e["correct_index"], explanation=e.get("reading", e.get("explanation", EXPLANATIONS.get(e["id"], ""))), citations=citation(e, purpose="story")) for e in stories
    ])
    entries = [*PRODUCTION, *FACT_EXTRA]
    facts = MovieFacts(status="ready", message="Saved, source-reviewed production background from Wikipedia.", items=[MovieFact(id=e["id"], title=e["title"], text=e.get("text", e.get("display_text")), citations=citation(e, purpose="background")) for e in entries])
    return quiz, facts
