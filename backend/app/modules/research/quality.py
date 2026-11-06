"""Source quality (PRD E3): a deterministic domain tier, so scores are explainable and cost nothing.
Low tiers aren't dropped, but they don't count as authoritative when verifying claims."""

AUTHORITATIVE = 0.75

# (source_type, quality, domains). An entry starting with "." matches any host ending with it (e.g. ".edu").
TIERS: list[tuple[str, float, tuple[str, ...]]] = [
    # Anyone-can-upload document sites, some on .edu: checked before the academic suffixes.
    ("user_uploads", 0.45, ("academia.edu", "slideshare.net", "studocu.com", "scribd.com", "issuu.com")),
    ("academic", 0.9, (
        ".edu", ".ac.in", ".ac.uk", ".edu.au", ".ac.jp", "nptel.ac.in", "ocw.mit.edu", "arxiv.org", "ieee.org",
        "acm.org", "springer.com", "sciencedirect.com", "nature.com", "jstor.org", "researchgate.net",
        "semanticscholar.org", "ncbi.nlm.nih.gov", "cambridge.org", "oup.com", "wiley.com",
    )),
    ("official_docs", 0.9, (
        ".gov", ".gov.in", ".nic.in", "docs.python.org", "python.org", "docs.oracle.com", "developer.mozilla.org",
        "learn.microsoft.com", "postgresql.org", "kernel.org", "w3.org", "ietf.org", "rfc-editor.org",
        "cppreference.com", "isocpp.org", "docs.github.com", "numpy.org", "scikit-learn.org", "pytorch.org",
        "tensorflow.org", "mysql.com", "nist.gov",
    )),
    ("encyclopedia", 0.8, ("wikipedia.org", "britannica.com", "mathworld.wolfram.com", "plato.stanford.edu")),
    ("educational", 0.6, (
        "geeksforgeeks.org", "tutorialspoint.com", "javatpoint.com", "programiz.com", "w3schools.com",
        "khanacademy.org", "coursera.org", "edx.org", "byjus.com", "takeuforward.org", "baeldung.com",
        "freecodecamp.org", "brilliant.org", "studytonight.com", "cs.stackexchange.com", "math.stackexchange.com",
        "neso.academy", "scaler.com", "simplilearn.com", "guru99.com", "datacamp.com",
    )),
    ("forum", 0.35, ("stackoverflow.com", "stackexchange.com", "reddit.com", "quora.com")),
    ("blog", 0.4, ("medium.com", "dev.to", "substack.com", "blogspot.com", "wordpress.com", "hashnode.dev")),
]
DEFAULT = ("web", 0.45)


def _matches(host: str, entry: str) -> bool:
    return host.endswith(entry) if entry.startswith(".") else host == entry or host.endswith("." + entry)


def classify(host: str) -> tuple[str, float]:
    """(source_type, quality 0–1) for a hostname."""
    host = host.lower().removeprefix("www.")
    for source_type, quality, entries in TIERS:  # first match wins: listed most specific/trusted first
        if any(_matches(host, e) for e in entries):
            return source_type, quality
    return DEFAULT
