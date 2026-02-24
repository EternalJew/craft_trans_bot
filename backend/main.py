import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

from database import engine, get_db
import models
import schemas
from auth import authenticate_manager, create_access_token
from routers import routes, rides, bookings, parcels

# Create all tables on startup
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="CraftTrans API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)
app.include_router(rides.router)
app.include_router(bookings.router)
app.include_router(parcels.router)


@app.post("/auth/token", response_model=schemas.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    manager = authenticate_manager(db, form_data.username, form_data.password)
    if not manager:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    token = create_access_token({"sub": manager.username})
    return {"access_token": token, "token_type": "bearer"}


@app.get("/health")
def health():
    return {"status": "ok"}
