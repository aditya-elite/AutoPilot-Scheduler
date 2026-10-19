"""
Schedule router — the API surface behind the Gantt chart and the AI
Control Center.

Two important design choices:

1. `/schedule/optimize` returns immediately (202-style pattern) with a
   `run_id` and does the actual CP-SAT solve in a FastAPI
   BackgroundTask. CP-SAT is CPU-bound and can take many seconds; we
   never want to block the event loop or the caller's HTTP
   connection. (At real production scale, swap BackgroundTasks for a
   proper task queue like Celery/RQ/arq — the handler body barely
   changes, since it already treats "run the solve" as a decoupled
   unit of work.)

2. `/schedule/override` is how a manager's Gantt drag-and-drop lands.
   We do NOT just trust the client's placement — we re-validate it
   against the same constraints the solver enforces (machine
   availability/no-overlap, job precedence) and flag violations
   rather than silently accepting a broken schedule.
"""
from datetime import datetime, timezone, timedelta
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db, SessionLocal
from app.models import (
    Assignment, Task, OptimizationRun, AuditLog,
    OptimizationStatus, OptimizationGoal, AssignmentStatus, TaskStatus,
    Machine, MachineDowntime, TaskMachineEligibility, MachineStatus, DowntimeReason, Job,
)
from app.schemas import AssignmentOut, OptimizeRequest, OptimizationRunOut, ManualOverrideRequest, AssignmentStatusUpdate, RunLabelUpdate
from app.security import get_current_user, require_role
from app.repositories.scheduling_repo import (
    build_scheduling_problem,
    persist_solution,
    diagnose_scheduling_blockers,
)
from app.solver.job_shop_solver import FlexibleJobShopScheduler, OptimizationConfig
from app.websocket_manager import broadcast_sync
from pydantic import BaseModel

router = APIRouter(prefix="/schedule", tags=["schedule"])

class PresetRequest(BaseModel):
    preset_name: str

# Maps the UI's human-facing "AI Control Center" goal choice onto the
# solver's makespan/tardiness weight pair. This is the single spot
# that translates "business intent" into "optimization math".
_GOAL_WEIGHTS = {
    OptimizationGoal.minimize_makespan: (5, 1),
    OptimizationGoal.minimize_tardiness: (1, 8),
    OptimizationGoal.maximize_profit: (1, 10),   # profit-weighted tardiness dominates
    OptimizationGoal.balanced: (2, 4),
}


@router.get("/gantt", response_model=List[AssignmentOut])
def get_gantt(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    assignments = (
        db.query(Assignment)
        .options(
            joinedload(Assignment.task).joinedload(Task.job),
            joinedload(Assignment.task).joinedload(Task.eligible_machines),
            joinedload(Assignment.machine)
        )
        .filter(Assignment.status.in_([AssignmentStatus.planned, AssignmentStatus.confirmed, AssignmentStatus.in_progress, AssignmentStatus.completed]))
        .order_by(Assignment.scheduled_start)
        .all()
    )
    return [
        AssignmentOut(
            assignment_id=a.assignment_id,
            task_id=a.task_id,
            job_id=a.task.job.job_id,
            job_code=a.task.job.job_code,
            task_name=a.task.task_name,
            machine_id=a.machine_id,
            machine_code=a.machine.machine_code,
            scheduled_start=a.scheduled_start,
            scheduled_end=a.scheduled_end,
            status=a.status.value,
            is_manual_override=a.is_manual_override,
            violates_constraint=a.violates_constraint,
            violation_reason=a.violation_reason,
            eligible_machine_ids=[e.machine_id for e in a.task.eligible_machines],
        )
        for a in assignments
    ]


def _run_optimization_job(run_id: int, goal: OptimizationGoal, config: OptimizationConfig, triggered_by: str):
    """
    Executed in a background task/thread — has its OWN DB session
    since it outlives the request that triggered it.
    """
    db = SessionLocal()
    try:
        run = db.query(OptimizationRun).filter(OptimizationRun.run_id == run_id).first()
        run.status = OptimizationStatus.running
        run.started_at = datetime.now(timezone.utc)
        db.commit()

        blockers = diagnose_scheduling_blockers(db)
        if blockers:
            run.status = OptimizationStatus.failed
            run.error_message = " ; ".join(blockers)
            run.completed_at = datetime.now(timezone.utc)
            config_dict = dict(run.solver_config or {})
            config_dict["blockers"] = blockers
            run.solver_config = config_dict
            db.commit()
            # Push the failure too, not just successes — a re-solve
            # triggered by a breakdown/maintenance event has no caller
            # polling for its result, so without this the schedule
            # silently stays stale and nobody is told why.
            broadcast_sync("optimization_failed", {
                "run_id": run_id,
                "error_message": run.error_message,
                "blockers": blockers,
            })
            return

        problem = build_scheduling_problem(db)
        if not problem["jobs"]:
            run.status = OptimizationStatus.completed
            run.error_message = "No pending jobs to schedule."
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        scheduler = FlexibleJobShopScheduler(problem, config)
        result = scheduler.solve()

        run.status = OptimizationStatus.completed if result.assignments else OptimizationStatus.failed
        if not result.assignments:
            run.error_message = (
                f"No feasible schedule found (solver status: {result.status}). "
                "Check machine eligibility and offline machine constraints."
            )
        run.objective_value = result.objective_value
        run.makespan_minutes = result.makespan_minutes
        run.total_tardiness_minutes = result.total_tardiness_minutes
        run.completed_at = datetime.now(timezone.utc)

        # Calculate scheduling insights/explanations
        insights = []
        if result.assignments:
            from app.repositories.scheduling_repo import _minutes_from_origin
            
            # Map of job due date minutes
            job_due_minutes = {j.job_id: _minutes_from_origin(j.due_date) for j in db.query(Job).all()}
            
            # Group assignments by job_id
            job_assignments = {}
            for a in result.assignments:
                job_assignments.setdefault(a.job_id, []).append(a)
                
            for job_id, assigns in job_assignments.items():
                job = db.query(Job).filter(Job.job_id == job_id).first()
                if job:
                    completion_minute = max(a.end_minute for a in assigns)
                    due_date_minute = job_due_minutes.get(job_id, 999999)
                    
                    if completion_minute > due_date_minute:
                        latest_assign = max(assigns, key=lambda a: a.end_minute)
                        latest_task = db.query(Task).filter(Task.task_id == latest_assign.task_id).first()
                        latest_machine = db.query(Machine).filter(Machine.machine_id == latest_assign.machine_id).first()
                        
                        delay_amount = completion_minute - due_date_minute
                        insights.append(
                            f"Job {job.job_code} is delayed by {delay_amount}m. "
                            f"Its final operation '{latest_task.task_name}' completed late at minute {completion_minute} on {latest_machine.machine_code}."
                        )

        config_dict = dict(run.solver_config or {})
        config_dict["insights"] = insights
        run.solver_config = config_dict
        db.commit()

        if result.assignments:
            persist_solution(db, result, run_id, triggered_by)
            broadcast_sync("schedule_updated", {
                "run_id": run_id,
                "reason": "optimization_complete",
                "makespan_minutes": result.makespan_minutes,
                "insights": insights,
            })
        else:
            broadcast_sync("optimization_failed", {
                "run_id": run_id,
                "error_message": run.error_message,
                "blockers": [],
            })

    except Exception as exc:  # noqa: BLE001 — surface solver failures visibly, not silently
        run = db.query(OptimizationRun).filter(OptimizationRun.run_id == run_id).first()
        run.status = OptimizationStatus.failed
        run.error_message = str(exc)
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        broadcast_sync("optimization_failed", {
            "run_id": run_id,
            "error_message": str(exc),
            "blockers": [],
        })
    finally:
        db.close()


@router.post("/preset")
def apply_demo_preset(
    request: PresetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(require_role("factory_manager")),
):
    now = datetime.now(timezone.utc)
    
    if request.preset_name == "rush_order":
        existing = db.query(Job).filter(Job.job_code == "SO-2026-RUSH").first()
        if existing:
            raise HTTPException(status_code=400, detail="Rush order preset already active.")
            
        job = Job(
            job_code="SO-2026-RUSH",
            description="Urgent assembly order - VIP Client",
            priority_weight=10,
            profit_value=25000.0,
            due_date=now + timedelta(hours=5),
            status="pending",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        
        lathe1 = db.query(Machine).filter(Machine.machine_code == "LATHE-01").first()
        weld1 = db.query(Machine).filter(Machine.machine_code == "WELD-01").first()
        
        t1 = Task(job_id=job.job_id, sequence_index=0, task_name="Rush Prep Operation", base_duration_minutes=30, status="pending")
        db.add(t1)
        t2 = Task(job_id=job.job_id, sequence_index=1, task_name="Rush Assembly", base_duration_minutes=45, status="pending")
        db.add(t2)
        db.commit()
        db.refresh(t1)
        db.refresh(t2)
        
        if lathe1:
            db.add(TaskMachineEligibility(task_id=t1.task_id, machine_id=lathe1.machine_id, processing_minutes=30))
        if weld1:
            db.add(TaskMachineEligibility(task_id=t2.task_id, machine_id=weld1.machine_id, processing_minutes=45))
            
        db.commit()
        
        goal = OptimizationGoal.balanced
        mw, tw = _GOAL_WEIGHTS[goal]
        config = OptimizationConfig(makespan_weight=mw, tardiness_weight=tw, max_solve_seconds=15.0)
        
        run = OptimizationRun(
            triggered_by=user.user_id,
            goal=goal,
            status=OptimizationStatus.queued,
            solver_config={"trigger": "preset_rush_order"},
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        
        background_tasks.add_task(_run_optimization_job, run.run_id, goal, config, str(user.user_id))
        return {"detail": "Rush Job preset applied and solver triggered", "run_id": run.run_id}
        
    elif request.preset_name == "cnc_breakdown":
        cnc2 = db.query(Machine).filter(Machine.machine_code == "CNC-02").first()
        if not cnc2:
            raise HTTPException(status_code=404, detail="CNC-02 machine not found")
            
        cnc2.status = MachineStatus.offline
        
        downtime = MachineDowntime(
            machine_id=cnc2.machine_id,
            reason=DowntimeReason.unplanned_breakdown,
            start_time=now,
            end_time=now + timedelta(hours=4),
            notes="Simulated preset breakdown",
            created_by=user.user_id,
        )
        db.add(downtime)
        
        goal = OptimizationGoal.balanced
        mw, tw = _GOAL_WEIGHTS[goal]
        config = OptimizationConfig(makespan_weight=mw, tardiness_weight=tw, max_solve_seconds=15.0)
        
        run = OptimizationRun(
            triggered_by=user.user_id,
            goal=goal,
            status=OptimizationStatus.queued,
            solver_config={"trigger": "preset_cnc_breakdown", "machine_id": cnc2.machine_id},
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        
        background_tasks.add_task(_run_optimization_job, run.run_id, goal, config, str(user.user_id))
        return {"detail": "CNC-02 Breakdown preset applied and solver triggered", "run_id": run.run_id}
        
    elif request.preset_name == "reset":
        db.query(Assignment).delete()
        db.query(MachineDowntime).delete()
        db.query(TaskMachineEligibility).delete()
        db.query(Task).delete()
        db.query(Job).delete()
        db.query(OptimizationRun).delete()
        db.query(AuditLog).delete()

        # Always rebuild the standard factory machine set so reset is deterministic,
        # even if a previous preset replaced machines (e.g., employee_shift).
        db.query(Machine).delete()
        db.commit()

        machines = [
            Machine(machine_code="CNC-01", machine_name="CNC Mill #1", machine_type="CNC_MILL", cost_per_hour=45.0, status="online"),
            Machine(machine_code="CNC-02", machine_name="CNC Mill #2", machine_type="CNC_MILL", cost_per_hour=50.0, status="online"),
            Machine(machine_code="LATHE-01", machine_name="Lathe Station", machine_type="LATHE", cost_per_hour=40.0, status="online"),
            Machine(machine_code="WELD-01", machine_name="Welding Station", machine_type="WELDING_STATION", cost_per_hour=35.0, status="online"),
            Machine(machine_code="ASM-01", machine_name="Assembly Line #1", machine_type="ASSEMBLY_LINE", cost_per_hour=30.0, status="online"),
        ]
        for m in machines:
            db.add(m)
        db.commit()
        
        cnc1 = db.query(Machine).filter(Machine.machine_code == "CNC-01").first()
        cnc2 = db.query(Machine).filter(Machine.machine_code == "CNC-02").first()
        lathe1 = db.query(Machine).filter(Machine.machine_code == "LATHE-01").first()
        weld1 = db.query(Machine).filter(Machine.machine_code == "WELD-01").first()
        asm1 = db.query(Machine).filter(Machine.machine_code == "ASM-01").first()
        
        job_specs = [
            {
                "job_code": "SO-2026-1001", "description": "Bracket assembly — Acme Corp",
                "priority_weight": 9, "profit_value": 12000.0, "due_date": now + timedelta(hours=10),
                "tasks": [
                    ("Rough mill housing", 45, [(cnc1, 45), (cnc2, 50)]),
                    ("Lathe finish shaft", 30, [(lathe1, 30)]),
                    ("Weld sub-assembly", 40, [(weld1, 40)]),
                ],
            },
            {
                "job_code": "SO-2026-1002", "description": "Gearbox housing — Nordic Industries",
                "priority_weight": 6, "profit_value": 6500.0, "due_date": now + timedelta(hours=18),
                "tasks": [
                    ("Mill housing", 60, [(cnc2, 60), (cnc1, 65)]),
                    ("Assemble unit", 35, [(asm1, 35)]),
                ],
            },
            {
                "job_code": "SO-2026-1003", "description": "Custom fixture — rapid turnaround",
                "priority_weight": 10, "profit_value": 20000.0, "due_date": now + timedelta(hours=6),
                "tasks": [
                    ("Lathe prep", 25, [(lathe1, 25)]),
                    ("Weld frame", 50, [(weld1, 50)]),
                    ("Final assembly", 20, [(asm1, 20)]),
                ],
            },
            {
                "job_code": "SO-2026-1004", "description": "Standard bracket batch",
                "priority_weight": 3, "profit_value": 1800.0, "due_date": now + timedelta(hours=30),
                "tasks": [
                    ("Mill batch", 90, [(cnc1, 90), (cnc2, 95)]),
                ],
            },
        ]
        
        for spec in job_specs:
            job = Job(
                job_code=spec["job_code"], description=spec["description"],
                priority_weight=spec["priority_weight"], profit_value=spec["profit_value"],
                due_date=spec["due_date"], status="pending",
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            
            for idx, (task_name, base_duration, machine_options) in enumerate(spec["tasks"]):
                task = Task(job_id=job.job_id, sequence_index=idx, task_name=task_name, base_duration_minutes=base_duration)
                db.add(task)
                db.commit()
                db.refresh(task)
                
                for machine, minutes in machine_options:
                    if machine:
                        db.add(TaskMachineEligibility(task_id=task.task_id, machine_id=machine.machine_id, processing_minutes=minutes))
            db.commit()
            
        goal = OptimizationGoal.balanced
        mw, tw = _GOAL_WEIGHTS[goal]
        config = OptimizationConfig(makespan_weight=mw, tardiness_weight=tw, max_solve_seconds=15.0)

        run = OptimizationRun(
            triggered_by=user.user_id,
            goal=goal,
            status=OptimizationStatus.queued,
            solver_config={"trigger": "preset_reset"},
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        background_tasks.add_task(_run_optimization_job, run.run_id, goal, config, str(user.user_id))
        return {"detail": "Database reset and all tasks re-optimized", "run_id": run.run_id}
        
    elif request.preset_name == "job_shop":
        db.query(Assignment).delete()
        db.query(MachineDowntime).delete()
        db.query(TaskMachineEligibility).delete()
        db.query(Task).delete()
        db.query(Job).delete()
        db.query(OptimizationRun).delete()
        db.query(AuditLog).delete()
        
        # Restore standard machines if deleted by employee shift
        db.query(Machine).delete()
        db.commit()
        
        machines = [
            Machine(machine_code="CNC-01", machine_name="CNC Mill #1", machine_type="CNC_MILL", cost_per_hour=45.0, status="online"),
            Machine(machine_code="CNC-02", machine_name="CNC Mill #2", machine_type="CNC_MILL", cost_per_hour=50.0, status="online"),
            Machine(machine_code="LATHE-01", machine_name="Lathe Station", machine_type="LATHE", cost_per_hour=40.0, status="online"),
            Machine(machine_code="WELD-01", machine_name="Welding Station", machine_type="WELDING_STATION", cost_per_hour=35.0, status="online"),
            Machine(machine_code="ASM-01", machine_name="Assembly Line #1", machine_type="ASSEMBLY_LINE", cost_per_hour=30.0, status="online"),
        ]
        for m in machines:
            db.add(m)
        db.commit()
        
        cnc1 = db.query(Machine).filter(Machine.machine_code == "CNC-01").first()
        cnc2 = db.query(Machine).filter(Machine.machine_code == "CNC-02").first()
        lathe1 = db.query(Machine).filter(Machine.machine_code == "LATHE-01").first()
        weld1 = db.query(Machine).filter(Machine.machine_code == "WELD-01").first()
        asm1 = db.query(Machine).filter(Machine.machine_code == "ASM-01").first()
        
        job_specs = [
            {
                "job_code": "SO-JSP-01", "description": "Traditional Job Shop Order 1",
                "priority_weight": 7, "profit_value": 8000.0, "due_date": now + timedelta(hours=8),
                "tasks": [
                    ("Rough Milling", 40, [(cnc1, 40)]),
                    ("Lathe Turning", 30, [(lathe1, 30)]),
                    ("Assembly Work", 25, [(asm1, 25)]),
                ],
            },
            {
                "job_code": "SO-JSP-02", "description": "Traditional Job Shop Order 2",
                "priority_weight": 8, "profit_value": 9500.0, "due_date": now + timedelta(hours=6),
                "tasks": [
                    ("Shaft Lathe", 45, [(lathe1, 45)]),
                    ("Frame Welding", 35, [(weld1, 35)]),
                    ("Finish Milling", 30, [(cnc2, 30)]),
                ],
            },
        ]
        
        for spec in job_specs:
            job = Job(
                job_code=spec["job_code"], description=spec["description"],
                priority_weight=spec["priority_weight"], profit_value=spec["profit_value"],
                due_date=spec["due_date"], status="pending",
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            
            for idx, (task_name, base_duration, machine_options) in enumerate(spec["tasks"]):
                task = Task(job_id=job.job_id, sequence_index=idx, task_name=task_name, base_duration_minutes=base_duration)
                db.add(task)
                db.commit()
                db.refresh(task)
                
                for machine, minutes in machine_options:
                    if machine:
                        db.add(TaskMachineEligibility(task_id=task.task_id, machine_id=machine.machine_id, processing_minutes=minutes))
            db.commit()
            
        goal = OptimizationGoal.balanced
        mw, tw = _GOAL_WEIGHTS[goal]
        config = OptimizationConfig(makespan_weight=mw, tardiness_weight=tw, max_solve_seconds=15.0)
        
        run = OptimizationRun(
            triggered_by=user.user_id,
            goal=goal,
            status=OptimizationStatus.queued,
            solver_config={"trigger": "preset_job_shop"},
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        
        background_tasks.add_task(_run_optimization_job, run.run_id, goal, config, str(user.user_id))
        return {"detail": "Traditional Job Shop preset applied and solver triggered", "run_id": run.run_id}

    elif request.preset_name == "flow_shop":
        db.query(Assignment).delete()
        db.query(MachineDowntime).delete()
        db.query(TaskMachineEligibility).delete()
        db.query(Task).delete()
        db.query(Job).delete()
        db.query(OptimizationRun).delete()
        db.query(AuditLog).delete()
        
        # Restore standard machines if deleted by employee shift
        db.query(Machine).delete()
        db.commit()
        
        machines = [
            Machine(machine_code="CNC-01", machine_name="CNC Mill #1", machine_type="CNC_MILL", cost_per_hour=45.0, status="online"),
            Machine(machine_code="CNC-02", machine_name="CNC Mill #2", machine_type="CNC_MILL", cost_per_hour=50.0, status="online"),
            Machine(machine_code="LATHE-01", machine_name="Lathe Station", machine_type="LATHE", cost_per_hour=40.0, status="online"),
            Machine(machine_code="WELD-01", machine_name="Welding Station", machine_type="WELDING_STATION", cost_per_hour=35.0, status="online"),
            Machine(machine_code="ASM-01", machine_name="Assembly Line #1", machine_type="ASSEMBLY_LINE", cost_per_hour=30.0, status="online"),
        ]
        for m in machines:
            db.add(m)
        db.commit()
        
        cnc1 = db.query(Machine).filter(Machine.machine_code == "CNC-01").first()
        lathe1 = db.query(Machine).filter(Machine.machine_code == "LATHE-01").first()
        asm1 = db.query(Machine).filter(Machine.machine_code == "ASM-01").first()
        
        job_specs = [
            {
                "job_code": "SO-FSP-01", "description": "Flow Shop Part A",
                "priority_weight": 6, "profit_value": 5000.0, "due_date": now + timedelta(hours=10),
                "tasks": [
                    ("Milling A", 30, [(cnc1, 30)]),
                    ("Lathe A", 20, [(lathe1, 20)]),
                    ("Assembly A", 25, [(asm1, 25)]),
                ],
            },
            {
                "job_code": "SO-FSP-02", "description": "Flow Shop Part B",
                "priority_weight": 7, "profit_value": 7500.0, "due_date": now + timedelta(hours=12),
                "tasks": [
                    ("Milling B", 40, [(cnc1, 40)]),
                    ("Lathe B", 30, [(lathe1, 30)]),
                    ("Assembly B", 15, [(asm1, 15)]),
                ],
            },
            {
                "job_code": "SO-FSP-03", "description": "Flow Shop Part C",
                "priority_weight": 5, "profit_value": 4000.0, "due_date": now + timedelta(hours=15),
                "tasks": [
                    ("Milling C", 25, [(cnc1, 25)]),
                    ("Lathe C", 35, [(lathe1, 35)]),
                    ("Assembly C", 30, [(asm1, 30)]),
                ],
            },
        ]
        
        for spec in job_specs:
            job = Job(
                job_code=spec["job_code"], description=spec["description"],
                priority_weight=spec["priority_weight"], profit_value=spec["profit_value"],
                due_date=spec["due_date"], status="pending",
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            
            for idx, (task_name, base_duration, machine_options) in enumerate(spec["tasks"]):
                task = Task(job_id=job.job_id, sequence_index=idx, task_name=task_name, base_duration_minutes=base_duration)
                db.add(task)
                db.commit()
                db.refresh(task)
                
                for machine, minutes in machine_options:
                    if machine:
                        db.add(TaskMachineEligibility(task_id=task.task_id, machine_id=machine.machine_id, processing_minutes=minutes))
            db.commit()
            
        goal = OptimizationGoal.balanced
        mw, tw = _GOAL_WEIGHTS[goal]
        config = OptimizationConfig(makespan_weight=mw, tardiness_weight=tw, max_solve_seconds=15.0)
        
        run = OptimizationRun(
            triggered_by=user.user_id,
            goal=goal,
            status=OptimizationStatus.queued,
            solver_config={"trigger": "preset_flow_shop"},
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        
        background_tasks.add_task(_run_optimization_job, run.run_id, goal, config, str(user.user_id))
        return {"detail": "Flow Shop preset applied and solver triggered", "run_id": run.run_id}

    elif request.preset_name == "employee_shift":
        db.query(Assignment).delete()
        db.query(MachineDowntime).delete()
        db.query(TaskMachineEligibility).delete()
        db.query(Task).delete()
        db.query(Job).delete()
        db.query(OptimizationRun).delete()
        db.query(AuditLog).delete()
        
        db.query(Machine).delete()
        db.commit()
        
        employees = [
            Machine(machine_code="Alice", machine_name="Alice (Welder)", machine_type="WELDING_STATION", cost_per_hour=35.0, status="online"),
            Machine(machine_code="Bob", machine_name="Bob (Machinist)", machine_type="CNC_MILL", cost_per_hour=40.0, status="online"),
            Machine(machine_code="Charlie", machine_name="Charlie (Assembler)", machine_type="ASSEMBLY_LINE", cost_per_hour=25.0, status="online"),
            Machine(machine_code="David", machine_name="David (Inspector)", machine_type="QUALITY_CHECK", cost_per_hour=30.0, status="online"),
        ]
        for emp in employees:
            db.add(emp)
        db.commit()
        
        alice = db.query(Machine).filter(Machine.machine_code == "Alice").first()
        bob = db.query(Machine).filter(Machine.machine_code == "Bob").first()
        charlie = db.query(Machine).filter(Machine.machine_code == "Charlie").first()
        david = db.query(Machine).filter(Machine.machine_code == "David").first()
        
        job_specs = [
            {
                "job_code": "Monday-Shift", "description": "Monday Shift Coverage",
                "priority_weight": 5, "profit_value": 10000.0, "due_date": now + timedelta(hours=24),
                "tasks": [
                    ("CNC Machining Duty", 480, [(bob, 480), (alice, 600), (charlie, 600)]),
                    ("Welding Duty", 480, [(alice, 480), (bob, 600)]),
                    ("Assembly Line Duty", 480, [(charlie, 480), (david, 540), (bob, 600)]),
                    ("Packaging Duty", 480, [(charlie, 480), (bob, 540), (david, 600)]),
                ],
            },
            {
                "job_code": "Tuesday-Shift", "description": "Tuesday Shift Coverage",
                "priority_weight": 5, "profit_value": 10000.0, "due_date": now + timedelta(hours=48),
                "tasks": [
                    ("CNC Machining Duty", 480, [(bob, 480), (alice, 600)]),
                    ("Assembly Line Duty", 480, [(charlie, 480), (david, 540)]),
                    ("Quality Check Duty", 480, [(david, 480), (bob, 600)]),
                    ("Packaging Duty", 480, [(charlie, 480), (bob, 560)]),
                ],
            },
        ]
        
        for spec in job_specs:
            job = Job(
                job_code=spec["job_code"], description=spec["description"],
                priority_weight=spec["priority_weight"], profit_value=spec["profit_value"],
                due_date=spec["due_date"], status="pending",
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            
            for idx, (task_name, duration, machine_options) in enumerate(spec["tasks"]):
                task = Task(job_id=job.job_id, sequence_index=idx, task_name=task_name, base_duration_minutes=duration)
                db.add(task)
                db.commit()
                db.refresh(task)
                
                for machine, minutes in machine_options:
                    if machine:
                        db.add(TaskMachineEligibility(task_id=task.task_id, machine_id=machine.machine_id, processing_minutes=minutes))
            db.commit()
            
        goal = OptimizationGoal.balanced
        mw, tw = _GOAL_WEIGHTS[goal]
        config = OptimizationConfig(makespan_weight=mw, tardiness_weight=tw, max_solve_seconds=15.0)
        
        run = OptimizationRun(
            triggered_by=user.user_id,
            goal=goal,
            status=OptimizationStatus.queued,
            solver_config={"trigger": "preset_employee_shift"},
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        
        background_tasks.add_task(_run_optimization_job, run.run_id, goal, config, str(user.user_id))
        return {"detail": "Employee Shift Scheduling preset applied and solver triggered", "run_id": run.run_id}

    elif request.preset_name == "resource_allocation":
        db.query(Assignment).delete()
        db.query(MachineDowntime).delete()
        db.query(TaskMachineEligibility).delete()
        db.query(Task).delete()
        db.query(Job).delete()
        db.query(OptimizationRun).delete()
        db.query(AuditLog).delete()
        
        db.query(Machine).delete()
        db.commit()
        
        machines = [
            Machine(machine_code="CNC-01", machine_name="CNC Mill #1", machine_type="CNC_MILL", cost_per_hour=45.0, status="online"),
            Machine(machine_code="CNC-02", machine_name="CNC Mill #2", machine_type="CNC_MILL", cost_per_hour=50.0, status="online"),
            Machine(machine_code="LATHE-01", machine_name="Lathe Station", machine_type="LATHE", cost_per_hour=40.0, status="online"),
            Machine(machine_code="WELD-01", machine_name="Welding Station", machine_type="WELDING_STATION", cost_per_hour=35.0, status="online"),
            Machine(machine_code="ASM-01", machine_name="Assembly Line #1", machine_type="ASSEMBLY_LINE", cost_per_hour=30.0, status="online"),
        ]
        for m in machines:
            db.add(m)
        db.commit()
        
        cnc1 = db.query(Machine).filter(Machine.machine_code == "CNC-01").first()
        cnc2 = db.query(Machine).filter(Machine.machine_code == "CNC-02").first()
        lathe1 = db.query(Machine).filter(Machine.machine_code == "LATHE-01").first()
        weld1 = db.query(Machine).filter(Machine.machine_code == "WELD-01").first()
        asm1 = db.query(Machine).filter(Machine.machine_code == "ASM-01").first()
        
        job_specs = [
            {"job_code": "Order-A", "desc": "Milling job A", "tasks": [("Milling A", 50, [(cnc1, 50), (cnc2, 55)])]},
            {"job_code": "Order-B", "desc": "Milling job B", "tasks": [("Milling B", 70, [(cnc1, 70), (cnc2, 65)])]},
            {"job_code": "Order-C", "desc": "Welding job C", "tasks": [("Welding C", 40, [(weld1, 40), (asm1, 60)])]},
            {"job_code": "Order-D", "desc": "Lathe job D", "tasks": [("Turning D", 30, [(lathe1, 30), (cnc1, 45)])]},
            {"job_code": "Order-E", "desc": "Assembly job E", "tasks": [("Assembly E", 45, [(asm1, 45), (weld1, 60)])]},
        ]
        
        for spec in job_specs:
            job = Job(
                job_code=spec["job_code"], description=spec["desc"],
                priority_weight=5, profit_value=5000.0,
                due_date=now + timedelta(hours=12), status="pending",
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            
            for task_name, duration, machine_options in spec["tasks"]:
                task = Task(job_id=job.job_id, sequence_index=0, task_name=task_name, base_duration_minutes=duration)
                db.add(task)
                db.commit()
                db.refresh(task)
                
                for machine, minutes in machine_options:
                    if machine:
                        db.add(TaskMachineEligibility(task_id=task.task_id, machine_id=machine.machine_id, processing_minutes=minutes))
            db.commit()
            
        goal = OptimizationGoal.balanced
        mw, tw = _GOAL_WEIGHTS[goal]
        config = OptimizationConfig(makespan_weight=mw, tardiness_weight=tw, max_solve_seconds=15.0)
        
        run = OptimizationRun(
            triggered_by=user.user_id,
            goal=goal,
            status=OptimizationStatus.queued,
            solver_config={"trigger": "preset_resource_allocation"},
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        
        background_tasks.add_task(_run_optimization_job, run.run_id, goal, config, str(user.user_id))
        return {"detail": "Resource Allocation preset applied and solver triggered", "run_id": run.run_id}

    else:
        raise HTTPException(status_code=400, detail="Invalid preset name")

@router.post("/optimize", response_model=OptimizationRunOut)
def trigger_optimize(
    request: OptimizeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(require_role("factory_manager")),
):
    goal = OptimizationGoal(request.goal)
    default_makespan_w, default_tardiness_w = _GOAL_WEIGHTS[goal]

    config = OptimizationConfig(
        makespan_weight=request.makespan_weight or default_makespan_w,
        tardiness_weight=request.tardiness_weight or default_tardiness_w,
        max_solve_seconds=request.max_solve_seconds or 20.0,
    )

    run = OptimizationRun(
        triggered_by=user.user_id,
        goal=goal,
        status=OptimizationStatus.queued,
        solver_config={
            "makespan_weight": config.makespan_weight,
            "tardiness_weight": config.tardiness_weight,
            "max_solve_seconds": config.max_solve_seconds,
        },
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(_run_optimization_job, run.run_id, goal, config, str(user.user_id))

    return OptimizationRunOut.model_validate(run)


@router.get("/runs/{run_id}", response_model=OptimizationRunOut)
def get_run_status(run_id: int, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    run = db.query(OptimizationRun).filter(OptimizationRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Optimization run not found")
    return OptimizationRunOut.model_validate(run)


@router.post("/override", response_model=AssignmentOut)
def manual_override(
    request: ManualOverrideRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("factory_manager")),
):
    """
    Handles a manager's Gantt drag-and-drop. We move the assignment,
    then re-validate it against the two constraints the solver itself
    enforces: (a) no overlap on the target machine, (b) job
    precedence (this task cannot start before its predecessor ends).
    Violations are FLAGGED, not silently blocked — a manager may have
    a real-world reason (e.g. an expedite) to accept a flagged
    schedule, but they see the risk.
    """
    assignment = db.query(Assignment).filter(Assignment.assignment_id == request.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    task = db.query(Task).options(joinedload(Task.eligible_machines)).filter(Task.task_id == assignment.task_id).first()
    duration = assignment.scheduled_end - assignment.scheduled_start
    new_end = request.new_start + duration

    old_value = {
        "machine_id": assignment.machine_id,
        "scheduled_start": str(assignment.scheduled_start),
        "scheduled_end": str(assignment.scheduled_end),
    }

    assignment.machine_id = request.new_machine_id
    assignment.scheduled_start = request.new_start
    assignment.scheduled_end = new_end
    assignment.is_manual_override = True

    violations = []

    # (a) Overlap check on the destination machine.
    overlapping = (
        db.query(Assignment)
        .filter(
            Assignment.machine_id == request.new_machine_id,
            Assignment.assignment_id != assignment.assignment_id,
            Assignment.status.in_([AssignmentStatus.planned, AssignmentStatus.confirmed]),
            Assignment.scheduled_start < new_end,
            Assignment.scheduled_end > request.new_start,
        )
        .first()
    )
    if overlapping:
        violations.append(f"Overlaps with assignment #{overlapping.assignment_id} on the same machine.")

    # (b) Precedence check within the job.
    prior_task = (
        db.query(Task)
        .filter(Task.job_id == task.job_id, Task.sequence_index == task.sequence_index - 1)
        .first()
    )
    if prior_task:
        prior_assignment = (
            db.query(Assignment)
            .filter(Assignment.task_id == prior_task.task_id, Assignment.status.in_([AssignmentStatus.planned, AssignmentStatus.confirmed]))
            .order_by(Assignment.scheduled_end.desc())
            .first()
        )
        if prior_assignment and prior_assignment.scheduled_end > request.new_start:
            violations.append("Starts before its predecessor task finishes.")

    # (c) Machine status check (cannot override on offline machine)
    target_machine = db.query(Machine).filter(Machine.machine_id == request.new_machine_id).first()
    if target_machine and target_machine.status == MachineStatus.offline:
        violations.append(f"Machine {target_machine.machine_code} is offline.")

    assignment.violates_constraint = bool(violations)
    assignment.violation_reason = "; ".join(violations) if violations else None

    db.add(AuditLog(
        entity_type="assignment",
        entity_id=assignment.assignment_id,
        action="override",
        old_value=old_value,
        new_value={"machine_id": assignment.machine_id, "scheduled_start": str(assignment.scheduled_start)},
        changed_by=user.user_id,
    ))
    db.commit()
    db.refresh(assignment)

    broadcast_sync("schedule_updated", {
        "reason": "manual_override",
        "assignment_id": assignment.assignment_id,
        "violates_constraint": assignment.violates_constraint,
    })

    return AssignmentOut(
        assignment_id=assignment.assignment_id,
        task_id=assignment.task_id,
        job_id=task.job_id,
        job_code=task.job.job_code,
        task_name=task.task_name,
        machine_id=assignment.machine_id,
        machine_code=assignment.machine.machine_code,
        scheduled_start=assignment.scheduled_start,
        scheduled_end=assignment.scheduled_end,
        status=assignment.status.value,
        is_manual_override=assignment.is_manual_override,
        violates_constraint=assignment.violates_constraint,
        violation_reason=assignment.violation_reason,
        eligible_machine_ids=[e.machine_id for e in task.eligible_machines],
    )


@router.patch("/assignments/{assignment_id}/status", response_model=AssignmentOut)
def update_assignment_status(
    assignment_id: int,
    request: AssignmentStatusUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Used by the Operator's shift-queue checklist. Any authenticated
    user (operator or manager) can mark their own in-progress task as
    'in_progress' or 'completed' — this is intentionally a lighter
    permission bar than the manager-only override/optimize endpoints,
    since it reflects real-world shop-floor work happening, not a
    schedule change.
    """
    if request.status not in ("in_progress", "completed"):
        raise HTTPException(status_code=400, detail="status must be 'in_progress' or 'completed'")

    assignment = (
        db.query(Assignment)
        .options(
            joinedload(Assignment.task).joinedload(Task.job),
            joinedload(Assignment.task).joinedload(Task.eligible_machines),
            joinedload(Assignment.machine)
        )
        .filter(Assignment.assignment_id == assignment_id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    now = datetime.now(timezone.utc)

    old_status = assignment.status.value
    if request.status == "in_progress":
        assignment.status = AssignmentStatus.in_progress
        assignment.actual_start = assignment.actual_start or now
        assignment.task.status = TaskStatus.in_progress
    else:
        assignment.status = AssignmentStatus.completed
        assignment.actual_end = now
        assignment.task.status = TaskStatus.completed

    db.add(AuditLog(
        entity_type="assignment",
        entity_id=assignment.assignment_id,
        action="update",
        old_value={"status": old_status},
        new_value={"status": assignment.status.value},
        changed_by=user.user_id,
    ))
    db.commit()
    db.refresh(assignment)

    broadcast_sync("schedule_updated", {"reason": "status_update", "assignment_id": assignment_id})

    return AssignmentOut(
        assignment_id=assignment.assignment_id,
        task_id=assignment.task_id,
        job_id=assignment.task.job_id,
        job_code=assignment.task.job.job_code,
        task_name=assignment.task.task_name,
        machine_id=assignment.machine_id,
        machine_code=assignment.machine.machine_code,
        scheduled_start=assignment.scheduled_start,
        scheduled_end=assignment.scheduled_end,
        status=assignment.status.value,
        is_manual_override=assignment.is_manual_override,
        violates_constraint=assignment.violates_constraint,
        violation_reason=assignment.violation_reason,
        eligible_machine_ids=[e.machine_id for e in assignment.task.eligible_machines],
    )


@router.get("/runs", response_model=List[OptimizationRunOut])
def list_optimization_runs(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return db.query(OptimizationRun).order_by(OptimizationRun.created_at.desc()).all()


@router.put("/runs/{run_id}/label", response_model=OptimizationRunOut)
def label_optimization_run(
    run_id: int,
    request: RunLabelUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_role("factory_manager")),
):
    run = db.query(OptimizationRun).filter(OptimizationRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Optimization run not found")
        
    config = dict(run.solver_config or {})
    config["label"] = request.label
    
    from sqlalchemy.orm.attributes import flag_modified
    run.solver_config = config
    flag_modified(run, "solver_config")
    
    db.commit()
    db.refresh(run)
    return run


@router.get("/gantt/{run_id}", response_model=List[AssignmentOut])
def get_gantt_for_run(run_id: int, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    assignments = (
        db.query(Assignment)
        .options(
            joinedload(Assignment.task).joinedload(Task.job),
            joinedload(Assignment.task).joinedload(Task.eligible_machines),
            joinedload(Assignment.machine)
        )
        .filter(Assignment.optimization_run_id == run_id)
        .order_by(Assignment.scheduled_start)
        .all()
    )
    return [
        AssignmentOut(
            assignment_id=a.assignment_id,
            task_id=a.task_id,
            job_id=a.task.job.job_id,
            job_code=a.task.job.job_code,
            task_name=a.task.task_name,
            machine_id=a.machine_id,
            machine_code=a.machine.machine_code,
            scheduled_start=a.scheduled_start,
            scheduled_end=a.scheduled_end,
            status=a.status.value,
            is_manual_override=a.is_manual_override,
            violates_constraint=a.violates_constraint,
            violation_reason=a.violation_reason,
            eligible_machine_ids=[e.machine_id for e in a.task.eligible_machines],
        )
        for a in assignments
    ]
