import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

QuestionType = Literal["mcq", "true_false", "fill_blank", "numerical", "short", "long", "descriptive"]
Difficulty = Literal["easy", "medium", "hard"]


class Criterion(BaseModel):
    criterion: str = Field(min_length=1, max_length=200)
    marks: int = Field(ge=1, le=100)


# --- Question bank ------------------------------------------------------------------------------------------------


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    topic_id: uuid.UUID | None
    text: str
    type: str
    marks: int
    difficulty: str
    options: list[str]
    answer: str | None
    rubric: list[dict[str, Any]]
    explanation: str
    source_kind: str
    document_id: uuid.UUID | None
    source_page: int | None
    source_label: str
    status: str
    created_at: datetime
    topic_title: str | None = None
    unit_title: str | None = None
    filename: str | None = None


class QuestionIn(BaseModel):
    """A hand-written question (H1 "instructor-created")."""

    topic_id: uuid.UUID | None = None
    text: str = Field(min_length=5, max_length=5000)
    type: QuestionType
    marks: int = Field(ge=1, le=100)
    difficulty: Difficulty = "medium"
    options: list[str] = Field(default_factory=list, max_length=8)
    answer: str | None = Field(default=None, max_length=10000)
    rubric: list[Criterion] = Field(default_factory=list, max_length=10)
    explanation: str = Field(default="", max_length=5000)


class QuestionPatch(BaseModel):
    """Review and correction (H3). Only the fields sent change."""

    topic_id: uuid.UUID | None = None
    text: str | None = Field(default=None, min_length=5, max_length=5000)
    type: QuestionType | None = None
    marks: int | None = Field(default=None, ge=1, le=100)
    difficulty: Difficulty | None = None
    options: list[str] | None = Field(default=None, max_length=8)
    answer: str | None = Field(default=None, max_length=10000)
    rubric: list[Criterion] | None = Field(default=None, max_length=10)
    explanation: str | None = Field(default=None, max_length=5000)
    status: Literal["draft", "approved"] | None = None


class PaperOut(BaseModel):
    """A question paper and its extraction (H3)."""

    document_id: uuid.UUID
    filename: str
    document_status: str
    job_id: uuid.UUID | None
    status: str  # none | queued | running | succeeded | failed
    error: str | None
    questions: int
    drafts: int


# --- Quizzes ------------------------------------------------------------------------------------------------------


class QuizRequest(BaseModel):
    """H4 filters. On a course: optionally one unit or some topics (A21)."""

    count: int = Field(default=5, ge=1, le=30)
    difficulty: Difficulty | None = None
    marks: int | None = Field(default=None, ge=1, le=100)
    types: list[QuestionType] = Field(default_factory=list)
    unit_id: uuid.UUID | None = None
    topic_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)


class QuizQuestionOut(BaseModel):
    """What a student sees while answering: no key, rubric or explanation."""

    id: uuid.UUID
    position: int
    text: str
    type: str
    marks: int
    difficulty: str
    options: list[str]
    topic_title: str | None


class AttemptSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    score: float
    max_score: float
    job_id: uuid.UUID | None
    error: str | None
    created_at: datetime
    graded_at: datetime | None


class QuizOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    settings: dict[str, Any]
    status: str
    job_id: uuid.UUID | None
    error: str | None
    created_at: datetime
    questions: list[QuizQuestionOut] = Field(default_factory=list)
    attempts: list[AttemptSummary] = Field(default_factory=list)


class AnswerIn(BaseModel):
    question_id: uuid.UUID
    answer: str = Field(default="", max_length=20000)


class AttemptIn(BaseModel):
    answers: list[AnswerIn] = Field(max_length=100)


class AnswerResult(BaseModel):
    question: QuizQuestionOut
    answer: str
    score: float | None
    max_score: float
    graded_by: str | None  # auto | ai (estimated)
    correct: bool | None  # objective questions only
    feedback: dict[str, Any]
    reference_answer: str | None  # mcq/true_false: the correct option's text
    explanation: str


class AttemptResults(BaseModel):
    attempt: AttemptSummary
    quiz_id: uuid.UUID
    quiz_title: str
    course_id: uuid.UUID
    answers: list[AnswerResult]


# --- LLM output (flexible: checked and cleaned by grading.normalize_question / check_key) ------------------------


class LlmPaperQuestion(BaseModel):
    label: str
    text: str
    marks: int | None
    type: str
    options: list[str]
    difficulty: str
    page: int


class LlmPaper(BaseModel):
    questions: list[LlmPaperQuestion]


class LlmCriterion(BaseModel):
    criterion: str
    marks: int


class LlmKey(BaseModel):
    index: int
    answer: str
    rubric: list[LlmCriterion]
    explanation: str


class LlmNewQuestion(BaseModel):
    topic: int
    type: str
    text: str
    marks: int
    difficulty: str
    options: list[str]
    answer: str
    rubric: list[LlmCriterion]
    explanation: str


class LlmQuizWork(BaseModel):
    keys: list[LlmKey]
    questions: list[LlmNewQuestion]


class LlmAwarded(BaseModel):
    criterion: str
    awarded: float


class LlmGrade(BaseModel):
    index: int
    criteria: list[LlmAwarded]
    correct_concepts: list[str]
    missing_concepts: list[str]
    incorrect_statements: list[str]
    suggestions: list[str]


class LlmGrades(BaseModel):
    grades: list[LlmGrade]
