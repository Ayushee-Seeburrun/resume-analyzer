import os
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./job_tracker.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Application(Base):
    __tablename__ = "job-applications"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String)
    job_title = Column(String)
    platform = Column(String)
    status = Column(String)
    applied_date = Column(String)
    notes = Column(String)


class ResumeAnalysis(Base):
    __tablename__ = "resume_analyses"

    id = Column(Integer, primary_key=True, index=True)
    candidate_name = Column(String, nullable=True)
    resume_filename = Column(String, nullable=True)
    job_description = Column(Text, nullable=False)
    resume_text = Column(Text, nullable=False)
    analysis_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


def create_tables():
    Base.metadata.create_all(bind=engine)
