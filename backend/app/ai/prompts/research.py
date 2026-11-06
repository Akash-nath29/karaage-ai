"""Research prompts. Bump PROMPT_VERSION on any change: it's stored with every research run (PRD rule 19)."""

PROMPT_VERSION = "research-v1"

PLAN_SYSTEM = (
    "You plan focused web research for a student's study guide on one syllabus topic. "
    "You first judge what the student's own materials already cover."
)


def plan_prompt(topic: str, subtopics: str, materials: str, max_queries: int) -> str:
    return f"""Topic: {topic}
Subtopics: {subtopics or "none listed"}

Passages from the student's uploaded materials (may be empty or off-topic):
<document>
{materials or "(no passages found)"}
</document>

Return:
- covered: concepts of this topic the passages explain well enough to teach from (short phrases).
- missing: concepts of this topic (and its subtopics) the passages don't explain, or explain too thinly.
- sufficient: true only if the passages alone could teach the whole topic.
- queries: at most {max_queries} web search queries that target the missing concepts first, then clear
  explanations and worked examples. Specific, academic wording; no site: operators; no duplicates."""


VERIFY_SYSTEM = "You cross-check factual claims across sources for a study guide. You are careful and literal."


def verify_prompt(topic: str, sources: str) -> str:
    return f"""Topic: {topic}

<source> blocks: S1, S2, … are web pages; M1, M2, … are passages from the student's own materials.
{sources}

List at most 8 important factual claims about this topic that a study guide would state (definitions, properties,
conditions, complexities, formulas, dates). For each claim:
- supporting: ids of the sources that state or directly support it.
- contradicting: ids of the sources that state something incompatible with it.
Use only the ids above. Don't list claims that no source supports."""
