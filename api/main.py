from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .logging_config import setup_logging
setup_logging()

from .api import router

app = FastAPI(
    title="Agent API",
    description="API Docs",
    version="1.0.0",
    docs_url="/docs", 
    redoc_url="/redoc"  
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],
)

app.include_router(router)
