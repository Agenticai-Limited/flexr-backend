from fastapi import APIRouter, Depends, File, UploadFile

from src.flexr.crew import Flexr
from fastapi import HTTPException
from pydantic import BaseModel
from .auth import authenticate_user, LoginRequest
from typing import Dict, Optional
import tempfile
from loguru import logger
from .db_factory import DBFactory

router = APIRouter(prefix="/api", tags=["AI Crews"])


class CrewInput(BaseModel):
    """
    Input model for crew operations
    """

    query: str | None = None

class FeedbackRequest(BaseModel):
    """
    Feedback request model
    """

    messageId: str
    liked: bool
    reason: Optional[str] = None
    content: str
    metadata: Optional[str] = None


@router.post(
    "/qa",
    summary="Flexr Crew Handler",
    description="Handle knowledgebase related questions",
)
async def handle_qa(input_data: CrewInput):
    """
    QA team processes inquiries

    - **input_data**: Input data containing questions

    Returns: QA team processing result
    """
    return Flexr().crew().kickoff(input_data.model_dump())


@router.post(
    "/login", summary="User Authentication", description="Authenticate user credentials"
)
async def login(request: LoginRequest):
    """
    Process user login requests

    - **request**: Login request containing username and password

    Returns: Authentication result
    """
    return authenticate_user(request)


@router.post(
    "/upload",
    summary="File upload",
    description="Handle file uploads then return the file path",
)
async def upload(file: UploadFile = File(...)):
    """
    Process file uploads

    - **file**: Uploaded file

    Returns: File path
    """
    logger.info(f"file: {file}")

    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=file.filename
        ) as temp_file:
            while chunk := await file.read(1024 * 1024):
                temp_file.write(chunk)
            temp_file_path = temp_file.name
            logger.info(f"temp_file_path: {temp_file_path}")
            return {"url": temp_file_path, "status": "success", "name": temp_file_path}
    except Exception as e:
        logger.error(f"File upload error: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        await file.close()


@router.post(
    "/feedback",
    summary="feedback crewai response",
    description="feedback crewai response",
)
def log_feedback(feedback: FeedbackRequest):
    """
    Log feedback for crewai response and save to SQLite database

    Args:
        feedback (FeedbackRequest): The feedback data to be logged

    Returns:
        dict: Status of the feedback logging operation
    """
    logger.info(f"feedback: {feedback}")
    db_util = DBFactory.get_db_util()
    return db_util.save_feedback(feedback)
