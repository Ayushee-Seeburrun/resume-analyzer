from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

applications = []

class ApplicationCreate(BaseModel):
    company: str
    job_title: str
    status: str


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
