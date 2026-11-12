"""NLP analysis: structure, readability, repetition, capitalization, grammar, citations, score, summary, suggestions."""
import re
from collections import Counter
from math import log, sqrt

import numpy as np

EXPECTED = {
    "Abstract": r"abstract|executive summary",
    "Introduction": r"introduction|background",
    "Methodology": r"method|approach|design|implementation",
    "Results": r"result|finding|evaluation|analysis",
    "Conclusion": r"conclusion|future work|recommendation",
    "References": r"reference|bibliograph|works cited",
}

WEIGHTS = {
    "Structure": 0.18,
    "Readability": 0.15,
    "Repetition": 0.15,
    "Keyword coverage": 0.12,
    "Length balance": 0.12,
    "Capitalization": 0.09,
    "Grammar": 0.10,
    "Citations": 0.09,
}

# Common grammar / style mistakes regex patterns
GRAMMAR_RULES = [
    (
        re.compile(r"\b(\w+)\s+\1\b", re.I),
        "Repeated consecutive word",
        "Remove the duplicated word.",
    ),
    (
        re.compile(r"\b(a)\s+([aeiouAEIOU][a-zA-Z]{2,})\b"),
        "Article mismatch ('a' before vowel sound)",
        "Use 'an' instead of 'a' before a vowel sound (unless pronounced with a 'yu' sound like 'university').",
    ),
    (
        re.compile(r"\b(an)\s+([bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ][a-zA-Z]{2,})\b"),
        "Article mismatch ('an' before consonant)",
        "Use 'a' instead of 'an' before a consonant sound (unless silent 'h' like 'hour').",
    ),
    (
        re.compile(r"\b(could|would|should|must|might)\s+of\b", re.I),
        "Incorrect modal phrase ('... of')",
        "Replace 'of' with 'have' (e.g., 'should have', 'could have').",
    ),
    (
        re.compile(r"\b(alot|wierd|recieve|seperate|definately|occured|untill|wich|teh)\b", re.I),
        "Common spelling / usage error",
        "Correct spelling (e.g., 'a lot', 'weird', 'receive', 'separate', 'definitely', 'occurred', 'until').",
    ),
    (
        re.compile(r"\b(doesn't|don't|isn't|aren't|wasn't|weren't|can't|won't|it's|they're|we're|you're)\b", re.I),
        "Informal contraction in formal writing",
        "Expand contractions (e.g., 'do not', 'is not', 'it is') for formal academic or business reports.",
    ),
    (
        re.compile(r"\s+[,.;:!?]"),
        "Extra space before punctuation",
        "Remove the space preceding the punctuation mark.",
    ),
    (
        re.compile(r"[,.;:!?][A-Za-z]"),
        "Missing space after punctuation",
        "Add a single space after punctuation marks.",
    ),
    (
        re.compile(r"\b(there|their|they're)\s+(is|are|was|were)\s+many\b", re.I),
        "Potential homophone / agreement check",
        "Verify 'there/their/they're' usage and subject-verb agreement.",
    ),
    (
        re.compile(r"\b(less)\s+(people|students|items|files|errors|words|papers|users|studies)\b", re.I),
        "Quantifier error ('less' with countable noun)",
        "Use 'fewer' instead of 'less' for countable nouns.",
    ),
]

EXCEPT_AN = {"hour", "honest", "honor", "honour", "heir", "herb"}
EXCEPT_A = {"user", "users", "university", "unique", "unit", "uniform", "union", "useful", "european", "one"}
STOP_WORDS = set("a an and are as at be been but by for from had has have he her hers him his i if in into is it its me my of on or our ours she so than that the their theirs them then there these they this those to was we were what when where which who will with you your".split())


def _term_counts(text):
    return Counter(word for word in re.findall(r"(?u)\\b\\w\\w+\\b", text.lower()) if word not in STOP_WORDS)


def _tfidf_matrix(documents):
    """Build L2-normalized TF-IDF rows without an external NLP dependency."""
    counts = [_term_counts(doc) for doc in documents]
    vocabulary = {term for row in counts for term in row}
    if not vocabulary:
        return np.zeros((len(documents), 0))
    document_frequency = Counter(term for row in counts for term in row)
    terms = list(vocabulary)
    matrix = np.zeros((len(documents), len(terms)))
    for row_index, row in enumerate(counts):
        for column, term in enumerate(terms):
            if row[term]:
                idf = log((1 + len(documents)) / (1 + document_frequency[term])) + 1
                matrix[row_index, column] = row[term] * idf
        norm = np.linalg.norm(matrix[row_index])
        if norm:
            matrix[row_index] /= norm
    return matrix


def _clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.split()) >= 5]


def _syllables(word):
    word = word.lower()
    groups = re.findall(r"[aeiouy]+", word)
    n = len(groups) - (1 if word.endswith("e") and len(groups) > 1 else 0)
    return max(1, n)


def check_sections(headings, text):
    out = []
    for name, pat in EXPECTED.items():
        in_headings = any(re.search(pat, h, re.I) for h in headings)
        in_lines = re.search(rf"^\s*(\d+\.?\s*)?({pat})\w*\s*$", text, re.I | re.M)
        out.append({"name": name, "found": bool(in_headings or in_lines)})
    return out


def find_repeats(paragraphs, threshold=0.6, top=5):
    idx = [i for i, p in enumerate(paragraphs) if len(p.split()) >= 12]
    if len(idx) < 2:
        return [], 0.0
    tfidf = _tfidf_matrix([paragraphs[i] for i in idx])
    # L2-normalized rows make dot products cosine similarities.
    sim = tfidf @ tfidf.T
    pairs = []
    for a in range(len(idx)):
        for b in range(a + 1, len(idx)):
            if sim[a, b] >= threshold:
                pairs.append((float(sim[a, b]), idx[a], idx[b]))
    pairs.sort(reverse=True)
    involved = {i for _, i, j in pairs for i in (i, j)}
    frac = len(involved) / len(idx)
    repeats = [
        {
            "a": f"Para {i+1}",
            "b": f"Para {j+1}",
            "similarity": round(s, 2),
            "text": paragraphs[i][:140] + "...",
        }
        for s, i, j in pairs[:top]
    ]
    return repeats, frac


def readability(text):
    sents = _sentences(text) or [text]
    words = re.findall(r"[A-Za-z']+", text)
    if not words:
        return 0.0, 0.0
    asl = len(words) / len(sents)
    asw = sum(_syllables(w) for w in words) / len(words)
    ease = 206.835 - 1.015 * asl - 84.6 * asw
    return ease, asl


def keyword_spread(paragraphs, k=10):
    if len(paragraphs) < 3:
        return 50.0
    freq = Counter()
    for paragraph in paragraphs:
        freq.update(_term_counts(paragraph))
    top = [term for term, _ in freq.most_common(k)]
    thirds = np.array_split(np.arange(len(paragraphs)), 3)
    spread = []
    for t in top:
        hit = sum(any(t in _term_counts(paragraphs[i]) for i in part) for part in thirds)
        spread.append(hit / 3)
    return 100 * float(np.mean(spread)) if spread else 0.0


def check_capitalization(paragraphs, headings, top=12):
    """Check sentence starts, standalone pronoun 'i', all-caps shouting, and heading case."""
    issues = []
    total_checks = 1

    # 1. Headings capitalization check
    for h in headings:
        words = h.split()
        if len(words) >= 2 and h.isupper() and len(h) > 12:
            issues.append({
                "category": "All-Caps Heading",
                "snippet": h[:90],
                "advice": "Avoid ALL CAPS in long headings; use Title Case instead.",
            })
        elif words and words[0][0].islower():
            issues.append({
                "category": "Uncapitalized Heading",
                "snippet": h[:90],
                "advice": "Capitalize the first letter of headings.",
            })

    # 2. Paragraph sentence starts, standalone 'i', and excessive ALL-CAPS words
    for idx, p in enumerate(paragraphs):
        sents = re.split(r"(?<=[.!?])\s+", p.strip())
        for s in sents:
            s_clean = s.lstrip(" \"'([")
            if not s_clean:
                continue
            total_checks += 1
            if s_clean[0].islower():
                issues.append({
                    "category": "Sentence Start",
                    "snippet": f'Para {idx+1}: "{s[:85]}..."',
                    "advice": "Capitalize the first letter of every sentence.",
                })

        # Standalone lowercase 'i'
        if re.search(r"(?<![A-Za-z0-9_])i(?![A-Za-z0-9_'])", p):
            issues.append({
                "category": "Pronoun 'I'",
                "snippet": f'Para {idx+1}: "{p[:85]}..."',
                "advice": "Always capitalize the personal pronoun 'I'.",
            })

        # Excessive ALL CAPS words (excluding standard acronyms <= 5 chars)
        caps_words = [w for w in re.findall(r"\b[A-Z]{6,}\b", p)]
        if len(caps_words) >= 2:
            issues.append({
                "category": "Excessive ALL CAPS",
                "snippet": f"Para {idx+1}: {', '.join(caps_words[:4])}",
                "advice": "Avoid writing full words in ALL CAPS inside body paragraphs.",
            })

    penalty = min(65, len(issues) * 6.5)
    score = _clamp(round(100 - penalty))
    return score, issues[:top], len(issues)


def check_grammar(paragraphs, top=15):
    """Rule-based grammar, article, spelling, spacing, and formality checker."""
    issues = []
    for idx, p in enumerate(paragraphs):
        for pat, label, advice in GRAMMAR_RULES:
            for m in pat.finditer(p):
                matched = m.group(0)
                # Filter false positives for a/an exceptions
                if "Article mismatch ('a'" in label:
                    nxt = m.group(2).lower()
                    if nxt in EXCEPT_A or nxt.isupper():
                        continue
                if "Article mismatch ('an'" in label:
                    nxt = m.group(2).lower()
                    if nxt in EXCEPT_AN or nxt.isupper():
                        continue
                # Ignore decimals like 3.5 or abbreviations like e.g. for missing space check
                if "Missing space after punctuation" in label:
                    if re.search(r"\d\.\d|e\.g\.|i\.e\.|etc\.|vs\.|U\.S\.|Ph\.D\.", p[max(0, m.start()-3):m.end()+3], re.I):
                        continue

                start = max(0, m.start() - 25)
                end = min(len(p), m.end() + 25)
                context = p[start:end].strip()
                issues.append({
                    "category": label,
                    "match": matched.strip(),
                    "snippet": f'Para {idx+1}: "...{context}..."',
                    "advice": advice,
                })
                if len(issues) >= 40:
                    break
            if len(issues) >= 40:
                break

    total_count = len(issues)
    penalty = min(70, total_count * 5.0)
    score = _clamp(round(100 - penalty))
    return score, issues[:top], total_count


def check_citations(text, paragraphs):
    """Detect APA/MLA/IEEE inline citations and match against References/Bibliography section."""
    # Split body and references section
    ref_match = re.search(r"(?im)^\s*(\d+\.?\s*)?(references|bibliography|works cited)\s*$", text)
    if ref_match:
        body_text = text[:ref_match.start()]
        ref_text = text[ref_match.end():]
    else:
        body_text = text
        ref_text = ""

    # Inline citation patterns:
    # 1) Author-Year: (Smith, 2020), (Smith & Jones, 2021), (Smith et al., 2022), Smith (2020)
    author_year = re.findall(
        r"\(([A-Z][A-Za-z\-]+(?:\s+(?:&|and)\s+[A-Z][A-Za-z\-]+|\s+et\s+al\.)?,?\s*(?:19|20)\d{2}[a-z]?(?:;\s*[^)]+)?)\)",
        body_text,
    )
    narrative_ay = re.findall(
        r"\b([A-Z][A-Za-z\-]+(?:\s+et\s+al\.)?)\s*\(((?:19|20)\d{2}[a-z]?)\)",
        body_text,
    )
    # 2) Numeric IEEE / Vancouver: [1], [1, 2], [1-4]
    numeric_cites = re.findall(r"\[(\d+(?:\s*[-–,]\s*\d+)*)\]", body_text)

    inline_items = []
    for item in author_year:
        inline_items.append(f"({item.strip()})")
    for author, yr in narrative_ay:
        inline_items.append(f"{author} ({yr})")
    for num in numeric_cites:
        inline_items.append(f"[{num}]")

    # Deduplicate preserving order
    seen = set()
    unique_inline = []
    for c in inline_items:
        if c not in seen:
            seen.add(c)
            unique_inline.append(c)

    # Parse reference entries
    ref_lines = [line.strip() for line in ref_text.splitlines() if len(line.strip().split()) >= 4]
    has_ref_section = bool(ref_match)

    # Cross-check inline citations vs references
    unmatched_inline = []
    for c in unique_inline[:20]:
        if c.startswith("["):
            first_num = re.findall(r"\d+", c)[0]
            if ref_text and not re.search(rf"(?m)^\s*(\[{first_num}\]|{first_num}\.)", ref_text):
                unmatched_inline.append(c)
        else:
            surname_m = re.search(r"[A-Z][A-Za-z\-]{2,}", c)
            year_m = re.search(r"(19|20)\d{2}", c)
            if surname_m and ref_text:
                surname = surname_m.group(0).lower()
                yr = year_m.group(0) if year_m else ""
                if surname not in ref_text.lower() or (yr and yr not in ref_text):
                    unmatched_inline.append(c)

    # Detect style
    if numeric_cites and not (author_year or narrative_ay):
        style = "Numeric (IEEE / Vancouver)"
    elif (author_year or narrative_ay) and not numeric_cites:
        style = "Author-Year (APA / Harvard)"
    elif numeric_cites and (author_year or narrative_ay):
        style = "Mixed (Author-Year + Numeric)"
    else:
        style = "None detected"

    # Compute citation score
    score = 40
    if unique_inline:
        score += 25
    if has_ref_section and len(ref_lines) >= 2:
        score += 25
    elif has_ref_section:
        score += 10
    if unique_inline and has_ref_section and len(unmatched_inline) == 0:
        score += 10
    else:
        score -= min(25, len(unmatched_inline) * 5)

    if len(paragraphs) >= 6 and not unique_inline and not has_ref_section:
        score = 25

    score = _clamp(round(score))

    return {
        "score": score,
        "style": style,
        "inlineCount": len(unique_inline),
        "referenceCount": len(ref_lines),
        "hasReferenceSection": has_ref_section,
        "sampleCitations": unique_inline[:10],
        "unmatchedCitations": unmatched_inline[:8],
    }


def summarize(paragraphs, n=4):
    sents = _sentences(" ".join(paragraphs))
    if len(sents) <= n:
        return " ".join(sents)
    m = _tfidf_matrix(sents)
    scores = m.sum(axis=1) / np.array([sqrt(len(s.split())) for s in sents])
    scores[: max(3, len(sents) // 10)] *= 1.25
    keep = sorted(np.argsort(scores)[::-1][:n])
    return " ".join(sents[i] for i in keep)


def analyze(filename, ex):
    paras, headings, text = ex["paragraphs"], ex["headings"], ex["text"]
    words = len(re.findall(r"\w+", text))
    sections = check_sections(headings, text)
    repeats, rep_frac = find_repeats(paras)
    ease, asl = readability(text)

    cap_score, cap_issues, cap_total = check_capitalization(paras, headings)
    gram_score, gram_issues, gram_total = check_grammar(paras)
    citation_report = check_citations(text, paras)

    lens = [len(p.split()) for p in paras]
    good_para = sum(30 <= n <= 200 for n in lens) / max(1, len(lens))
    scores = {
        "Structure": 100 * sum(s["found"] for s in sections) / len(sections),
        "Readability": _clamp(100 - abs(ease - 50) * 1.4),
        "Repetition": _clamp(100 - rep_frac * 150),
        "Keyword coverage": keyword_spread(paras),
        "Length balance": 100 * (0.6 * good_para + 0.4 * min(words / 1500, 1)),
        "Capitalization": cap_score,
        "Grammar": gram_score,
        "Citations": citation_report["score"],
    }
    overall = round(sum(scores[k] * w for k, w in WEIGHTS.items()))
    summary = summarize(paras)

    sugg = []
    for s in sections:
        if not s["found"]:
            sugg.append({"type": "rule", "text": f"Add a '{s['name']}' section; it was not detected."})
    if words < 1500:
        sugg.append({"type": "rule", "text": f"The document is short ({words} words). Most reports need more depth."})
    if asl > 25:
        sugg.append({"type": "rule", "text": f"Sentences are long on average ({asl:.0f} words). Split the longest ones."})
    if lens and sum(n > 200 for n in lens) / len(lens) > 0.2:
        sugg.append({"type": "rule", "text": "Many paragraphs exceed 200 words. Break them into smaller ones."})
    if len(headings) < 4:
        sugg.append({"type": "rule", "text": "Very few headings detected. Use clear headings to structure the document."})
    for r in repeats[:2]:
        sugg.append({"type": "rule", "text": f"{r['a']} and {r['b']} are {int(r['similarity']*100)}% similar. Merge or rewrite one."})

    if cap_total > 0:
        sugg.append({"type": "rule", "text": f"Found {cap_total} capitalization issue(s) (sentence starts, pronoun 'I', or ALL CAPS). Review the Capitalization panel."})
    if gram_total > 0:
        sugg.append({"type": "rule", "text": f"Found {gram_total} grammar/style issue(s) (articles, duplicated words, spacing, or contractions). Review the Grammar panel."})
    if citation_report["inlineCount"] == 0:
        sugg.append({"type": "rule", "text": "No inline citations (e.g., (Author, 2024) or [1]) were detected. Support claims with citations."})
    elif citation_report["unmatchedCitations"]:
        sugg.append({
            "type": "rule",
            "text": f"{len(citation_report['unmatchedCitations'])} inline citation(s) could not be matched in the References section: {', '.join(citation_report['unmatchedCitations'][:3])}.",
        })
    if citation_report["style"] == "Mixed (Author-Year + Numeric)":
        sugg.append({"type": "rule", "text": "Mixed citation styles detected (both Author-Year and Numeric). Stick to one consistent citation format."})

    return {
        "filename": filename,
        "wordCount": words,
        "pages": ex["pages"],
        "ocrUsed": bool(ex.get("ocr_used", False)),
        "score": overall,
        "breakdown": [{"label": k, "value": round(v)} for k, v in scores.items()],
        "summary": summary,
        "sections": sections,
        "repeats": repeats,
        "capitalization": {
            "score": cap_score,
            "totalIssues": cap_total,
            "issues": cap_issues,
        },
        "grammar": {
            "score": gram_score,
            "totalIssues": gram_total,
            "issues": gram_issues,
        },
        "citations": citation_report,
        "suggestions": sugg,
    }