"""Story quiz with grounded factual answers and explicitly unscored readings."""

from typing import Literal

from pydantic import BaseModel, Field

from .movie_questions import MovieQuestion, MovieQuestionService, QuestionCitation, QuestionError


class QuizItem(BaseModel):
    id: str
    origin: Literal["reviewed", "generated"] = "reviewed"
    question: str
    kind: Literal["plot", "ending", "interpretation"] = "plot"
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str = Field(max_length=4000)
    citations: list[QuestionCitation] = Field(min_length=1, max_length=3)


class MovieQuiz(BaseModel):
    can_generate_more: bool = True
    prepared_at: str | None = None
    content_version: str | None = None
    status: str = Field(pattern="^(ready|source_unavailable|spoiler_permission_required)$")
    message: str
    items: list[QuizItem] = Field(default_factory=list, max_length=40)


BANK = (
    {"id": "dust-coordinates", "kind": "plot", "question": "Where do the dust patterns in Murph's room lead Cooper and Murph in Interstellar?",
     "options": ["A secret NASA facility", "An abandoned school", "A launch site on Mars", "Mann's planet"],
     "correct_index": 0, "fact": "nasa", "source_phrase": "binary code specifying coordinates"},
    {"id": "mann-motive", "kind": "plot", "evidence_question": "What does Mann hope for when he falsifies his data?", "question": "Why did Dr. Mann falsify his planet's data in Interstellar?",
     "options": ["To prove the gravity equation", "To make Earth habitable", "In the hope of being rescued", "To stop time dilation"],
     "correct_index": 2, "fact": "rescu", "source_phrase": "he falsified his data"},
    {"id": "watch-message", "kind": "ending", "question": "How does Cooper send the data TARS collected to Murph from the tesseract in Interstellar?",
     "options": ["Through a radio call", "Using Morse code through her watch's second hand", "By sending a video recording", "By rewriting her notebooks"],
     "correct_index": 1, "fact": "morse", "source_phrase": "second hand of her wristwatch"},
    {"id": "watch-meaning", "kind": "interpretation", "question": "What might the watch represent when Cooper reaches Murph across time?",
     "evidence_question": "How does Cooper send the data TARS collected to Murph from the tesseract in Interstellar?",
     "options": ["A reminder of lost time", "Their enduring connection across time", "A symbol of scientific curiosity", "The burden of Cooper's promise to return"],
     "correct_index": 1, "fact": "morse", "source_phrase": "second hand of her wristwatch",
     "reading": "One supported reading is that the watch represents Cooper and Murph's enduring connection across time: it becomes the channel through which they work together. Other readings, including lost time or a promise to return, are possible. This is an interpretation, not a confirmed hidden message or a scored answer."},
)


async def build_supported_items(service: MovieQuestionService, *, movie_id: int, allow_spoilers: bool, bank: tuple, evidence_purpose: str = "story") -> MovieQuiz:
    items, answers = [], {}
    for entry in bank:
        evidence_question = entry.get("evidence_question", entry["question"])
        try:
            if evidence_question not in answers:
                answers[evidence_question] = await service.ask(movie_id, MovieQuestion(question=evidence_question, allow_spoilers=allow_spoilers), evidence_phrase=entry["source_phrase"], evidence_purpose=evidence_purpose)
            result = answers[evidence_question]
        except QuestionError:
            if not items:
                raise
            break  # Keep already verified questions when a later branch fails.
        if result.status in ("source_unavailable", "spoiler_permission_required"):
            return MovieQuiz(status=result.status, message=result.answer)
        supporting = [citation for citation in result.citations
                      if entry["fact"] in citation.excerpt.casefold() and entry["source_phrase"] in citation.excerpt.casefold()]
        if result.status != "answered" or not supporting or entry["fact"] not in result.answer.casefold():
            continue
        items.append(QuizItem(
            id=entry["id"], kind=entry.get("kind", "plot"), question=entry["question"], options=entry["options"],
            correct_index=entry["correct_index"], explanation=(entry["reading"] + "\n\nScene evidence: " + result.answer) if "reading" in entry else result.answer, citations=supporting,
        ))
    if not items:
        raise QuestionError(502, "No source-supported quiz could be prepared. Try again.")
    return MovieQuiz(status="ready", message="Your story round is ready." if len(items) == len(bank) else "A shorter round is ready. Some questions did not have enough verified support.", items=items)


async def create_quiz(service: MovieQuestionService, *, movie_id: int, allow_spoilers: bool) -> MovieQuiz:
    return await build_supported_items(service, movie_id=movie_id, allow_spoilers=allow_spoilers, bank=BANK)
