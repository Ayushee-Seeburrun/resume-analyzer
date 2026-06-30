from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "postgresql://ayushee@localhost/job-tracker"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
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


def create_tables():
    Base.metadata.create_all(bind=engine)
