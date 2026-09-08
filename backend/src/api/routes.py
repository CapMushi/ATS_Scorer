import os
import time
import logging
import tempfile
import shutil

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from starlette.background import BackgroundTask
from typing import Optional

from config import MAX_CVS_PER_BATCH
from src.parser import parse_cv, parse_jd, extract_skills_from_jd, extract_required_yoe
from src.scorer import ScoringPipeline
from src.llm import (
    LLMClient,
    build_cv_extraction_prompt, build_jd_extraction_prompt,
    parse_cv_extraction, parse_jd_extraction,
)
from src.export import generate_excel_report
from src.models import (
    AnalysisResponse, JDAnalysisResponse,
    HealthResponse, CandidateResult, ParsedCandidate,
)
from src.utils.docx_converter import convert_docx_to_pdf, convert_docx_to_pdf_bytes

logger = logging.getLogger(__name__)
router = APIRouter()

# Globals will be injected or imported from a shared state, 
# but for now, we'll keep the lazy loaders here to avoid circular imports.
_pipeline: Optional[ScoringPipeline] = None
_llm: Optional[LLMClient] = None
_keybert_model = None


def get_pipeline() -> ScoringPipeline:
    global _pipeline
    if _pipeline is None:
        logger.info("Loading embedding model (first request)...")
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        _pipeline = ScoringPipeline(model=model)

        # Also init KeyBERT with same model
        global _keybert_model
        from keybert import KeyBERT
        _keybert_model = KeyBERT(model=model)

        logger.info("Model loaded successfully")
    return _pipeline


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm


@router.get("/health", response_model=HealthResponse)
async def health_check():
    llm = get_llm()
    return HealthResponse(
        status="ok",
        model_loaded=_pipeline is not None,
        gemini_configured=llm._gemini_available,
        groq_configured=llm._groq_available,
        llm_mode=llm.active_provider,
    )


@router.post("/convert-docx")
async def api_convert_docx(file: UploadFile = File(...)):
    """Converts a DOCX file to PDF and returns the file. Results are cached by content hash."""
    if not file.filename.lower().endswith(".docx") and not file.filename.lower().endswith(".doc"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")

    try:
        file_bytes = await file.read()
        temp_dir = tempfile.mkdtemp()

        pdf_bytes = convert_docx_to_pdf_bytes(file_bytes, file.filename or "file.docx", temp_dir)

        shutil.rmtree(temp_dir, ignore_errors=True)

        if not pdf_bytes:
            raise HTTPException(status_code=500, detail="Failed to convert DOCX to PDF")

        from fastapi.responses import Response
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{os.path.splitext(file.filename or "cv")[0]}.pdf"'}
        )
    except Exception as e:
        logger.error(f"Error in /convert-docx: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/parse-jd", response_model=JDAnalysisResponse)
async def analyze_jd(file: UploadFile = File(...)):
    """Parse a JD and extract skills + requirements."""
    content = await file.read()
    jd_text = parse_jd(content, file_name=file.filename or "jd")

    # Regex extraction
    global _keybert_model
    must_haves, nice_to_haves = extract_skills_from_jd(
        jd_text, keybert_model=_keybert_model
    )
    required_yoe = extract_required_yoe(jd_text)

    # LLM enhancement
    llm = get_llm()
    llm_enhanced = False

    if llm.is_available:
        prompt = build_jd_extraction_prompt(jd_text)
        raw = await llm.call_json_async(prompt)
        parsed = parse_jd_extraction(raw)

        if parsed:
            llm_enhanced = True
            # Merge LLM results with regex results
            llm_must = parsed.get("must_have_skills", [])
            llm_nice = parsed.get("nice_to_have_skills", [])
            llm_yoe = parsed.get("required_yoe", 0)

            if llm_must:
                combined = list(set(must_haves + llm_must))
                must_haves = sorted(combined)
            if llm_nice:
                combined_nice = list(set(nice_to_haves + llm_nice))
                nice_to_haves = sorted(combined_nice)
            if llm_yoe > 0:
                required_yoe = llm_yoe

    return JDAnalysisResponse(
        jd_text=jd_text,
        must_have_skills=must_haves,
        nice_to_have_skills=nice_to_haves,
        required_yoe=required_yoe,
        llm_enhanced=llm_enhanced,
    )


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_candidates(
    jd_file: UploadFile = File(...),
    cv_files: list[UploadFile] = File(...),
    must_have_skills: Optional[str] = Form(None),
    nice_to_have_skills: Optional[str] = Form(None),
    target_yoe: float = Form(0.0),
):
    """Full analysis pipeline: parse JD + CVs, score, rank."""
    start_time = time.time()

    if len(cv_files) > MAX_CVS_PER_BATCH:
        cv_files = cv_files[:MAX_CVS_PER_BATCH]

    jd_content = await jd_file.read()
    jd_text = parse_jd(jd_content, file_name=jd_file.filename or "jd")
    logger.info(f"JD parsed: {len(jd_text)} chars from '{jd_file.filename}'")

    pipeline = get_pipeline()
    llm = get_llm()

    global _keybert_model
    if must_have_skills:
        must_haves = [s.strip() for s in must_have_skills.split(",") if s.strip()]
    else:
        must_haves, _ = extract_skills_from_jd(jd_text, keybert_model=_keybert_model)

    if nice_to_have_skills:
        nice_to_haves = [s.strip() for s in nice_to_have_skills.split(",") if s.strip()]
    else:
        _, nice_to_haves = extract_skills_from_jd(jd_text, keybert_model=_keybert_model)

    candidates: list[ParsedCandidate] = []
    for cv_file in cv_files:
        try:
            cv_content = await cv_file.read()
            parsed = parse_cv(cv_content, file_name=cv_file.filename or "cv")
            logger.info(f"Parsed CV '{cv_file.filename}' -> name: '{parsed.contact.name}', text: {len(parsed.full_text)} chars")
            candidates.append(parsed)
        except Exception as e:
            logger.warning(f"Failed to parse {cv_file.filename}: {e}")

    if llm.is_available:
        llm.reset_rate_limits()
        for i, candidate in enumerate(candidates):
            prompt = build_cv_extraction_prompt(
                candidate.full_text, must_haves
            )
            raw = llm.call_json(prompt)
            logger.info(f"LLM output for CV {i} ('{candidate.file_name}'): {'OK' if raw else 'None'}")
            if raw:
                llm_data = parse_cv_extraction(raw)
                if llm_data:
                    candidates[i] = candidate.model_copy(
                        update={"llm_data": llm_data}
                    )
                    
                    # Detailed logging for transparency
                    found_skills = [s.name for s in llm_data.skills_found if s.context != "missing"]
                    missing_skills = [s.name for s in llm_data.skills_found if s.context == "missing"]
                    logger.info(f"  -> LLM name: '{llm_data.candidate_name}'")
                    logger.info(f"  -> LLM YOE (fallback guess): {llm_data.total_yoe}")
                    logger.info(f"  -> LLM found {len(found_skills)} skills: {', '.join(found_skills)}")
                    if missing_skills:
                        logger.info(f"  -> LLM missed {len(missing_skills)} skills: {', '.join(missing_skills)}")
                    
                else:
                    logger.warning(f"  -> LLM parse failed for CV {i} ('{candidate.file_name}')")
            else:
                logger.warning(f"  -> No LLM output for CV {i} ('{candidate.file_name}') — using regex fallback")

    results = pipeline.score_candidates(
        jd_text=jd_text,
        candidates=candidates,
        must_have_skills=must_haves,
        nice_to_have_skills=nice_to_haves,
        target_yoe=target_yoe,
    )

    elapsed = round(time.time() - start_time, 2)

    jd_analysis = JDAnalysisResponse(
        jd_text=jd_text,
        must_have_skills=must_haves,
        nice_to_have_skills=nice_to_haves,
        required_yoe=target_yoe,
    )

    return AnalysisResponse(
        candidates=results,
        jd_analysis=jd_analysis,
        llm_mode=llm.active_provider,
        processing_time_seconds=elapsed,
    )


@router.post("/analyze-single", response_model=CandidateResult)
async def analyze_single_candidate(
    cv_file: UploadFile = File(...),
    jd_text: str = Form(...),
    must_have_skills: Optional[str] = Form(None),
    nice_to_have_skills: Optional[str] = Form(None),
    target_yoe: float = Form(0.0),
):
    """Analyze a single candidate for streaming architecture."""
    pipeline = get_pipeline()
    llm = get_llm()

    must_haves = [s.strip() for s in must_have_skills.split(",")] if must_have_skills else []
    nice_to_haves = [s.strip() for s in nice_to_have_skills.split(",")] if nice_to_have_skills else []

    try:
        cv_content = await cv_file.read()
        parsed = parse_cv(cv_content, file_name=cv_file.filename or "cv")
        logger.info(f"Single parse CV '{cv_file.filename}'")
    except Exception as e:
        logger.warning(f"Failed to parse {cv_file.filename}: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to parse CV: {e}")

    if llm.is_available:
        prompt = build_cv_extraction_prompt(parsed.full_text, must_haves)
        logger.info(f"LLM is available, calling JSON for {parsed.file_name}")
        raw = await llm.call_json_async(prompt)
        if raw:
            logger.info(f"LLM call returned data of type: {type(raw)}")
            llm_data = parse_cv_extraction(raw)
            if llm_data:
                
                # Detailed logging for transparency
                found_skills = [s.name for s in llm_data.skills_found if s.context != "missing"]
                missing_skills = [s.name for s in llm_data.skills_found if s.context == "missing"]
                logger.info(f"Successfully parsed LLM data for '{parsed.file_name}':")
                logger.info(f"  -> Candidate: {llm_data.candidate_name}")
                logger.info(f"  -> Skills Found ({len(found_skills)}): {', '.join(found_skills)}")
                if missing_skills:
                    logger.info(f"  -> Skills Missing ({len(missing_skills)}): {', '.join(missing_skills)}")
                
                parsed = parsed.model_copy(update={"llm_data": llm_data})
            else:
                logger.warning(f"parse_cv_extraction returned None for raw data: {str(raw)[:200]}...")
        else:
            logger.warning(f"llm.call_json returned None for {parsed.file_name}")
    else:
        logger.warning(f"LLM is not available. Skipping LLM for {parsed.file_name}. Gemini ok: {llm._gemini_available}, Cooldown: {llm._gemini_rate_limit_until - time.time()}s remaining")

    # Score candidates takes a list, so we pass a list of 1 and extract the result
    results = pipeline.score_candidates(
        jd_text=jd_text,
        candidates=[parsed],
        must_have_skills=must_haves,
        nice_to_have_skills=nice_to_haves,
        target_yoe=target_yoe,
    )

    if not results:
        raise HTTPException(status_code=500, detail="Scoring failed")

    return results[0]

@router.post("/export")
async def export_excel(
    jd_file: UploadFile = File(...),
    cv_files: list[UploadFile] = File(...),
    must_have_skills: Optional[str] = Form(None),
    nice_to_have_skills: Optional[str] = Form(None),
    target_yoe: float = Form(0.0),
):
    """Run analysis and return styled Excel report."""
    response = await analyze_candidates(
        jd_file=jd_file,
        cv_files=cv_files,
        must_have_skills=must_have_skills,
        nice_to_have_skills=nice_to_have_skills,
        target_yoe=target_yoe,
    )

    excel_bytes = generate_excel_report(response.candidates)

    return StreamingResponse(
        excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=ats_recruitment_report.xlsx"
        },
    )

@router.post("/export-json")
async def export_excel_from_json(candidates: list[CandidateResult]):
    """Generate styled Excel report directly from JSON results."""
    excel_bytes = generate_excel_report(candidates)

    return StreamingResponse(
        excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=ats_recruitment_report.xlsx"
        },
    )
