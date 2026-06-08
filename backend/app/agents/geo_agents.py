"""All 8 GEO category agents.

Each class is a self-contained BaseAgent subclass; the orchestrator runs them concurrently.
"""
from __future__ import annotations  # Forward references for typing
import re  # Statistic/date pattern detection
import asyncio  # Concurrent citation checks
from app.agents.base import (  # Agent framework + every shared helper
    AgentContext,
    BaseAgent,
    scored,
    manual,
    not_measured,
    llm_scored,
    audit_numeric,
    audit_score,
    category_score,
    crux_metric,
    jsonld_types,
    type_present,
    block_mentions,
)
from app.models import Confidence, DetectionMethod, Priority, ParameterResult  # Enums + result


# ============================================================================
# answerability
# ============================================================================

class AnswerabilityAgent(BaseAgent):
    """Does the page answer the likely question directly and scannably?"""

    key = "answerability"  # Category key
    title = "Answerability"  # Display title
    kind = "geo"  # GEO report
    weight = 1.3  # Answerability is central to being cited by AI engines

    async def analyze(self, ctx: AgentContext) -> list[ParameterResult]:
        """Return all Answerability rows."""
        page = ctx.page  # Page signals shorthand
        gem = ctx.clients.gemini  # Gemini client
        results: list[ParameterResult] = []  # Accumulate rows

        # --- Concise top answer in the first 40-50 words (Gemini) ---
        intro = " ".join(page.visible_text.split()[:60])  # First ~60 words of the body
        results.append(
            await llm_scored(
                "Concise top answer",  # Parameter name
                "Direct answer in first 40-50 words",  # What to check
                gemini=gem,  # Gemini judges directness
                signal=f"Page title: {page.title}. Intro: {intro}. "
                "Does the opening directly answer the page's core question in ~40-50 words?",
                fallback_meeting=len(intro.split()) >= 30,  # Heuristic: a substantive intro exists
                fallback_detail=f"intro words={len(intro.split())}",  # Fallback evidence
                recommendation="Open with a direct, self-contained answer in the first 40-50 words.",
                priority=Priority.HIGH,
            )
        )

        # --- Question-phrased headings ---
        all_headings = [h for level in ("h2", "h3") for h in page.headings.get(level, [])]  # H2/H3 texts
        question_headings = [h for h in all_headings if self._is_question(h)]  # Question-style headings
        results.append(
            scored(
                "Question-phrased headings",  # Parameter name
                "H2/H3 as natural-language questions",  # What to check
                meeting=len(question_headings) >= 2,  # A couple of question headings
                partial=len(question_headings) == 1,  # One question heading
                method=DetectionMethod.CRAWL,  # Parsed headings
                detail=f"{len(question_headings)} of {len(all_headings)} H2/H3 are questions",  # Evidence
                recommendation="Phrase some H2/H3 headings as the natural-language questions users ask.",
                priority=Priority.MEDIUM,
            )
        )

        # --- FAQ section (FAQPage schema or visible Q&A) ---
        has_faq_schema = type_present(page, "FAQPage")  # FAQPage JSON-LD present?
        has_faq_text = "frequently asked questions" in page.visible_text.lower() or len(question_headings) >= 3
        results.append(
            scored(
                "FAQ section",  # Parameter name
                "Marked up with FAQPage schema; long-tail variants",  # What to check
                meeting=has_faq_schema,  # Best: schema-marked FAQ
                partial=has_faq_text,  # Visible FAQ without schema
                method=DetectionMethod.CRAWL,  # JSON-LD + content
                detail=f"FAQPage schema={has_faq_schema}, visible FAQ={has_faq_text}",  # Evidence
                recommendation="Add an FAQ section with FAQPage schema covering long-tail question variants.",
                priority=Priority.MEDIUM,
            )
        )

        # --- TL;DR / summary box (Gemini) ---
        lower = page.visible_text.lower()  # Lower-cased body
        has_tldr_marker = any(m in lower for m in ("tl;dr", "tldr", "in summary", "key takeaways", "summary:"))
        results.append(
            await llm_scored(
                "TL;DR / summary box",  # Parameter name
                "Scannable summary easy for AI to lift",  # What to check
                gemini=gem,  # Gemini judges presence of a liftable summary
                signal=f"First 1500 chars: {page.visible_text[:1500]}. "
                "Is there a scannable TL;DR/summary an AI could lift verbatim?",
                fallback_meeting=has_tldr_marker,  # Heuristic: explicit summary marker
                fallback_detail=f"summary marker present: {has_tldr_marker}",  # Fallback evidence
                recommendation="Add a short TL;DR/summary box near the top that AI engines can lift.",
                priority=Priority.MEDIUM,
            )
        )

        # --- Definition blocks ("X is ...") (Gemini) ---
        results.append(
            await llm_scored(
                "Definition blocks",  # Parameter name
                '"X is defined as..." near the top',  # What to check
                gemini=gem,  # Gemini judges definition presence
                signal=f"First 1200 chars: {page.visible_text[:1200]}. "
                "Is the key term clearly defined near the top (e.g. 'X is ...')?",
                fallback_meeting=" is " in page.visible_text[:400].lower(),  # Heuristic: a definition phrase
                fallback_detail="Heuristic: 'X is ...' pattern near the top.",  # Fallback evidence
                recommendation="Define the core term explicitly near the top of the page.",
                priority=Priority.LOW,
            )
        )

        # --- Step-by-step answers (ordered lists with action verbs) ---
        ordered_lists = page.soup.find_all("ol") if page.soup else []  # <ol> elements
        steps = max((len(ol.find_all("li")) for ol in ordered_lists), default=0)  # Longest step list
        results.append(
            scored(
                "Step-by-step answers",  # Parameter name
                "Numbered steps with clear action verbs",  # What to check
                meeting=steps >= 3,  # A real procedure has several steps
                partial=steps in (1, 2),  # A short list
                method=DetectionMethod.CRAWL,  # Parsed ordered lists
                detail=f"longest ordered list has {steps} items",  # Evidence
                recommendation="Use numbered (ol) steps with action verbs for how-to content.",
                priority=Priority.LOW,
                confidence=Confidence.MEDIUM,
            )
        )

        # --- Comparison answers (tables or "A vs B") ---
        has_table = bool(page.soup and page.soup.find("table"))  # A real table present?
        has_vs = " vs " in lower or " versus " in lower  # Comparative phrasing present?
        results.append(
            scored(
                "Comparison answers",  # Parameter name
                'Tables or "A vs B" sections for comparative queries',  # What to check
                meeting=has_table or has_vs,  # Either signal satisfies comparison readiness
                method=DetectionMethod.CRAWL,  # Detected comparison structures
                detail=f"table={has_table}, 'vs' phrasing={has_vs}",  # Evidence
                recommendation="Add comparison tables or 'A vs B' sections for comparative queries.",
                priority=Priority.LOW,
                confidence=Confidence.MEDIUM,
            )
        )

        return results  # All Answerability rows

    @staticmethod
    def _is_question(text: str) -> bool:
        """Return True if a heading reads like a natural-language question."""
        t = text.strip().lower()  # Normalise
        if t.endswith("?"):  # Ends with a question mark
            return True  # Clearly a question
        # Starts with a common interrogative word
        return t.split(" ")[0] in {"how", "what", "why", "when", "where", "who", "which", "can", "is", "are", "do"}

# ============================================================================
# extractability
# ============================================================================

class ExtractabilityAgent(BaseAgent):
    """Can an AI cleanly extract structured chunks from the markup?"""

    key = "extractability"  # Category key
    title = "Extractability"  # Display title
    kind = "geo"  # GEO report
    weight = 1.1  # Clean structure strongly affects extraction quality

    async def analyze(self, ctx: AgentContext) -> list[ParameterResult]:
        """Return all Extractability rows."""
        page = ctx.page  # Page signals shorthand
        soup = page.soup  # Parsed DOM
        gem = ctx.clients.gemini  # Gemini client
        results: list[ParameterResult] = []  # Accumulate rows

        # --- Semantic HTML (article/section/aside/figure vs div-soup) ---
        semantic_count = sum(len(soup.find_all(t)) for t in ("article", "section", "aside", "figure", "main", "nav")) if soup else 0
        div_count = len(soup.find_all("div")) if soup else 0  # Total <div>s (div-soup proxy)
        semantic_ratio = semantic_count / max(div_count, 1)  # Higher is better
        results.append(
            scored(
                "Semantic HTML",  # Parameter name
                "article/section/aside/figure used correctly; not div-soup",  # What to check
                meeting=semantic_count >= 3 and semantic_ratio >= 0.05,  # Real semantic structure
                partial=semantic_count >= 1,  # Some semantic elements
                method=DetectionMethod.CRAWL,  # Parsed DOM structure
                detail=f"semantic elements={semantic_count}, divs={div_count}",  # Evidence
                recommendation="Use semantic elements (article/section/figure) instead of nested divs.",
                priority=Priority.MEDIUM,
            )
        )

        # --- Chunkable paragraphs (short, single-idea paragraphs) ---
        para_lengths = [len(p.split()) for p in page.paragraphs if p.strip()]  # Words per paragraph
        short = [n for n in para_lengths if n <= 80]  # Paragraphs that are reasonably short
        share_short = (len(short) / len(para_lengths)) if para_lengths else 0.0  # Share of short paras
        results.append(
            scored(
                "Chunkable paragraphs",  # Parameter name
                "Short paragraphs (2-4 sentences); one idea each",  # What to check
                meeting=bool(para_lengths) and share_short >= 0.7,  # Mostly short paragraphs
                partial=bool(para_lengths) and share_short >= 0.4,  # Mixed
                method=DetectionMethod.CRAWL,  # From paragraph lengths
                detail=f"{len(short)}/{len(para_lengths)} paragraphs <= 80 words",  # Evidence
                recommendation="Break long paragraphs into short, single-idea chunks (2-4 sentences).",
                priority=Priority.MEDIUM,
            )
        )

        # --- Lists & tables (HTML, not image-based) ---
        list_count = len(soup.find_all(["ul", "ol"])) if soup else 0  # HTML lists
        table_count = len(soup.find_all("table")) if soup else 0  # HTML tables
        results.append(
            scored(
                "Lists & tables",  # Parameter name
                "HTML ul/ol/table (not image-based)",  # What to check
                meeting=(list_count + table_count) >= 1,  # At least one machine-readable structure
                method=DetectionMethod.CRAWL,  # Detected list/table elements
                detail=f"lists={list_count}, tables={table_count}",  # Evidence
                recommendation="Use real HTML lists/tables (not screenshots) so AI can parse them.",
                priority=Priority.LOW,
            )
        )

        # --- Heading-to-content ratio (each heading followed by content) ---
        heading_total = sum(len(v) for v in page.headings.values())  # Total headings
        # Healthy ratio: enough words per heading that sections are substantive
        words_per_heading = (page.word_count / heading_total) if heading_total else page.word_count
        results.append(
            scored(
                "Heading-to-content ratio",  # Parameter name
                "Each heading followed by substantive content",  # What to check
                meeting=heading_total >= 1 and 40 <= words_per_heading <= 400,  # Balanced sections
                partial=heading_total >= 1,  # Has headings but unbalanced
                method=DetectionMethod.CRAWL,  # Mapped headings to content
                detail=f"headings={heading_total}, words/heading={words_per_heading:.0f}",  # Evidence
                recommendation="Ensure each heading is followed by substantive (not empty) content.",
                priority=Priority.LOW,
                confidence=Confidence.MEDIUM,
            )
        )

        # --- Code blocks / data blocks (pre/code) ---
        code_count = len(soup.find_all(["pre", "code"])) if soup else 0  # Code/data blocks
        results.append(
            scored(
                "Code blocks / data blocks",  # Parameter name
                "pre/code tags; machine-readable tables",  # What to check
                meeting=code_count >= 1 or table_count >= 1,  # Has machine-readable blocks
                partial=True,  # Not all pages need code; absence is only a partial miss
                method=DetectionMethod.CRAWL,  # Detected code/data markup
                detail=f"pre/code blocks={code_count}",  # Evidence
                recommendation="Wrap code/data in <pre>/<code> and use real tables for datasets.",
                priority=Priority.LOW,
                confidence=Confidence.LOW,
            )
        )

        # --- No content locked in images/PDFs (Gemini + heuristic) ---
        img_to_text = (len(page.images) / max(page.word_count, 1))  # Images per word (high => image-heavy)
        results.append(
            await llm_scored(
                "No content in images/PDFs",  # Parameter name
                "Text not locked inside images/PDFs",  # What to check
                gemini=gem,  # Gemini judges whether key info is text vs image
                signal=f"Word count: {page.word_count}. Image count: {len(page.images)}. "
                f"Sample text: {page.visible_text[:800]}. "
                "Is the key information available as selectable text rather than locked in images/PDFs?",
                fallback_meeting=page.word_count >= 200 and img_to_text < 0.05,  # Mostly real text
                fallback_detail=f"words={page.word_count}, images={len(page.images)}",  # Fallback evidence
                recommendation="Provide important information as real text, not inside images or PDFs.",
                priority=Priority.MEDIUM,
            )
        )

        # --- Consistent terminology (Gemini) ---
        results.append(
            await llm_scored(
                "Consistent terminology",  # Parameter name
                "Same term used throughout; no synonym-switching",  # What to check
                gemini=gem,  # Gemini judges terminology consistency
                signal=f"Headings: {[h for v in page.headings.values() for h in v][:20]}. "
                f"Sample text: {page.visible_text[:1500]}. "
                "Is terminology consistent (no confusing synonym-switching for the same concept)?",
                fallback_meeting=True,  # Optimistic default when Gemini is unavailable
                fallback_detail="Heuristic default (Gemini unavailable).",  # Fallback evidence
                recommendation="Use one consistent term per concept throughout the page.",
                priority=Priority.LOW,
            )
        )

        return results  # All Extractability rows

# ============================================================================
# citability
# ============================================================================

import re  # Detect statistics and ISO dates


_STAT_RE = re.compile(r"\b\d+(\.\d+)?\s*(%|percent|million|billion|thousand|k\b)", re.IGNORECASE)  # Stats
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")  # ISO 8601 dates


class CitabilityAgent(BaseAgent):
    """Signals that make an AI engine trust and cite the page."""

    key = "citability"  # Category key
    title = "Citability & E-E-A-T"  # Display title
    kind = "geo"  # GEO report
    weight = 1.2  # Trust signals strongly influence citation

    async def analyze(self, ctx: AgentContext) -> list[ParameterResult]:
        """Return all Citability & E-E-A-T rows."""
        page = ctx.page  # Page signals shorthand
        gem = ctx.clients.gemini  # Gemini client
        lower = page.visible_text.lower()  # Lower-cased body text
        results: list[ParameterResult] = []  # Accumulate rows

        # --- Author + credentials (Gemini) ---
        results.append(
            await llm_scored(
                "Author + credentials",  # Parameter name
                "Named author, bio, qualifications visible",  # What to check
                gemini=gem,  # Gemini judges author signals
                signal=f"Text (first 2000 chars): {page.visible_text[:2000]}. "
                "Is there a named author with a bio and visible qualifications/credentials?",
                fallback_meeting=("author" in lower or "written by" in lower or "by " in lower[:200]),
                fallback_detail="Heuristic: author byline mention.",  # Fallback evidence
                recommendation="Add a named author with a bio and relevant credentials.",
                priority=Priority.MEDIUM,
            )
        )

        # --- Sources & citations (outbound links + references section) ---
        outbound = page.outbound_links  # External links
        has_refs = any(w in lower for w in ("references", "sources", "bibliography", "citation"))  # Refs?
        results.append(
            scored(
                "Sources & citations",  # Parameter name
                "Outbound links to primary sources; references section",  # What to check
                meeting=len(outbound) >= 3 or has_refs,  # Cites multiple sources / has a refs section
                partial=len(outbound) >= 1,  # Cites at least one source
                method=DetectionMethod.CRAWL,  # Parsed links + content
                detail=f"outbound links={len(outbound)}, references section={has_refs}",  # Evidence
                recommendation="Cite primary sources via outbound links and a references section.",
                priority=Priority.MEDIUM,
            )
        )

        # --- Statistics & data (detect + Gemini) ---
        stats = _STAT_RE.findall(page.visible_text)  # Quantitative claims found
        results.append(
            await llm_scored(
                "Statistics & data",  # Parameter name
                "Quantitative claims with source attribution",  # What to check
                gemini=gem,  # Gemini judges whether stats are attributed
                signal=f"Outbound link count: {len(outbound)}. Sample text: {page.visible_text[:1500]}. "
                "Are quantitative claims (stats/data) present and attributed to sources?",
                fallback_meeting=len(stats) >= 2 and len(outbound) >= 1,  # Has stats + a source
                fallback_detail=f"{len(stats)} stat-like tokens, {len(outbound)} outbound links",  # Evidence
                recommendation="Back quantitative claims with cited, linked sources.",
                priority=Priority.LOW,
            )
        )

        # --- Publish + updated dates (HTML + Article schema) ---
        has_iso = bool(_ISO_DATE_RE.search(page.html))  # ISO date in markup?
        has_dates_schema = block_mentions(page, "datePublished") or block_mentions(page, "dateModified")
        results.append(
            scored(
                "Publish + updated dates",  # Parameter name
                "ISO 8601 dates in HTML + Article schema",  # What to check
                meeting=has_iso and has_dates_schema,  # Both visible + schema dates
                partial=has_iso or has_dates_schema,  # One of the two
                method=DetectionMethod.CRAWL,  # Parsed dates + JSON-LD
                detail=f"iso date={has_iso}, schema dates={has_dates_schema}",  # Evidence
                recommendation="Expose ISO 8601 datePublished/dateModified in HTML and Article schema.",
                priority=Priority.MEDIUM,
            )
        )

        # --- About / Trust pages (internal links to about/contact/privacy) ---
        link_urls = " ".join(l.url.lower() for l in page.internal_links)  # All internal link URLs
        trust_hits = sum(slug in link_urls for slug in ("about", "contact", "privacy"))  # Trust pages linked
        results.append(
            scored(
                "About / Trust pages",  # Parameter name
                "About, Contact, Privacy pages present",  # What to check
                meeting=trust_hits >= 3,  # All three linked
                partial=trust_hits >= 1,  # At least one
                method=DetectionMethod.CRAWL,  # Detected from internal links
                detail=f"trust-page links found: {trust_hits}/3",  # Evidence
                recommendation="Link to About, Contact and Privacy pages from the site.",
                priority=Priority.LOW,
            )
        )

        # --- Expert review signals ("reviewed by"/"fact-checked by") ---
        review_markers = ("medically reviewed", "fact-checked", "fact checked", "reviewed by", "expert reviewed")
        has_review = any(m in lower for m in review_markers)  # Review label present?
        results.append(
            scored(
                "Expert review signals",  # Parameter name
                '"Medically reviewed by..."/"Fact-checked by..." labels',  # What to check
                meeting=has_review,  # Review label present
                partial=True,  # Not all content needs review labels; absence is a soft miss
                method=DetectionMethod.CRAWL,  # Pattern detection
                detail=f"review label present: {has_review}",  # Evidence
                recommendation='Add "Reviewed by"/"Fact-checked by" labels for YMYL content.',
                priority=Priority.LOW,
                confidence=Confidence.MEDIUM,
            )
        )

        # --- Wikidata / Wikipedia entity (external) ---
        results.append(await self._entity_row(ctx))  # Delegate to a helper (Wikidata + Wikipedia)

        # --- Press mentions & awards (on-page + Serper) ---
        results.append(await self._press_row(ctx, lower))  # Delegate (Serper web search)

        # --- Disclaimer / methodology (Gemini) ---
        has_method = any(w in lower for w in ("methodology", "how we", "our process", "disclaimer"))  # Markers
        results.append(
            await llm_scored(
                "Disclaimer / methodology",  # Parameter name
                "Methodology explained for research/data content",  # What to check
                gemini=gem,  # Gemini judges methodology presence
                signal=f"Sample text: {page.visible_text[:1500]}. "
                "For research/data content, is the methodology or a disclaimer explained?",
                fallback_meeting=has_method,  # Heuristic: methodology markers
                fallback_detail=f"methodology markers present: {has_method}",  # Fallback evidence
                recommendation="Explain methodology (or add a disclaimer) for research/data content.",
                priority=Priority.LOW,
            )
        )

        return results  # All Citability rows

    async def _entity_row(self, ctx: AgentContext) -> ParameterResult:
        """Check Wikidata + Wikipedia for the brand/organisation entity."""
        # Derive a brand name from Organization schema, then OG site name, then the host
        brand = self._brand_name(ctx.page)  # Best-effort brand name
        if not brand:  # No usable brand name
            return not_measured(
                "Wikidata / Wikipedia entity", "Organisation/person entity exists",
                DetectionMethod.EXTERNAL, "Could not determine a brand/entity name from the page.",
            )
        # Query both sources (they need no API key)
        in_wikidata = await ctx.clients.wikidata.entity_exists(brand)  # Wikidata match?
        in_wikipedia = await ctx.clients.wikidata.wikipedia_exists(brand)  # Wikipedia article?
        return scored(
            "Wikidata / Wikipedia entity",  # Parameter name
            "Organisation/person entity exists",  # What to check
            meeting=in_wikidata or in_wikipedia,  # Present in either source
            method=DetectionMethod.EXTERNAL,  # Via Wikidata/Wikipedia
            detail=f"brand='{brand}', wikidata={in_wikidata}, wikipedia={in_wikipedia}",  # Evidence
            recommendation="Establish a Wikidata item / Wikipedia presence for the organisation.",
            priority=Priority.LOW,
            confidence=Confidence.HIGH,
        )

    async def _press_row(self, ctx: AgentContext, lower: str) -> ParameterResult:
        """Detect press mentions/awards on-page and via a Serper web search."""
        on_page = any(m in lower for m in ("featured in", "as seen on", "award", "winner"))  # On-page markers
        brand = self._brand_name(ctx.page)  # Brand name for the search query
        external_hits = 0  # Number of press results found via Serper
        if ctx.clients.serper.enabled and brand:  # Only search when Serper is available
            results = await ctx.clients.serper.search(f'"{brand}" press OR featured OR award', num=10)  # Search
            external_hits = len(results)  # Count results as a weak signal
        return scored(
            "Press mentions & awards",  # Parameter name
            "Featured-in logos and award badges",  # What to check
            meeting=on_page or external_hits >= 3,  # On-page badges or several external mentions
            partial=external_hits >= 1,  # At least one external mention
            method=DetectionMethod.EXTERNAL,  # On-page + Serper
            detail=f"on_page_markers={on_page}, serper_hits={external_hits}",  # Evidence
            recommendation="Showcase press mentions and awards (with badges) and earn external coverage.",
            priority=Priority.LOW,
            confidence=Confidence.MEDIUM,
        )

    @staticmethod
    def _brand_name(page) -> str:
        """Best-effort brand/organisation name from schema, OG tags or the host."""
        for block in page.jsonld:  # Prefer an explicit Organization name
            t = block.get("@type")  # Block type(s)
            if (t == "Organization" or (isinstance(t, list) and "Organization" in t)) and block.get("name"):
                return str(block["name"])  # Schema-declared name
        if page.meta_tags.get("og:site_name"):  # Fall back to OpenGraph site name
            return page.meta_tags["og:site_name"]  # OG site name
        host = page.host.removeprefix("www.")  # Otherwise derive from the host
        return host.split(".")[0].capitalize() if host else ""  # First label of the domain

# ============================================================================
# ai structured data
# ============================================================================

class AiStructuredDataAgent(BaseAgent):
    """Schema types that help AI engines parse and trust the page."""

    key = "ai_structured_data"  # Category key
    title = "AI Structured Data"  # Display title
    kind = "geo"  # GEO report
    weight = 1.0  # Standard weight

    async def analyze(self, ctx: AgentContext) -> list[ParameterResult]:
        """Return all AI Structured Data rows."""
        page = ctx.page  # Page signals shorthand
        results: list[ParameterResult] = []  # Accumulate rows

        # Organization is broadly expected; its absence is a real miss (Not Meeting)
        results.append(self._schema_row(
            page, "Organization schema", "name, url, logo, sameAs (socials, Wikidata)",
            "Organization", required=True, recommendation="Add Organization JSON-LD with name/url/logo/sameAs.",
            priority=Priority.MEDIUM,
        ))

        # Article is expected for content pages; treat absence as a soft miss (Partial)
        results.append(self._schema_row(
            page, "Article schema", "headline, author, datePublished, dateModified, publisher",
            "Article", required=False, recommendation="Add Article JSON-LD (headline, author, dates, publisher).",
            priority=Priority.MEDIUM,
        ))

        # The remaining schema types are content-type specific: absence => Partial, not failure
        results.append(self._schema_row(
            page, "FAQPage schema", "Q&A pairs in JSON-LD", "FAQPage", required=False,
            recommendation="Add FAQPage JSON-LD for question/answer content.", priority=Priority.LOW,
        ))
        results.append(self._schema_row(
            page, "HowTo schema", "Steps with name, text, image", "HowTo", required=False,
            recommendation="Add HowTo JSON-LD for step-by-step content.", priority=Priority.LOW,
        ))
        results.append(self._schema_row(
            page, "Product / Offer schema", "name, description, price, availability, aggregateRating",
            "Product", required=False, recommendation="Add Product/Offer JSON-LD for product pages.",
            priority=Priority.LOW,
        ))
        results.append(self._schema_row(
            page, "Dataset schema", "For research/data pages", "Dataset", required=False,
            recommendation="Add Dataset JSON-LD for research/data pages.", priority=Priority.LOW,
        ))
        results.append(self._schema_row(
            page, "Event schema", "For time-bound content", "Event", required=False,
            recommendation="Add Event JSON-LD for time-bound content.", priority=Priority.LOW,
        ))
        results.append(self._schema_row(
            page, "ClaimReview schema", "Fact-check pages", "ClaimReview", required=False,
            recommendation="Add ClaimReview JSON-LD for fact-check content.", priority=Priority.LOW,
        ))

        # SpeakableSpecification is detected by mention (it is nested, not a top-level @type)
        speakable = block_mentions(page, "speakable") or block_mentions(page, "SpeakableSpecification")
        results.append(
            scored(
                "SpeakableSpecification",  # Parameter name
                "Important passages marked for voice/AI",  # What to check
                meeting=speakable,  # Speakable markup present
                partial=True,  # Optional; absence is only a soft miss
                method=DetectionMethod.CRAWL,  # Parsed JSON-LD
                detail=f"speakable present: {speakable}",  # Evidence
                recommendation="Mark key passages with SpeakableSpecification for voice/AI surfaces.",
                priority=Priority.LOW,
                confidence=Confidence.MEDIUM,
            )
        )

        return results  # All AI Structured Data rows

    @staticmethod
    def _schema_row(
        page,
        name: str,
        what: str,
        type_name: str,
        *,
        required: bool,
        recommendation: str,
        priority: Priority,
    ) -> ParameterResult:
        """Build a row for a single schema type's presence.

        `required=True` => absence is Not Meeting; otherwise absence is Partial
        (the schema only applies to certain content types).
        """
        present = type_present(page, type_name)  # Is the @type present?
        return scored(
            name,
            what,
            meeting=present,  # Meeting when the schema exists
            partial=(not present) and (not required),  # Optional schema absent => Partial
            method=DetectionMethod.CRAWL,  # Parsed JSON-LD
            detail=f"{type_name} schema present: {present}",  # Evidence
            recommendation=recommendation,  # Concrete fix
            priority=priority,  # Fix priority
            confidence=Confidence.HIGH,  # Deterministic schema detection
        )

# ============================================================================
# entity clarity
# ============================================================================

class EntityClarityAgent(BaseAgent):
    """Are the page's entities clearly defined, marked up and disambiguated?"""

    key = "entity_clarity"  # Category key
    title = "Entity Clarity"  # Display title
    kind = "geo"  # GEO report
    weight = 0.9  # Slightly lower weight

    async def analyze(self, ctx: AgentContext) -> list[ParameterResult]:
        """Return all Entity Clarity rows."""
        page = ctx.page  # Page signals shorthand
        gem = ctx.clients.gemini  # Gemini client
        lower = page.visible_text.lower()  # Lower-cased body
        results: list[ParameterResult] = []  # Accumulate rows

        # --- In-text definitions (Gemini) ---
        results.append(
            await llm_scored(
                "In-text definitions",  # Parameter name
                "First use of technical terms defined inline / linked",  # What to check
                gemini=gem,  # Gemini judges inline definitions
                signal=f"Sample text: {page.visible_text[:1500]}. "
                "Are technical terms defined inline (or linked) on first use?",
                fallback_meeting=any(p in lower for p in (" is a ", " refers to ", " means ")),  # Heuristic
                fallback_detail="Heuristic: definition phrases present.",  # Fallback evidence
                recommendation="Define technical terms inline (or link them) on first use.",
                priority=Priority.LOW,
            )
        )

        # --- Glossary page (internal link to a glossary) ---
        has_glossary = any(  # Look for a glossary/definitions page in internal links
            any(s in l.url.lower() or s in l.anchor.lower() for s in ("glossary", "definitions"))
            for l in page.internal_links
        )
        results.append(
            scored(
                "Glossary page",  # Parameter name
                "Dedicated glossary with anchor links",  # What to check
                meeting=has_glossary,  # Glossary linked
                partial=True,  # Optional; absence is a soft miss
                method=DetectionMethod.CRAWL,  # Detected glossary link
                detail=f"glossary link present: {has_glossary}",  # Evidence
                recommendation="Add a glossary page with anchor-linked term definitions.",
                priority=Priority.LOW,
                confidence=Confidence.MEDIUM,
            )
        )

        # --- Named entities marked up (sameAs in JSON-LD) ---
        has_sameas = block_mentions(page, "sameAs")  # sameAs links to authoritative URIs?
        results.append(
            scored(
                "Named entities marked up",  # Parameter name
                "People/places/orgs in schema with sameAs to authoritative URIs",  # What to check
                meeting=has_sameas,  # sameAs present
                method=DetectionMethod.CRAWL,  # Parsed JSON-LD sameAs
                detail=f"sameAs present: {has_sameas}",  # Evidence
                recommendation="Mark up entities with sameAs links to Wikidata/Wikipedia/socials.",
                priority=Priority.MEDIUM,
            )
        )

        # --- Disambiguation (Gemini) ---
        results.append(
            await llm_scored(
                "Disambiguation",  # Parameter name
                "Clarify ambiguous terms near first use",  # What to check
                gemini=gem,  # Gemini judges ambiguity
                signal=f"Title: {page.title}. Sample text: {page.visible_text[:1200]}. "
                "Are potentially ambiguous terms/brand names disambiguated near first use?",
                fallback_meeting=True,  # Optimistic default when Gemini is unavailable
                fallback_detail="Heuristic default (Gemini unavailable).",  # Fallback evidence
                recommendation="Disambiguate ambiguous terms/brands near their first use.",
                priority=Priority.LOW,
            )
        )

        # --- Knowledge panel consistency (Google Knowledge Graph) ---
        results.append(await self._knowledge_panel_row(ctx))  # Delegate (KG lookup)

        # --- Entity co-occurrence (Gemini) ---
        results.append(
            await llm_scored(
                "Entity co-occurrence",  # Parameter name
                "Mention related authoritative entities",  # What to check
                gemini=gem,  # Gemini judges related-entity coverage
                signal=f"Title: {page.title}. Headings: {[h for v in page.headings.values() for h in v][:15]}. "
                "Does the page mention related authoritative entities a knowledgeable source would?",
                fallback_meeting=page.word_count >= 400,  # Heuristic: enough content to cover entities
                fallback_detail=f"word count={page.word_count}",  # Fallback evidence
                recommendation="Mention related authoritative entities to strengthen topical context.",
                priority=Priority.LOW,
            )
        )

        return results  # All Entity Clarity rows

    async def _knowledge_panel_row(self, ctx: AgentContext) -> ParameterResult:
        """Compare the brand to its Google Knowledge Graph entity (when available)."""
        if not ctx.clients.knowledge_graph.enabled:  # No GOOGLE_API_KEY
            return not_measured(
                "Knowledge panel consistency", "Brand name/description/logo match Knowledge Panel",
                DetectionMethod.EXTERNAL, "Google Knowledge Graph unavailable (no GOOGLE_API_KEY).",
            )
        brand = self._brand_name(ctx.page)  # Derive a brand name
        if not brand:  # No brand to look up
            return not_measured(
                "Knowledge panel consistency", "Brand name/description/logo match Knowledge Panel",
                DetectionMethod.EXTERNAL, "Could not determine a brand name from the page.",
            )
        entity = await ctx.clients.knowledge_graph.lookup(brand)  # KG entity for the brand
        found = bool(entity)  # Whether an entity exists
        return scored(
            "Knowledge panel consistency",  # Parameter name
            "Brand name/description/logo match Knowledge Panel",  # What to check
            meeting=found,  # Meeting when a KG entity exists
            partial=True,  # Soft miss when absent (small brands may have none)
            method=DetectionMethod.EXTERNAL,  # Via Knowledge Graph
            detail=f"brand='{brand}', KG entity found: {found}",  # Evidence
            recommendation="Build a consistent entity (name/description/logo) recognised by the Knowledge Graph.",
            priority=Priority.LOW,
            confidence=Confidence.MEDIUM,
        )

    @staticmethod
    def _brand_name(page) -> str:
        """Derive a brand name from Organization schema, OG site name, or host."""
        for block in page.jsonld:  # Prefer an explicit Organization name
            t = block.get("@type")  # Block type(s)
            if (t == "Organization" or (isinstance(t, list) and "Organization" in t)) and block.get("name"):
                return str(block["name"])  # Schema name
        if page.meta_tags.get("og:site_name"):  # Then OG site name
            return page.meta_tags["og:site_name"]  # OG name
        host = page.host.removeprefix("www.")  # Else the domain
        return host.split(".")[0].capitalize() if host else ""  # First label

# ============================================================================
# ai bot crawlability
# ============================================================================

class AiBotCrawlabilityAgent(BaseAgent):
    """Can AI crawlers access the site (robots directives + llms.txt files)?"""

    key = "ai_bot_crawlability"  # Category key
    title = "AI-Bot Crawlability"  # Display title
    kind = "geo"  # GEO report
    weight = 1.0  # Standard weight

    async def analyze(self, ctx: AgentContext) -> list[ParameterResult]:
        """Return all AI-Bot Crawlability rows."""
        page = ctx.page  # Page signals shorthand
        # Pre-parse robots.txt into a directive map for fast per-agent checks
        groups = self._parse_robots(page.robots_txt)  # user-agent -> set of disallow paths
        results: list[ParameterResult] = []  # Accumulate rows

        # --- Major AI assistants: GPTBot / ClaudeBot / PerplexityBot ---
        blocked_major = [b for b in ("GPTBot", "ClaudeBot", "PerplexityBot") if self._blocked(groups, b)]
        results.append(
            scored(
                "GPTBot / ClaudeBot / PerplexityBot",  # Parameter name
                "Explicit allow/disallow in robots.txt",  # What to check
                meeting=len(blocked_major) == 0,  # None of the major AI bots are blocked
                partial=len(blocked_major) < 3,  # Some allowed
                method=DetectionMethod.CRAWL,  # Parsed robots.txt
                detail=f"blocked: {blocked_major or 'none'}",  # Evidence
                recommendation="Allow GPTBot/ClaudeBot/PerplexityBot in robots.txt if you want AI citations.",
                priority=Priority.MEDIUM,
            )
        )

        # --- Google-Extended (controls AI Overviews training) ---
        results.append(self._bot_row(
            groups, "Google-Extended", "Google-Extended",
            "Controls AI Overviews training data",
            "Allow Google-Extended to permit use in AI Overviews (or block intentionally).",
        ))

        # --- llms.txt ---
        results.append(
            scored(
                "llms.txt",  # Parameter name
                "Machine-readable site summary for LLMs",  # What to check
                meeting=page.llms_txt_exists,  # /llms.txt present
                method=DetectionMethod.CRAWL,  # Fetched /llms.txt
                detail=f"/llms.txt exists: {page.llms_txt_exists}",  # Evidence
                recommendation="Publish an /llms.txt summarising your site for LLMs.",
                priority=Priority.LOW,
            )
        )

        # --- CCBot (Common Crawl) ---
        results.append(self._bot_row(
            groups, "CCBot", "CCBot", "Explicit allow/disallow",
            "Decide explicitly whether to allow CCBot (Common Crawl) in robots.txt.",
        ))

        # --- Applebot-Extended ---
        results.append(self._bot_row(
            groups, "Applebot-Extended", "Applebot-Extended", "Apple Intelligence crawler directive",
            "Set an explicit Applebot-Extended directive in robots.txt.",
        ))

        # --- Meta AI crawlers (meta-externalagent) ---
        results.append(self._bot_row(
            groups, "meta-externalagent", "meta-externalagent", "Meta AI training/retrieval directive",
            "Set an explicit meta-externalagent directive in robots.txt.",
        ))

        # --- Crawl rate limits (Crawl-delay should not throttle AI bots) ---
        crawl_delay = self._max_crawl_delay(page.robots_txt)  # Largest Crawl-delay declared
        results.append(
            scored(
                "Crawl rate limits",  # Parameter name
                "AI bots not throttled to stale content",  # What to check
                meeting=crawl_delay <= 5,  # Small/none is fine
                partial=5 < crawl_delay <= 30,  # Moderate throttling
                method=DetectionMethod.CRAWL,  # Parsed Crawl-delay
                detail=f"max Crawl-delay={crawl_delay}s",  # Evidence
                recommendation="Avoid large Crawl-delay values that throttle AI crawlers to stale content.",
                priority=Priority.LOW,
                confidence=Confidence.MEDIUM,
            )
        )

        # --- llms-full.txt ---
        results.append(
            scored(
                "llms-full.txt",  # Parameter name
                "Extended page-level metadata file",  # What to check
                meeting=page.llms_full_txt_exists,  # /llms-full.txt present
                partial=True,  # Optional; absence is a soft miss
                method=DetectionMethod.CRAWL,  # Fetched /llms-full.txt
                detail=f"/llms-full.txt exists: {page.llms_full_txt_exists}",  # Evidence
                recommendation="Optionally publish /llms-full.txt with extended page-level metadata.",
                priority=Priority.LOW,
            )
        )

        return results  # All AI-Bot Crawlability rows

    def _bot_row(self, groups, name, user_agent, what, recommendation) -> ParameterResult:
        """Build a row indicating whether `user_agent` is allowed (not blocked)."""
        blocked = self._blocked(groups, user_agent)  # Is this UA disallowed from /?
        return scored(
            name, what,
            meeting=not blocked,  # Meeting when the bot is not blocked
            method=DetectionMethod.CRAWL,  # Parsed robots.txt
            detail=f"{user_agent} blocked: {blocked}",  # Evidence
            recommendation=recommendation,  # Concrete fix
            priority=Priority.LOW,
            confidence=Confidence.MEDIUM,
        )

    @staticmethod
    def _parse_robots(robots_txt: str) -> dict[str, list[str]]:
        """Parse robots.txt into {user-agent(lower): [disallow paths]}."""
        groups: dict[str, list[str]] = {}  # Result map
        current: list[str] = []  # User-agents the current block applies to
        for raw in robots_txt.splitlines():  # Scan each line
            line = raw.split("#", 1)[0].strip()  # Strip comments + whitespace
            if not line:  # Blank line ends a block grouping (loosely)
                continue  # Skip blanks
            key, _, value = line.partition(":")  # Split "Field: value"
            key = key.strip().lower()  # Normalise the field name
            value = value.strip()  # Trim the value
            if key == "user-agent":  # Start/extend a user-agent group
                current = [value.lower()]  # Track the agent this block targets
                groups.setdefault(value.lower(), [])  # Ensure an entry exists
            elif key == "disallow" and current:  # Disallow within the active group(s)
                for ua in current:  # Apply to each tracked agent
                    groups.setdefault(ua, []).append(value)  # Record the disallow path
        return groups  # Parsed directive map

    @staticmethod
    def _blocked(groups: dict[str, list[str]], user_agent: str) -> bool:
        """Return True if `user_agent` (or *) is disallowed from the site root."""
        ua = user_agent.lower()  # Normalise the agent name
        # Specific agent rules take precedence over the wildcard group
        rules = groups.get(ua)  # Agent-specific disallow paths
        if rules is None:  # No specific block => inherit the wildcard group
            rules = groups.get("*", [])  # Fall back to "User-agent: *"
        return any(path == "/" for path in rules)  # Blocked when Disallow: / is present

    @staticmethod
    def _max_crawl_delay(robots_txt: str) -> float:
        """Return the largest Crawl-delay value declared in robots.txt (0 if none)."""
        max_delay = 0.0  # Track the maximum
        for raw in robots_txt.splitlines():  # Scan lines
            line = raw.split("#", 1)[0].strip().lower()  # Normalise
            if line.startswith("crawl-delay:"):  # Crawl-delay directive
                try:  # Value may be non-numeric
                    max_delay = max(max_delay, float(line.split(":", 1)[1].strip()))  # Update max
                except ValueError:  # Ignore malformed values
                    continue  # Skip
        return max_delay  # Largest declared delay

# ============================================================================
# ai quality
# ============================================================================

import asyncio  # Run the independent citation checks concurrently



class AiQualityAgent(BaseAgent):
    """Gemini-judged quality plus live AI-engine citation appearance checks."""

    key = "ai_quality"  # Category key
    title = "AI Quality Scores"  # Display title
    kind = "geo"  # GEO report
    weight = 1.2  # These map most directly to "will an AI cite this?"

    def __init__(self) -> None:
        """Initialise the per-run citation panel."""
        self._panel: dict = {}  # Filled during analyze(); read by the orchestrator

    async def analyze(self, ctx: AgentContext) -> list[ParameterResult]:
        """Return all AI Quality rows and populate the GEO citation panel."""
        page = ctx.page  # Page signals shorthand
        gem = ctx.clients.gemini  # Gemini client
        text_sample = page.visible_text[:2500]  # Bounded text sample for judgement prompts
        results: list[ParameterResult] = []  # Accumulate rows

        # --- Clarity score (Gemini) ---
        results.append(await llm_scored(
            "Clarity score", "Writing unambiguous and scannable?", gemini=gem,
            signal=f"Sample: {text_sample}. Is the writing unambiguous and scannable?",
            fallback_meeting=page.word_count >= 200, fallback_detail="Heuristic on length.",
            recommendation="Tighten writing: shorter sentences, clear structure, scannable formatting.",
            priority=Priority.MEDIUM,
        ))

        # --- Authority score (Gemini) ---
        results.append(await llm_scored(
            "Authority score", "Expertise, credentials, sourcing signaled?", gemini=gem,
            signal=f"Sample: {text_sample}. Are expertise, credentials and sourcing clearly signalled?",
            fallback_meeting=len(page.outbound_links) >= 2, fallback_detail="Heuristic on outbound links.",
            recommendation="Signal expertise: author credentials, citations and authoritative sources.",
            priority=Priority.MEDIUM,
        ))

        # --- Comprehensiveness (Gemini) ---
        results.append(await llm_scored(
            "Comprehensiveness", "Covers topic fully enough to be self-sufficient?", gemini=gem,
            signal=f"Title: {page.title}. Headings: {[h for v in page.headings.values() for h in v][:15]}. "
            f"Sample: {text_sample}. Does the page cover the topic fully enough to be self-sufficient?",
            fallback_meeting=page.word_count >= 800, fallback_detail="Heuristic on length.",
            recommendation="Cover the full topic so the page can answer a query without other sources.",
            priority=Priority.MEDIUM,
        ))

        # --- Citation likelihood (Gemini) ---
        results.append(await llm_scored(
            "Citation likelihood", "Would an AI engine prefer this source?", gemini=gem,
            signal=f"Title: {page.title}. Sample: {text_sample}. "
            "Would an AI engine prefer to cite this source over typical alternatives?",
            fallback_meeting=page.word_count >= 600 and len(page.outbound_links) >= 2,
            fallback_detail="Heuristic on depth + sourcing.",
            recommendation="Increase citation appeal: original data, clarity, sourcing and structure.",
            priority=Priority.MEDIUM,
        ))

        # --- Sample-query self-sufficiency test (Gemini) ---
        results.append(await llm_scored(
            "Sample-query self-sufficiency test", "Ask 5-10 likely queries; does page alone answer each?",
            gemini=gem,
            signal=f"Title: {page.title}. Sample: {text_sample}. "
            "Imagine 5-10 likely user queries for this page; does the page alone answer most of them?",
            fallback_meeting=page.word_count >= 600, fallback_detail="Heuristic on length.",
            recommendation="Ensure the page answers the common queries it targets, without external pages.",
            priority=Priority.MEDIUM,
        ))

        # --- AI Overview appearance monitoring (SerpApi + Perplexity + OpenAI) ---
        results.append(await self._citation_row(ctx))  # Delegate; also fills the panel

        # --- Hallucination surface area (Gemini) ---
        results.append(await llm_scored(
            "Hallucination surface area", "Reduce ambiguous claims AI might misattribute", gemini=gem,
            signal=f"Sample: {text_sample}. "
            "Are claims specific and well-scoped (low risk of AI misattribution/hallucination)?",
            fallback_meeting=True, fallback_detail="Heuristic default (Gemini unavailable).",
            recommendation="Make claims specific and well-scoped to reduce AI misattribution risk.",
            priority=Priority.LOW,
        ))

        # --- Prompt-align test (Gemini summary simulation) ---
        results.append(await llm_scored(
            "Prompt-align test", "Simulate LLM summary; accurate and favourable?", gemini=gem,
            signal=f"Title: {page.title}. Sample: {text_sample}. "
            "If an LLM summarised this page, would the summary be accurate and favourable to the brand?",
            fallback_meeting=True, fallback_detail="Heuristic default (Gemini unavailable).",
            recommendation="Structure content so an LLM summary is accurate and favourable.",
            priority=Priority.LOW,
        ))

        # --- Competing source gap analysis (SerpApi + Perplexity) ---
        results.append(await self._gap_row(ctx))  # Delegate; uses the panel's citation lists

        return results  # All AI Quality rows

    async def _citation_row(self, ctx: AgentContext) -> ParameterResult:
        """Check whether the domain is cited by Perplexity / Google AI Overview / ChatGPT."""
        page = ctx.page  # Page signals shorthand
        host = page.host.removeprefix("www.")  # Bare host for matching
        query = page.title or host  # Use the page title as the representative query
        if not host:  # No host means nothing to check
            return not_measured(
                "AI Overview appearance monitoring", "Cited in Google AI Overviews / SearchGPT / Perplexity?",
                DetectionMethod.EXTERNAL, "No host available to check.",
            )

        # Run the three engine checks concurrently (each degrades to None/empty)
        pplx_cites, serp_cites, openai_mentions = await asyncio.gather(
            ctx.clients.perplexity.citations(query) if ctx.clients.perplexity.enabled else _empty_list(),
            ctx.clients.serpapi.ai_overview_sources(query) if ctx.clients.serpapi.enabled else _empty_list(),
            ctx.clients.openai.mentions_domain(query, host) if ctx.clients.openai.enabled else _none(),
        )

        # Determine which engines cite this domain
        in_pplx = any(host in (u or "") for u in pplx_cites)  # Perplexity cites the host?
        in_serp = any(host in (u or "") for u in serp_cites)  # AI Overview cites the host?
        in_openai = bool(openai_mentions)  # ChatGPT references the host?
        engines = [name for name, hit in (("Perplexity", in_pplx), ("Google AI Overview", in_serp), ("ChatGPT", in_openai)) if hit]

        # Record the panel data the GEO report renders (engines + competitor citations)
        self._panel = {
            "query": query,  # Representative query used
            "cited_by": engines,  # Engines that cite the domain
            "perplexity_sources": pplx_cites[:10],  # Top Perplexity sources
            "ai_overview_sources": serp_cites[:10],  # Top AI Overview sources
            "chatgpt_mentions": openai_mentions,  # None when unavailable
        }

        any_enabled = ctx.clients.perplexity.enabled or ctx.clients.serpapi.enabled or ctx.clients.openai.enabled
        if not any_enabled:  # No citation engine configured
            return not_measured(
                "AI Overview appearance monitoring", "Cited in Google AI Overviews / SearchGPT / Perplexity?",
                DetectionMethod.EXTERNAL, "No citation engines available (missing API keys).",
            )
        return scored(
            "AI Overview appearance monitoring",  # Parameter name
            "Cited in Google AI Overviews / SearchGPT / Perplexity?",  # What to check
            meeting=len(engines) >= 1,  # Cited by at least one engine
            method=DetectionMethod.EXTERNAL,  # Live citation checks
            detail=f"cited by: {engines or 'none'} for query '{query[:60]}'",  # Evidence
            recommendation="Improve answerability/authority so AI engines cite the page for its queries.",
            priority=Priority.MEDIUM,
            confidence=Confidence.MEDIUM,
            evidence=self._panel,  # Attach panel data to the row too
        )

    async def _gap_row(self, ctx: AgentContext) -> ParameterResult:
        """Diff the AI citation lists against the target domain to find competitor gaps."""
        host = ctx.page.host.removeprefix("www.")  # Target host
        sources = (self._panel.get("perplexity_sources", []) + self._panel.get("ai_overview_sources", []))
        if not sources:  # No citation lists were obtained
            return not_measured(
                "Competing source gap analysis", "Which sources AI cites for key queries that you lack",
                DetectionMethod.EXTERNAL, "No citation lists available (missing keys/results).",
            )
        # Competitor domains are the cited sources that are not the target domain
        competitors = sorted({self._domain_of(u) for u in sources if host not in (u or "")} - {""})
        cited = any(host in (u or "") for u in sources)  # Is the target itself cited?
        return scored(
            "Competing source gap analysis",  # Parameter name
            "Which sources AI cites for key queries that you lack",  # What to check
            meeting=cited,  # Meeting when the target is among the cited sources
            partial=len(competitors) > 0,  # We at least identified competitor sources
            method=DetectionMethod.EXTERNAL,  # Derived from citation diffs
            detail=f"target cited: {cited}; competitors cited: {competitors[:8]}",  # Evidence
            recommendation="Close the gap vs cited competitor sources (coverage, data, authority).",
            priority=Priority.MEDIUM,
            confidence=Confidence.MEDIUM,
            evidence={"competitors": competitors[:10], "target_cited": cited},  # UI data
        )

    @staticmethod
    def _domain_of(url: str) -> str:
        """Return the bare host of a URL ("" when unparseable)."""
        from urllib.parse import urlparse  # Local import for a tiny helper

        try:  # Parsing arbitrary citation URLs can fail
            return urlparse(url).netloc.lower().removeprefix("www.")  # Bare host
        except Exception:  # Unparseable URL
            return ""  # Treat as unknown


async def _empty_list() -> list:
    """Awaitable that yields an empty list (placeholder for disabled clients)."""
    return []  # Used so asyncio.gather always receives awaitables


async def _none():
    """Awaitable that yields None (placeholder for the disabled OpenAI client)."""
    return None  # Used so asyncio.gather always receives awaitables

# ============================================================================
# multimodal
# ============================================================================

class MultimodalAgent(BaseAgent):
    """Image alts, transcripts, conversational tone, snippet shape and speakable markup."""

    key = "multimodal"  # Category key
    title = "Multimodal & Voice GEO"  # Display title
    kind = "geo"  # GEO report
    weight = 0.8  # Lower weight (relevant mainly to media/voice content)

    async def analyze(self, ctx: AgentContext) -> list[ParameterResult]:
        """Return all Multimodal & Voice rows."""
        page = ctx.page  # Page signals shorthand
        gem = ctx.clients.gemini  # Gemini client
        results: list[ParameterResult] = []  # Accumulate rows

        # --- Image alt text quality ---
        imgs = [i for i in page.images if i.get("src")]  # Images with a source
        with_alt = [i for i in imgs if i.get("alt")]  # Images with a non-empty alt
        descriptive = [i for i in with_alt if len((i.get("alt") or "").split()) >= 3]  # Multi-word alts
        share = (len(descriptive) / len(imgs)) if imgs else 1.0  # Share of descriptive alts
        results.append(
            scored(
                "Image alt text quality",  # Parameter name
                "Descriptive alts that match image content",  # What to check
                meeting=(not imgs) or share >= 0.6,  # No images, or mostly descriptive alts
                partial=bool(imgs) and share >= 0.3,  # Some descriptive alts
                method=DetectionMethod.CRAWL,  # Parsed alts (Gemini vision optional)
                detail=f"{len(descriptive)}/{len(imgs)} images have descriptive alts",  # Evidence
                recommendation="Write descriptive alt text (3+ meaningful words) that matches each image.",
                priority=Priority.LOW,
            )
        )

        # --- Video transcripts ---
        has_video = bool(page.soup and page.soup.find(["video", "iframe"]))  # Video/embeds present?
        lower = page.visible_text.lower()  # Lower-cased body
        has_transcript = "transcript" in lower or type_present(page, "VideoObject")  # Transcript signal
        results.append(
            scored(
                "Video transcripts",  # Parameter name
                "Full text transcripts on-page or in schema",  # What to check
                meeting=(not has_video) or has_transcript,  # No video, or a transcript exists
                partial=has_video and not has_transcript,  # Video without a transcript
                method=DetectionMethod.CRAWL,  # Detected transcript/VideoObject
                detail=f"video={has_video}, transcript signal={has_transcript}",  # Evidence
                recommendation="Provide full text transcripts for videos (on-page or in VideoObject schema).",
                priority=Priority.LOW,
                confidence=Confidence.MEDIUM,
            )
        )

        # --- Conversational phrasing (Gemini) ---
        results.append(
            await llm_scored(
                "Conversational phrasing",  # Parameter name
                "Some content in natural spoken language for voice",  # What to check
                gemini=gem,  # Gemini judges tone
                signal=f"Sample: {page.visible_text[:1500]}. "
                "Is some content phrased in natural, spoken language suitable for voice answers?",
                fallback_meeting=True,  # Optimistic default when Gemini is unavailable
                fallback_detail="Heuristic default (Gemini unavailable).",  # Fallback evidence
                recommendation="Include some natural, conversational phrasing suited to voice answers.",
                priority=Priority.LOW,
            )
        )

        # --- Featured snippet shape (paragraph/list/table) (Gemini) ---
        has_list = bool(page.soup and page.soup.find(["ul", "ol"]))  # List present?
        has_table = bool(page.soup and page.soup.find("table"))  # Table present?
        results.append(
            await llm_scored(
                "Featured snippet shape",  # Parameter name
                "Match Google's voice/AI format: paragraph, list, or table",  # What to check
                gemini=gem,  # Gemini judges snippet-shaped content
                signal=f"Has list: {has_list}. Has table: {has_table}. Sample: {page.visible_text[:1000]}. "
                "Is content shaped as a concise paragraph, list or table that fits a featured snippet?",
                fallback_meeting=has_list or has_table,  # Heuristic: structured content present
                fallback_detail=f"list={has_list}, table={has_table}",  # Fallback evidence
                recommendation="Shape key answers as a concise paragraph, list or table for snippets.",
                priority=Priority.LOW,
            )
        )

        # --- SpeakableSpecification (voice) ---
        speakable = block_mentions(page, "speakable") or block_mentions(page, "SpeakableSpecification")
        results.append(
            scored(
                "SpeakableSpecification (voice)",  # Parameter name
                "Passages marked for text-to-speech",  # What to check
                meeting=speakable,  # Speakable markup present
                partial=True,  # Optional; absence is a soft miss
                method=DetectionMethod.CRAWL,  # Parsed JSON-LD
                detail=f"speakable present: {speakable}",  # Evidence
                recommendation="Mark key passages with SpeakableSpecification for text-to-speech.",
                priority=Priority.LOW,
                confidence=Confidence.MEDIUM,
            )
        )

        return results  # All Multimodal & Voice rows
