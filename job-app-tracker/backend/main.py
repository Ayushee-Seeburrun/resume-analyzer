import json
import os
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv()

app = FastAPI()

applications = []

class ApplicationCreate(BaseModel):
    company: str
    job_title: str
    status: str


class ResumeAnalysisRequest(BaseModel):
    job_description: str = Field(..., min_length=50)
    resume_text: str = Field(..., min_length=50)
    candidate_name: str | None = None


class ResumeAnalysisResult(BaseModel):
    candidate_name: str | None = None
    fit_score: int = Field(..., ge=0, le=100)
    fit_level: Literal["Excellent", "Strong", "Moderate", "Weak", "Poor"]
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
        "recommendation",
        "matched_keywords",
        "missing_keywords",
        "strengths",
        "concerns",
        "summary_bullets",
    ],
}


@app.get("/")
def home():
    return {"message": "Job Application Tracker API is running"}


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
                        "in the resume. Return only valid JSON matching the supplied schema."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Candidate name: {payload.candidate_name or 'Unknown'}\n\n"
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
        return ResumeAnalysisResult(**analysis)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail="OpenAI returned an invalid resume analysis response",
        ) from exc
