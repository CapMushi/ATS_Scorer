"""
Main scoring pipeline — orchestrates all scoring components.
This is the heart of the ATS engine, combining semantic similarity,
BM25 keyword matching, skill evaluation, YOE, and calibration.
"""

from typing import Optional

from sentence_transformers import SentenceTransformer

from config import (
    VECTOR_WEIGHT,
    BM25_WEIGHT,
    SKILLS_SECTION_WEIGHT,
    RECENT_EXP_WEIGHT,
    OLDER_EXP_WEIGHT
)
from ..models.schemas import (
    CandidateResult, ScoringAudit, SubScores,
    ParsedCandidate, ContactInfo, SkillMatch,
    ExperienceEntry, EducationEntry,
)
from .semantic_scorer import SemanticScorer
from .keyword_scorer import compute_bm25_scores
from .skill_evaluator import evaluate_skills
from .yoe_extractor import extract_yoe
from .calibrator import (
    calibrate_scores,
    apply_skill_penalty,
    apply_nice_to_have_bonus,
    apply_yoe_modifier,
)


class ScoringPipeline:
    """
    Orchestrates the full scoring pipeline for a batch of candidates.
    Loads the embedding model once and reuses it across batches.
    """

    def __init__(self, model: Optional[SentenceTransformer] = None):
        self.semantic = SemanticScorer(model=model)

    def _split_experience_for_recency(
        self, experience_text: str
    ) -> tuple[str, str]:
        """Split experience into recent and older halves."""
        if not experience_text.strip():
            return ("", "")

        lines = [ln for ln in experience_text.split("\n") if ln.strip()]
        if len(lines) <= 3:
            return (experience_text, "")

        midpoint = len(lines) // 2
        recent = "\n".join(lines[:midpoint])
        older = "\n".join(lines[midpoint:])
        return (recent, older)

    def score_candidates(
        self,
        jd_text: str,
        candidates: list[ParsedCandidate],
        must_have_skills: list[str],
        nice_to_have_skills: list[str],
        target_yoe: float = 0.0,
    ) -> list[CandidateResult]:
        """
        Run the full scoring pipeline on a batch of candidates.

        Returns sorted list of CandidateResult (highest score first).
        """
        if not candidates:
            return []

        n = len(candidates)

        # === Extract section texts ===
        cv_skills_texts = []
        cv_recent_texts = []
        cv_older_texts = []

        for c in candidates:
            sec = c.sections
            skills = sec.skills or ""
            experience = sec.experience or ""
            full = c.full_text

            cv_skills_texts.append(skills if skills.strip() else full)

            exp_source = experience if experience.strip() else full
            recent, older = self._split_experience_for_recency(exp_source)
            cv_recent_texts.append(recent if recent.strip() else exp_source)
            cv_older_texts.append(older if older.strip() else "")

        # === Semantic scoring per section ===
        skills_cosine = self.semantic.compute_similarities(
            jd_text, cv_skills_texts
        )
        recent_cosine = self.semantic.compute_similarities(
            jd_text, cv_recent_texts
        )

        has_older = any(t.strip() for t in cv_older_texts)
        older_cosine = (
            self.semantic.compute_similarities(jd_text, cv_older_texts)
            if has_older
            else [0.0] * n
        )

        # Weighted vector scores
        vector_scores = []
        for i in range(n):
            weighted = (
                skills_cosine[i] * SKILLS_SECTION_WEIGHT
                + recent_cosine[i] * RECENT_EXP_WEIGHT
                + older_cosine[i] * OLDER_EXP_WEIGHT
            )
            vector_scores.append(weighted)

        # === BM25 keyword scoring ===
        bm25_corpus = [
            f"{cv_skills_texts[i]} {cv_recent_texts[i]}" for i in range(n)
        ]
        bm25_scores = compute_bm25_scores(jd_text, bm25_corpus)

        # === Combine vector + BM25 ===
        raw_composite = [
            (vector_scores[i] * VECTOR_WEIGHT) + (bm25_scores[i] * BM25_WEIGHT)
            for i in range(n)
        ]

        # === Calibrate to 0-100% ===
        calibrated = calibrate_scores(raw_composite)

        # === Skill evaluation + penalty ===
        skill_results = []
        penalty_amounts = []

        for i, c in enumerate(candidates):
            sections_dict = c.sections.model_dump()
            llm_skills = None
            if c.llm_data and c.llm_data.skills_found:
                llm_skills = [s.model_dump() for s in c.llm_data.skills_found]

            eval_result = evaluate_skills(
                sections_dict, must_have_skills, llm_skills=llm_skills
            )
            skill_results.append(eval_result)

            pre_penalty = calibrated[i]
            if must_have_skills:
                calibrated[i], penalty = apply_skill_penalty(
                    calibrated[i], eval_result["ratio"]
                )
            else:
                penalty = 0.0
            penalty_amounts.append(penalty)

        # === Nice-to-have bonus ===
        nice_results = []
        bonus_amounts = []

        for i, c in enumerate(candidates):
            if nice_to_have_skills:
                sections_dict = c.sections.model_dump()
                eval_bonus = evaluate_skills(sections_dict, nice_to_have_skills)
                nice_results.append(eval_bonus)

                calibrated[i], bonus = apply_nice_to_have_bonus(
                    calibrated[i], eval_bonus["ratio"]
                )
                bonus_amounts.append(bonus)
            else:
                nice_results.append({
                    "contextual": [], "stuffed": [], "missing": [],
                    "ratio": 0.0, "detail": [],
                })
                bonus_amounts.append(0.0)

        # === YOE extraction + modifier ===
        yoe_values = []
        yoe_amounts = []

        for i, c in enumerate(candidates):
            sections_dict = c.sections.model_dump()
            llm_yoe = c.llm_data.total_yoe if c.llm_data else None
            llm_experience_entries = c.llm_data.experience_entries if c.llm_data else None

            yoe = extract_yoe(
                sections_dict, 
                c.full_text, 
                llm_yoe=llm_yoe,
                llm_experience_entries=llm_experience_entries
            )
            yoe_values.append(yoe)

            calibrated[i], yoe_mod = apply_yoe_modifier(
                calibrated[i], yoe, target_yoe
            )
            yoe_amounts.append(yoe_mod)

        # === Role Match Booster ===
        role_bonus_amounts = []
        jd_intro = jd_text[:500].lower() # Extract first 500 chars of JD which usually has the title
        for i, c in enumerate(candidates):
            bonus = 0.0
            if c.llm_data and c.llm_data.current_role:
                # Use word-based string matching instead of embeddings to avoid length-dilution
                role_words = [w for w in c.llm_data.current_role.lower().split() if len(w) > 3]
                if role_words:
                    match_count = sum(1 for w in role_words if w in jd_intro)
                    match_ratio = match_count / len(role_words)
                    
                    if match_ratio >= 0.5:
                        bonus = 15.0 # Flat 15% bonus if title matches JD intro well
                        calibrated[i] = min(100.0, calibrated[i] + bonus)
            role_bonus_amounts.append(bonus)

        # (Removed Leader-Anchored Relative Normalization per v2 plan for score stability)

        # === Build results ===
        results: list[CandidateResult] = []

        for i, c in enumerate(candidates):
            # Sub-scores
            skill_pts = round(skills_cosine[i] * 35, 1)
            recent_pts = round(recent_cosine[i] * 45, 1)
            older_pts = round(older_cosine[i] * 20, 1)
            bm25_pts = round(bm25_scores[i] * 100, 1)

            base_pct = calibrate_scores([raw_composite[i]])[0]

            all_matched = (
                skill_results[i]["contextual"] + skill_results[i]["stuffed"]
            )
            all_nice = (
                nice_results[i]["contextual"] + nice_results[i]["stuffed"]
            )

            # Build skill detail list
            detail_list = skill_results[i].get("detail", [])
            skills_detail = [
                SkillMatch(**d) for d in detail_list
            ]

            # Get LLM data if available
            llm = c.llm_data
            contact = c.contact or ContactInfo()
            experience_entries = []
            education_entries = []
            certifications = []
            candidate_summary = ""
            candidate_name = contact.name
            normalized_universities = []

            if llm:
                candidate_name = llm.candidate_name or contact.name
                contact = ContactInfo(
                    name=candidate_name,
                    email=contact.email or llm.email,
                    phone=contact.phone or llm.phone,
                    linkedin=contact.linkedin or llm.linkedin,
                    github=contact.github or llm.github,
                    portfolio=contact.portfolio or llm.portfolio,
                    location=contact.location or llm.location,
                )
                experience_entries = [
                    ExperienceEntry(**e.model_dump())
                    for e in llm.experience_entries
                ]
                education_entries = [
                    EducationEntry(**e.model_dump())
                    for e in llm.education
                ]
                certifications = llm.certifications
                candidate_summary = llm.candidate_summary
                
                # Extract unique normalized universities
                normalized_universities = list({
                    e.normalized_institution for e in education_entries 
                    if e.normalized_institution
                })


            result = CandidateResult(
                file_name=c.file_name,
                source_link=c.source_link,
                full_text=c.full_text,
                final_score_pct=calibrated[i],
                candidate_name=candidate_name,
                contact=contact,
                candidate_yoe=yoe_values[i],
                current_role=llm.current_role if llm else "",
                matched_skills=all_matched,
                contextual_skills=skill_results[i]["contextual"],
                stuffed_skills=skill_results[i]["stuffed"],
                missing_skills=skill_results[i]["missing"],
                nice_to_have_matched=all_nice,
                skills_detail=skills_detail,
                experience_entries=experience_entries,
                education=education_entries,
                normalized_universities=normalized_universities,
                certifications=certifications,
                candidate_summary=candidate_summary,
                sections=c.sections,
                audit=ScoringAudit(
                    subscores=SubScores(
                        skill_match=skill_pts,
                        recent_exp=recent_pts,
                        older_exp=older_pts,
                        bm25_keyword=bm25_pts,
                    ),
                    skills_similarity_pct=round(skills_cosine[i] * 100, 2),
                    recent_exp_similarity_pct=round(recent_cosine[i] * 100, 2),
                    older_exp_similarity_pct=round(older_cosine[i] * 100, 2),
                    raw_vector_pct=round(vector_scores[i] * 100, 2),
                    raw_bm25_pct=round(bm25_scores[i] * 100, 2),
                    composite_base_pct=base_pct,
                    must_have_penalty_pct=penalty_amounts[i],
                    nice_to_have_bonus_pct=bonus_amounts[i],
                    role_match_bonus_pct=role_bonus_amounts[i],
                    yoe_modifier_pct=yoe_amounts[i],
                    calibrated_final_pct=calibrated[i],
                ),
                llm_enhanced=c.llm_data is not None,
            )
            results.append(result)

        return sorted(results, key=lambda r: r.final_score_pct, reverse=True)
