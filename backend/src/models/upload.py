"""
Upload models for data upload functionality
"""
from datetime import datetime
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class DataUpload(Base):
    __tablename__ = "data_uploads"
    
    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    file_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class DataUploadRequest(BaseModel):
    filename: str = Field(..., min_length=1)
    file_size: int = Field(..., gt=0)
    file_type: str = Field(..., min_length=1)


class DataUploadResponse(BaseModel):
    id: str
    filename: str
    size: int
    file_type: str
    status: str
    created_at: datetime = Field(default_factory=datetime.now)


class FileValidationError(Exception):
    pass