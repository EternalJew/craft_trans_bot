from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import models, schemas
from database import get_db
from auth import require_admin

router = APIRouter(prefix="/api/routes", tags=["routes"])


@router.get("", response_model=List[schemas.RouteOut])
def list_routes(db: Session = Depends(get_db)):
    return db.query(models.Route).order_by(models.Route.id).all()


@router.post("", response_model=schemas.RouteOut)
def create_route(body: schemas.RouteCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    route = models.Route(name=body.name, direction=body.direction, is_active=body.is_active)
    db.add(route)
    db.flush()
    for i, s in enumerate(body.stops):
        db.add(models.Stop(
            route_id=route.id, city=s.city, country=s.country,
            order=s.order if s.order is not None else i,
            pickup=s.pickup, dropoff=s.dropoff, lat=s.lat, lng=s.lng,
        ))
    db.commit()
    db.refresh(route)
    return route


@router.get("/{route_id}", response_model=schemas.RouteOut)
def get_route(route_id: int, db: Session = Depends(get_db)):
    route = db.query(models.Route).filter(models.Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return route


@router.put("/{route_id}", response_model=schemas.RouteOut)
def update_route(route_id: int, body: schemas.RouteUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    route = db.query(models.Route).filter(models.Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    route.name = body.name
    route.direction = body.direction
    route.is_active = body.is_active
    db.query(models.Stop).filter(models.Stop.route_id == route_id).delete()
    for i, s in enumerate(body.stops):
        db.add(models.Stop(
            route_id=route_id, city=s.city, country=s.country,
            order=s.order if s.order is not None else i,
            pickup=s.pickup, dropoff=s.dropoff, lat=s.lat, lng=s.lng,
        ))
    db.commit()
    db.refresh(route)
    return route


@router.delete("/{route_id}")
def delete_route(route_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    route = db.query(models.Route).filter(models.Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    db.delete(route)
    db.commit()
    return {"ok": True}
