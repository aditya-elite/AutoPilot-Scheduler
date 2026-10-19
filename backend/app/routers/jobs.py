from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Job, Task, TaskMachineEligibility
from app.schemas import JobOut, JobCreate, JobUpdate, TaskCreate
from app.security import get_current_user, require_role

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=List[JobOut])
def list_jobs(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return (
        db.query(Job)
        .options(joinedload(Job.tasks).joinedload(Task.eligible_machines))
        .order_by(Job.due_date)
        .all()
    )


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return (
        db.query(Job)
        .options(joinedload(Job.tasks).joinedload(Task.eligible_machines))
        .filter(Job.job_id == job_id)
        .first()
    )


@router.post("", response_model=JobOut)
def create_job(
    job_in: JobCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_role("factory_manager")),
):
    existing = db.query(Job).filter(Job.job_code == job_in.job_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Job code already exists")
        
    job = Job(
        job_code=job_in.job_code,
        description=job_in.description,
        priority_weight=job_in.priority_weight,
        profit_value=job_in.profit_value,
        due_date=job_in.due_date,
        material_available_minutes=job_in.material_available_minutes,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    if job_in.tasks:
        for t_in in job_in.tasks:
            task = Task(
                job_id=job.job_id,
                sequence_index=t_in.sequence_index,
                task_name=t_in.task_name,
                base_duration_minutes=t_in.base_duration_minutes,
                status="pending",
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            
            for elig_in in t_in.eligible_machines:
                elig = TaskMachineEligibility(
                    task_id=task.task_id,
                    machine_id=elig_in.machine_id,
                    processing_minutes=elig_in.processing_minutes,
                )
                db.add(elig)
        db.commit()
        db.refresh(job)
        
    return job


@router.put("/{job_id}", response_model=JobOut)
def update_job(
    job_id: int,
    job_in: JobUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_role("factory_manager")),
):
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job_in.job_code is not None:
        existing = db.query(Job).filter(
            Job.job_code == job_in.job_code,
            Job.job_id != job_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Job code already exists")
        job.job_code = job_in.job_code
        
    if job_in.description is not None:
        job.description = job_in.description
    if job_in.priority_weight is not None:
        job.priority_weight = job_in.priority_weight
    if job_in.profit_value is not None:
        job.profit_value = job_in.profit_value
    if job_in.due_date is not None:
        job.due_date = job_in.due_date
    if job_in.material_available_minutes is not None:
        job.material_available_minutes = job_in.material_available_minutes
        
    db.commit()
    db.refresh(job)
    return job


@router.put("/{job_id}/tasks", response_model=JobOut)
def update_job_tasks(
    job_id: int,
    tasks_in: List[TaskCreate],
    db: Session = Depends(get_db),
    _user=Depends(require_role("factory_manager")),
):
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    db.query(Task).filter(Task.job_id == job_id).delete()
    db.commit()
    
    for t_in in tasks_in:
        task = Task(
            job_id=job.job_id,
            sequence_index=t_in.sequence_index,
            task_name=t_in.task_name,
            base_duration_minutes=t_in.base_duration_minutes,
            status="pending",
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        
        for elig_in in t_in.eligible_machines:
            elig = TaskMachineEligibility(
                task_id=task.task_id,
                machine_id=elig_in.machine_id,
                processing_minutes=elig_in.processing_minutes,
            )
            db.add(elig)
            
    db.commit()
    db.refresh(job)
    return job


@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_role("factory_manager")),
):
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    db.delete(job)
    db.commit()
    return {"detail": "Job deleted successfully"}
