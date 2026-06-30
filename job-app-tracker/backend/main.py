import json
import os
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from database import ResumeAnalysis, SessionLocal, create_tables

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
create_tables()

applications = []

class ApplicationCreate(BaseModel):
    company: str
    job_title: str
    status: str


class ScoringWeights(BaseModel):
    required_skills: int = Field(35, ge=0, le=100)
    experience_relevance: int = Field(20, ge=0, le=100)
    responsibilities_match: int = Field(15, ge=0, le=100)
    tools_match: int = Field(10, ge=0, le=100)
    seniority_match: int = Field(10, ge=0, le=100)
    education_domain_match: int = Field(10, ge=0, le=100)

    @model_validator(mode="after")
    def weights_must_total_100(self):
        if sum(self.model_dump().values()) != 100:
            raise ValueError("Scoring weights must total 100")
        return self


class ScoreBreakdown(BaseModel):
    required_skills: int = Field(..., ge=0, le=100)
    experience_relevance: int = Field(..., ge=0, le=100)
    responsibilities_match: int = Field(..., ge=0, le=100)
    tools_match: int = Field(..., ge=0, le=100)
    seniority_match: int = Field(..., ge=0, le=100)
    education_domain_match: int = Field(..., ge=0, le=100)


class ResumeAnalysisRequest(BaseModel):
    job_description: str = Field(..., min_length=50)
    resume_text: str = Field(..., min_length=50)
    candidate_name: str | None = None
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)


class ResumeAnalysisResult(BaseModel):
    candidate_name: str | None = None
    fit_score: int = Field(..., ge=0, le=100)
    fit_level: Literal["Excellent", "Strong", "Moderate", "Weak", "Poor"]
    scoring_weights: ScoringWeights
    score_breakdown: ScoreBreakdown
    recommendation: Literal[
        "Strong interview",
        "Interview",
        "Maybe interview",
        "Do not interview",
    ]
    matched_keywords: list[str]
    missing_keywords: list[str]
    strengths: list[str]
    concerns: list[str]
    summary_bullets: list[str]


class ResumeAnalysisResponse(ResumeAnalysisResult):
    id: int | None = None
    resume_filename: str | None = None
    resume_text: str
    saved: bool = False


class ResumeAnalysisSaveRequest(BaseModel):
    job_description: str = Field(..., min_length=50)
    resume_text: str = Field(..., min_length=50)
    analysis: ResumeAnalysisResult
    candidate_name: str | None = None
    resume_filename: str | None = None


class SavedResumeAnalysis(BaseModel):
    id: int
    candidate_name: str | None = None
    resume_filename: str | None = None
    fit_score: int
    fit_level: str
    scoring_weights: ScoringWeights
    score_breakdown: ScoreBreakdown
    recommendation: str
    matched_keywords: list[str]
    missing_keywords: list[str]
    strengths: list[str]
    concerns: list[str]
    summary_bullets: list[str]
    created_at: str


RESUME_ANALYSIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "candidate_name": {"type": ["string", "null"]},
        "fit_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "fit_level": {
            "type": "string",
            "enum": ["Excellent", "Strong", "Moderate", "Weak", "Poor"],
        },
        "scoring_weights": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "required_skills": {"type": "integer", "minimum": 0, "maximum": 100},
                "experience_relevance": {"type": "integer", "minimum": 0, "maximum": 100},
                "responsibilities_match": {"type": "integer", "minimum": 0, "maximum": 100},
                "tools_match": {"type": "integer", "minimum": 0, "maximum": 100},
                "seniority_match": {"type": "integer", "minimum": 0, "maximum": 100},
                "education_domain_match": {"type": "integer", "minimum": 0, "maximum": 100},
            },
            "required": [
                "required_skills",
                "experience_relevance",
                "responsibilities_match",
                "tools_match",
                "seniority_match",
                "education_domain_match",
            ],
        },
        "score_breakdown": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "required_skills": {"type": "integer", "minimum": 0, "maximum": 100},
                "experience_relevance": {"type": "integer", "minimum": 0, "maximum": 100},
                "responsibilities_match": {"type": "integer", "minimum": 0, "maximum": 100},
                "tools_match": {"type": "integer", "minimum": 0, "maximum": 100},
                "seniority_match": {"type": "integer", "minimum": 0, "maximum": 100},
                "education_domain_match": {"type": "integer", "minimum": 0, "maximum": 100},
            },
            "required": [
                "required_skills",
                "experience_relevance",
                "responsibilities_match",
                "tools_match",
                "seniority_match",
                "education_domain_match",
            ],
        },
        "recommendation": {
            "type": "string",
            "enum": [
                "Strong interview",
                "Interview",
                "Maybe interview",
                "Do not interview",
            ],
        },
        "matched_keywords": {"type": "array", "items": {"type": "string"}},
        "missing_keywords": {"type": "array", "items": {"type": "string"}},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "concerns": {"type": "array", "items": {"type": "string"}},
        "summary_bullets": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "candidate_name",
        "fit_score",
        "fit_level",
        "scoring_weights",
        "score_breakdown",
        "recommendation",
        "matched_keywords",
        "missing_keywords",
        "strengths",
        "concerns",
        "summary_bullets",
    ],
}


def fit_level_from_score(score: int) -> Literal["Excellent", "Strong", "Moderate", "Weak", "Poor"]:
    if score >= 90:
        return "Excellent"
    if score >= 75:
        return "Strong"
    if score >= 60:
        return "Moderate"
    if score >= 40:
        return "Weak"
    return "Poor"


def recommendation_from_score(
    score: int,
) -> Literal["Strong interview", "Interview", "Maybe interview", "Do not interview"]:
    if score >= 90:
        return "Strong interview"
    if score >= 75:
        return "Interview"
    if score >= 60:
        return "Maybe interview"
    return "Do not interview"


def enforce_scoring_rubric(
    analysis: ResumeAnalysisResult,
    weights: ScoringWeights,
) -> ResumeAnalysisResult:
    weight_values = weights.model_dump()
    raw_breakdown = analysis.score_breakdown.model_dump()
    capped_breakdown = {
        key: min(max(raw_breakdown[key], 0), weight_values[key])
        for key in weight_values
    }
    fit_score = sum(capped_breakdown.values())

    return ResumeAnalysisResult(
        **{
            **analysis.model_dump(),
            "fit_score": fit_score,
            "fit_level": fit_level_from_score(fit_score),
            "recommendation": recommendation_from_score(fit_score),
            "scoring_weights": weights,
            "score_breakdown": ScoreBreakdown(**capped_breakdown),
        }
    )


def parse_scoring_weights(raw_weights: str | None) -> ScoringWeights:
    if not raw_weights:
        return ScoringWeights()

    try:
        return ScoringWeights(**json.loads(raw_weights))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail="Scoring weights must be valid JSON and total 100",
        ) from exc


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def extract_text_from_pdf(upload: UploadFile) -> str:
    if upload.content_type not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(status_code=400, detail="Resume upload must be a PDF file")

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="PDF support is not installed. Run: pip install -r requirements.txt",
        ) from exc

    try:
        reader = PdfReader(upload.file)
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read PDF resume: {exc}") from exc

    resume_text = "\n\n".join(page.strip() for page in pages if page.strip()).strip()
    if len(resume_text) < 50:
        raise HTTPException(
            status_code=400,
            detail="Could not extract enough text from this PDF resume",
        )

    return resume_text


def run_resume_analysis(payload: ResumeAnalysisRequest) -> ResumeAnalysisResult:
    if len(payload.job_description.strip()) < 50:
        raise HTTPException(
            status_code=422,
            detail="Job description must contain at least 50 characters",
        )

    if len(payload.resume_text.strip()) < 50:
        raise HTTPException(
            status_code=422,
            detail="Resume text must contain at least 50 characters",
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY is not configured in the backend environment",
        )

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="OpenAI SDK is not installed. Run: pip install -r requirements.txt",
        ) from exc

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    weights = payload.scoring_weights
    weights_json = json.dumps(weights.model_dump(), indent=2)

    try:
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert technical recruiter and ATS resume analyst. "
                        "Compare the candidate resume against the job description. "
                        "Be specific, fair, and evidence-based. Identify missing keywords "
                        "that appear in the job description but are absent or weakly represented "
                        "in the resume. Score each category using the user-supplied maximum "
                        "weights. The score_breakdown values must be integers where each value "
                        "is between 0 and that category's configured weight. fit_score must be "
                        "the sum of score_breakdown. Return only valid JSON matching the supplied schema."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Candidate name: {payload.candidate_name or 'Unknown'}\n\n"
                        f"SCORING WEIGHTS, TOTAL 100:\n{weights_json}\n\n"
                        "Return scoring_weights exactly as provided above. "
                        "Return score_breakdown as the points earned in each category.\n\n"
                        "Score category meanings:\n"
                        "- required_skills: must-have skills explicitly required by the job.\n"
                        "- experience_relevance: relevance of the candidate's past work to this role.\n"
                        "- responsibilities_match: overlap with day-to-day job responsibilities.\n"
                        "- tools_match: match for named tools, technologies, frameworks, and platforms.\n"
                        "- seniority_match: years, seniority, leadership, and role-level alignment.\n"
                        "- education_domain_match: education, certifications, industry, and domain fit.\n\n"
                        f"JOB DESCRIPTION:\n{payload.job_description}\n\n"
                        f"CANDIDATE RESUME:\n{payload.resume_text}"
                    ),
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "resume_analysis_result",
                    "schema": RESUME_ANALYSIS_SCHEMA,
                    "strict": True,
                }
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI resume analysis failed: {exc}",
        ) from exc

    try:
        analysis = json.loads(response.output_text)
        analysis["scoring_weights"] = weights.model_dump()
        return enforce_scoring_rubric(ResumeAnalysisResult(**analysis), weights)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail="OpenAI returned an invalid resume analysis response",
        ) from exc


def save_resume_analysis(
    db: Session,
    job_description: str,
    resume_text: str,
    analysis: ResumeAnalysisResult,
    candidate_name: str | None = None,
    resume_filename: str | None = None,
) -> ResumeAnalysis:
    record = ResumeAnalysis(
        candidate_name=candidate_name or analysis.candidate_name,
        resume_filename=resume_filename,
        job_description=job_description,
        resume_text=resume_text,
        analysis_json=analysis.model_dump_json(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def serialize_saved_analysis(record: ResumeAnalysis) -> SavedResumeAnalysis:
    raw_analysis = json.loads(record.analysis_json)
    if "scoring_weights" not in raw_analysis:
        raw_analysis["scoring_weights"] = ScoringWeights().model_dump()
    if "score_breakdown" not in raw_analysis:
        remaining_score = raw_analysis.get("fit_score", 0)
        fallback_breakdown = {}
        for key, weight in raw_analysis["scoring_weights"].items():
            category_score = min(remaining_score, weight)
            fallback_breakdown[key] = category_score
            remaining_score -= category_score
        raw_analysis["score_breakdown"] = fallback_breakdown

    analysis = ResumeAnalysisResult(**raw_analysis)
    return SavedResumeAnalysis(
        id=record.id,
        candidate_name=record.candidate_name,
        resume_filename=record.resume_filename,
        created_at=record.created_at.isoformat(),
        **analysis.model_dump(exclude={"candidate_name"}),
    )


@app.get("/")
def home():
    return FileResponse("static/index.html")


@app.get("/applications")
def get_applications():
    return applications


@app.get("/applications/{application_id}")
def get_application(application_id: int):
    for application in applications:
        if application["id"] == application_id:
            return application

    raise HTTPException(status_code=404, detail="Application not found")


@app.post("/applications", status_code=201)
def create_application(application: ApplicationCreate):
    new_application = {
        "id": len(applications) + 1,
        **application.model_dump(),
    }
    applications.append(new_application)
    return new_application


@app.put("/applications/{application_id}")
def update_application(application_id: int, updated_application: ApplicationCreate):
    for application in applications:
        if application["id"] == application_id:
            application["company"] = updated_application.company
            application["job_title"] = updated_application.job_title
            application["status"] = updated_application.status
            return application

    raise HTTPException(status_code=404, detail="Application not found")


@app.delete("/applications/{application_id}")
def delete_application(application_id: int):
    for application in applications:
        if application["id"] == application_id:
            applications.remove(application)
            return {"message": "Application deleted"}

    raise HTTPException(status_code=404, detail="Application not found")


@app.post("/resume/analyze", response_model=ResumeAnalysisResult)
def analyze_resume(payload: ResumeAnalysisRequest):
    return run_resume_analysis(payload)


@app.post("/resume/analyze-upload", response_model=ResumeAnalysisResponse)
def analyze_resume_upload(
    job_description: str = Form(..., min_length=50),
    resume_file: UploadFile = File(...),
    candidate_name: str | None = Form(None),
    scoring_weights: str | None = Form(None),
    save: bool = Form(False),
    db: Session = Depends(get_db),
):
    resume_text = extract_text_from_pdf(resume_file)
    weights = parse_scoring_weights(scoring_weights)
    analysis = run_resume_analysis(
        ResumeAnalysisRequest(
            job_description=job_description,
            resume_text=resume_text,
            candidate_name=candidate_name,
            scoring_weights=weights,
        )
    )

    record = None
    if save:
        record = save_resume_analysis(
            db=db,
            job_description=job_description,
            resume_text=resume_text,
            analysis=analysis,
            candidate_name=candidate_name,
            resume_filename=resume_file.filename,
        )

    return ResumeAnalysisResponse(
        **analysis.model_dump(),
        id=record.id if record else None,
        resume_filename=resume_file.filename,
        resume_text=resume_text,
        saved=bool(record),
    )


@app.post("/resume/analyses", response_model=SavedResumeAnalysis, status_code=201)
def create_saved_resume_analysis(
    payload: ResumeAnalysisSaveRequest,
    db: Session = Depends(get_db),
):
    record = save_resume_analysis(
        db=db,
        job_description=payload.job_description,
        resume_text=payload.resume_text,
        analysis=payload.analysis,
        candidate_name=payload.candidate_name,
        resume_filename=payload.resume_filename,
    )
    return serialize_saved_analysis(record)


@app.get("/resume/analyses", response_model=list[SavedResumeAnalysis])
def list_saved_resume_analyses(db: Session = Depends(get_db)):
    records = (
        db.query(ResumeAnalysis)
        .order_by(ResumeAnalysis.created_at.desc(), ResumeAnalysis.id.desc())
        .all()
    )
    return [serialize_saved_analysis(record) for record in records]


@app.get("/resume/analyses/{analysis_id}", response_model=SavedResumeAnalysis)
def get_saved_resume_analysis(analysis_id: int, db: Session = Depends(get_db)):
    record = db.query(ResumeAnalysis).filter(ResumeAnalysis.id == analysis_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Resume analysis not found")

    return serialize_saved_analysis(record)
