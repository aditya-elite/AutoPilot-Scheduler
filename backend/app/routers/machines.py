from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Machine, TaskMachineEligibility, Assignment, MachineDowntime
from app.schemas import MachineOut, MachineCreate, MachineUpdate
from app.security import get_current_user, require_role

router = APIRouter(prefix="/machines", tags=["machines"])


def _cleanup_legacy_emma(db: Session) -> None:
    """
    One-time compatibility cleanup for old demo data that created a
    machine code 'Emma'. We remove that machine and any direct links so
    it no longer appears in the UI.
    """
    legacy = db.query(Machine).filter(Machine.machine_code == "Emma").first()
    if not legacy:
        return

    db.query(TaskMachineEligibility).filter(TaskMachineEligibility.machine_id == legacy.machine_id).delete()
    db.query(Assignment).filter(Assignment.machine_id == legacy.machine_id).delete()
    db.query(MachineDowntime).filter(MachineDowntime.machine_id == legacy.machine_id).delete()
    db.delete(legacy)
    db.commit()


@router.get("", response_model=List[MachineOut])
def list_machines(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    _cleanup_legacy_emma(db)
    return db.query(Machine).order_by(Machine.machine_code).all()


@router.get("/{machine_id}", response_model=MachineOut)
def get_machine(machine_id: int, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return db.query(Machine).filter(Machine.machine_id == machine_id).first()


@router.post("", response_model=MachineOut)
def create_machine(
    machine_in: MachineCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_role("factory_manager")),
):
    existing = db.query(Machine).filter(Machine.machine_code == machine_in.machine_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Machine code already exists")
    
    machine = Machine(
        machine_code=machine_in.machine_code,
        machine_name=machine_in.machine_name,
        machine_type=machine_in.machine_type,
        cost_per_hour=machine_in.cost_per_hour,
        status=machine_in.status or "online"
    )
    db.add(machine)
    db.commit()
    db.refresh(machine)
    return machine


@router.put("/{machine_id}", response_model=MachineOut)
def update_machine(
    machine_id: int,
    machine_in: MachineUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_role("factory_manager")),
):
    machine = db.query(Machine).filter(Machine.machine_id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
        
    if machine_in.machine_code is not None:
        existing = db.query(Machine).filter(
            Machine.machine_code == machine_in.machine_code,
            Machine.machine_id != machine_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Machine code already exists")
        machine.machine_code = machine_in.machine_code
        
    if machine_in.machine_name is not None:
        machine.machine_name = machine_in.machine_name
    if machine_in.machine_type is not None:
        machine.machine_type = machine_in.machine_type
    if machine_in.cost_per_hour is not None:
        machine.cost_per_hour = machine_in.cost_per_hour
    if machine_in.status is not None:
        machine.status = machine_in.status
        
    db.commit()
    db.refresh(machine)
    return machine


@router.delete("/{machine_id}")
def delete_machine(
    machine_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_role("factory_manager")),
):
    machine = db.query(Machine).filter(Machine.machine_id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    db.query(TaskMachineEligibility).filter(TaskMachineEligibility.machine_id == machine_id).delete()
    db.query(Assignment).filter(Assignment.machine_id == machine_id).delete()
    db.delete(machine)
    db.commit()
    return {"detail": "Machine deleted successfully"}
