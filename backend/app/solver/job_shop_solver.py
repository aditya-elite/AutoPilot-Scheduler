"""
AutoPilot Scheduler — Phase 1 Baseline Optimization Engine
===========================================================

This module implements a FLEXIBLE JOB-SHOP scheduling solver using
Google OR-Tools' CP-SAT constraint programming solver.

Why "flexible" job-shop, specifically?
---------------------------------------
In a classic job-shop problem, each task can only run on ONE fixed
machine. Our factory schema (see schema.sql) allows a task to be
eligible on SEVERAL machines, each with its own processing time
(task_machine_eligibility table). The solver must therefore decide
TWO things simultaneously for every task:

    1. WHICH eligible machine will run it
    2. WHEN it will start on that machine

This is what lets the AI route around a broken machine automatically
(the "Breakdown Simulator") — if a machine is marked offline, the
solver simply never assigns anything to it.

How this file is organized
---------------------------
1. Data contracts (typed dicts) that mirror the Postgres schema.
2. `load_scheduling_data()` — a stand-in for the FastAPI/SQLAlchemy
   query layer. In production this function is replaced by a
   repository call; the CONTRACT (the shape of the dict) stays the
   same, which is the whole point of separating this module from the
   database layer.
3. `FlexibleJobShopScheduler` — builds and solves the CP-SAT model.
4. `__main__` block — a runnable demo with mock data.

Run it directly with:  python job_shop_solver.py
"""

from __future__ import annotations

import collections
import dataclasses
from typing import Dict, List, Optional, TypedDict

from ortools.sat.python import cp_model


# =====================================================================
# 1. DATA CONTRACTS
#    These TypedDicts describe exactly what the FastAPI layer must
#    hand to this solver. Keeping this as a narrow, explicit contract
#    means the solver has ZERO knowledge of SQLAlchemy, FastAPI, or
#    the database — it is pure optimization logic and is trivially
#    unit-testable.
# =====================================================================

class MachineDowntimeWindow(TypedDict):
    start_minute: int   # minutes from the scheduling horizon origin
    end_minute: int


class MachineOption(TypedDict):
    machine_id: int
    processing_minutes: int


class TaskSpec(TypedDict):
    task_id: int
    sequence_index: int              # order within the job (0-based)
    eligible_machines: List[MachineOption]


class JobSpec(TypedDict):
    job_id: int
    due_date_minute: int             # due date, expressed as minutes from horizon origin
    priority_weight: int             # 1-10, higher = more important
    profit_value: float              # used when optimization goal is "maximize_profit"
    material_available_minute: int   # release date when raw materials arrive
    tasks: List[TaskSpec]            # must already be sorted by sequence_index


class SchedulingProblem(TypedDict):
    jobs: List[JobSpec]
    machine_ids: List[int]
    machine_downtime: Dict[int, List[MachineDowntimeWindow]]  # machine_id -> forbidden windows


@dataclasses.dataclass
class OptimizationConfig:
    """Tunable knobs exposed to the AI Control Center in the UI."""
    # Relative weighting between finishing everything fast (makespan)
    # vs. not missing due dates (tardiness). The UI's "Maximize Speed"
    # vs "Maximize Profit/On-Time" slider maps directly onto these.
    makespan_weight: int = 1
    tardiness_weight: int = 5
    max_solve_seconds: float = 30.0
    num_search_workers: int = 8


@dataclasses.dataclass
class TaskAssignment:
    """One row of solver output — maps 1:1 onto the `assignments` table."""
    task_id: int
    job_id: int
    machine_id: int
    start_minute: int
    end_minute: int


@dataclasses.dataclass
class SolveResult:
    status: str
    makespan_minutes: Optional[int]
    total_tardiness_minutes: Optional[int]
    objective_value: Optional[float]
    assignments: List[TaskAssignment]


# =====================================================================
# 2. DATA LOADING (stand-in for the real repository/query layer)
#    In production, this is replaced by a function in
#    `app/repositories/scheduling_repo.py` that queries Postgres via
#    SQLAlchemy and returns the exact same SchedulingProblem shape.
#    Keeping the shape identical means this solver file never changes
#    when the persistence layer changes.
# =====================================================================

def load_scheduling_data() -> SchedulingProblem:
    """
    Returns a small mock flexible job-shop problem: 3 jobs, each with
    2-3 tasks, across 3 machines, with one machine partially blocked
    by planned maintenance — mirroring what a real query against
    `jobs`, `tasks`, `task_machine_eligibility`, and `machine_downtime`
    would return.
    """
    return {
        "machine_ids": [1, 2, 3],
        "machine_downtime": {
            # Machine 2 is down for planned maintenance from minute 60 to 90.
            2: [{"start_minute": 60, "end_minute": 90}],
        },
        "jobs": [
            {
                "job_id": 101,
                "due_date_minute": 240,
                "priority_weight": 8,
                "profit_value": 5000.0,
                "material_available_minute": 0,
                "tasks": [
                    {
                        "task_id": 1001,
                        "sequence_index": 0,
                        "eligible_machines": [
                            {"machine_id": 1, "processing_minutes": 40},
                            {"machine_id": 2, "processing_minutes": 35},
                        ],
                    },
                    {
                        "task_id": 1002,
                        "sequence_index": 1,
                        "eligible_machines": [
                            {"machine_id": 3, "processing_minutes": 30},
                        ],
                    },
                ],
            },
            {
                "job_id": 102,
                "due_date_minute": 200,
                "priority_weight": 5,
                "profit_value": 2000.0,
                "material_available_minute": 30, # raw materials arrive at minute 30
                "tasks": [
                    {
                        "task_id": 1003,
                        "sequence_index": 0,
                        "eligible_machines": [
                            {"machine_id": 2, "processing_minutes": 50},
                            {"machine_id": 1, "processing_minutes": 55},
                        ],
                    },
                    {
                        "task_id": 1004,
                        "sequence_index": 1,
                        "eligible_machines": [
                            {"machine_id": 3, "processing_minutes": 25},
                        ],
                    },
                    {
                        "task_id": 1005,
                        "sequence_index": 2,
                        "eligible_machines": [
                            {"machine_id": 1, "processing_minutes": 20},
                            {"machine_id": 2, "processing_minutes": 20},
                        ],
                    },
                ],
            },
            {
                "job_id": 103,
                "due_date_minute": 180,
                "priority_weight": 10,
                "profit_value": 9000.0,
                "material_available_minute": 0,
                "tasks": [
                    {
                        "task_id": 1006,
                        "sequence_index": 0,
                        "eligible_machines": [
                            {"machine_id": 3, "processing_minutes": 45},
                        ],
                    },
                    {
                        "task_id": 1007,
                        "sequence_index": 1,
                        "eligible_machines": [
                            {"machine_id": 1, "processing_minutes": 35},
                            {"machine_id": 2, "processing_minutes": 40},
                        ],
                    },
                ],
            },
        ],
    }


# =====================================================================
# 3. THE SOLVER
# =====================================================================

class FlexibleJobShopScheduler:
    """
    Builds and solves a flexible job-shop CP-SAT model.

    Modeling approach (the classic OR-Tools "optional interval"
    pattern for flexible job-shop):

      For every task T with N eligible machines, we create N OPTIONAL
      interval variables — one per candidate machine — each guarded
      by a boolean "presence" literal. Exactly one of those N
      literals must be true (the task runs on exactly one machine).
      Only the "present" interval actually occupies time on its
      machine; the others are logically inert.

      Constraints:
        (a) Exactly-one machine chosen per task.
        (b) Precedence: task[i] must finish before task[i+1] starts,
            within the same job.
        (c) No-overlap per machine across ALL tasks that could run on
            it (including fixed "downtime" intervals, which are
            always-present intervals with no choice — they simply
            block time on that machine).

      Objective:
        We minimize a weighted sum of:
          - overall makespan (finish time of the last task overall)
          - total weighted tardiness (how far each job's completion
            exceeds its due date, weighted by job priority)
        The relative weights are exposed via OptimizationConfig so
        the "AI Control Center" UI can push the AI toward
        Speed-first or On-Time/Profit-first behavior without any
        code changes.
    """

    def __init__(self, problem: SchedulingProblem, config: OptimizationConfig):
        self.problem = problem
        self.config = config
        self.model = cp_model.CpModel()

        # Populated during build():
        self._horizon: int = 0
        self._task_presence: Dict[tuple, cp_model.IntVar] = {}   # (task_id, machine_id) -> BoolVar
        self._task_start: Dict[int, cp_model.IntVar] = {}         # task_id -> start var (machine-agnostic)
        self._task_end: Dict[int, cp_model.IntVar] = {}           # task_id -> end var (machine-agnostic)
        self._machine_intervals: Dict[int, List[cp_model.IntervalVar]] = collections.defaultdict(list)
        self._machine_tasks: Dict[int, List[dict]] = collections.defaultdict(list)
        self._job_completion: Dict[int, cp_model.IntVar] = {}
        self._job_tardiness: Dict[int, cp_model.IntVar] = {}
        self._makespan: Optional[cp_model.IntVar] = None

    # -----------------------------------------------------------------
    def _compute_horizon(self) -> int:
        """
        A safe upper bound on total schedule length: sum of the LONGEST
        processing option for every task, plus the latest due date, as
        a cushion. CP-SAT needs a finite horizon to bound the domain of
        start/end integer variables.
        """
        total_max_duration = sum(
            max(opt["processing_minutes"] for opt in task["eligible_machines"])
            for job in self.problem["jobs"]
            for task in job["tasks"]
        )
        latest_due_date = max(job["due_date_minute"] for job in self.problem["jobs"])
        return total_max_duration + latest_due_date

    # -----------------------------------------------------------------
    def build(self) -> None:
        model = self.model
        self._horizon = self._compute_horizon()
        horizon = self._horizon

        # ---- 3a. Fixed downtime intervals block machine time up front.
        # These have no "presence" choice — they always occupy the
        # machine. This single mechanism is what powers the Breakdown
        # Simulator: mark a machine offline -> add/extend a downtime
        # window covering the whole horizon -> re-solve.
        for machine_id, windows in self.problem["machine_downtime"].items():
            for i, window in enumerate(windows):
                start, end = window["start_minute"], window["end_minute"]
                downtime_interval = model.NewIntervalVar(
                    start, end - start, end, f"downtime_m{machine_id}_{i}"
                )
                self._machine_intervals[machine_id].append(downtime_interval)

        # ---- 3b. Per-task optional intervals (one per eligible machine).
        for job in self.problem["jobs"]:
            job_id = job["job_id"]
            prev_end_var: Optional[cp_model.IntVar] = None
            mat_avail = job.get("material_available_minute", 0)

            for task_idx, task in enumerate(job["tasks"]):
                task_id = task["task_id"]

                # Machine-agnostic start/end vars: these represent
                # "when does this task actually happen", regardless of
                # which machine ends up running it. They are linked to
                # the chosen machine's optional interval below.
                start_var = model.NewIntVar(0, horizon, f"start_t{task_id}")
                end_var = model.NewIntVar(0, horizon, f"end_t{task_id}")
                self._task_start[task_id] = start_var
                self._task_end[task_id] = end_var

                # Constraint: Job cannot start before materials are available
                if task_idx == 0 and mat_avail > 0:
                    model.Add(start_var >= mat_avail)

                presence_literals = []

                for option in task["eligible_machines"]:
                    machine_id = option["machine_id"]
                    duration = option["processing_minutes"]

                    presence_lit = model.NewBoolVar(
                        f"presence_t{task_id}_m{machine_id}"
                    )
                    presence_literals.append(presence_lit)
                    self._task_presence[(task_id, machine_id)] = presence_lit

                    # Optional interval: only "occupies" the machine's
                    # timeline if presence_lit is true.
                    interval = model.NewOptionalIntervalVar(
                        start_var, duration, end_var, presence_lit,
                        f"interval_t{task_id}_m{machine_id}",
                    )
                    self._machine_intervals[machine_id].append(interval)

                    # Record task info for setup changeover time constraints
                    self._machine_tasks[machine_id].append({
                        "task_id": task_id,
                        "priority": job["priority_weight"],
                        "presence": presence_lit,
                        "start": start_var,
                        "end": end_var
                    })

                # Exactly one eligible machine is chosen for this task.
                model.AddExactlyOne(presence_literals)

                # Precedence within the job: this task cannot start
                # before the previous task in the same job has ended.
                if prev_end_var is not None:
                    model.Add(start_var >= prev_end_var)
                prev_end_var = end_var

            # Job completion = end of its last task.
            last_task_id = job["tasks"][-1]["task_id"]
            self._job_completion[job_id] = self._task_end[last_task_id]

        # ---- 3c. No-overlap per machine (covers both real tasks and
        # fixed downtime intervals defined above).
        for machine_id, intervals in self._machine_intervals.items():
            model.AddNoOverlap(intervals)

        # ---- Setup / Changeover times constraints:
        # If consecutive tasks on the same machine belong to jobs with different priority levels,
        # inject a 15-minute setup/clean buffer between them.
        for machine_id, task_list in self._machine_tasks.items():
            num_tasks = len(task_list)
            for idx1 in range(num_tasks):
                t1 = task_list[idx1]
                for idx2 in range(idx1 + 1, num_tasks):
                    t2 = task_list[idx2]
                    
                    setup_time = 15 if t1["priority"] != t2["priority"] else 0
                    if setup_time > 0:
                        before = model.NewBoolVar(f"before_t{t1['task_id']}_t{t2['task_id']}_m{machine_id}")
                        model.Add(t2["start"] >= t1["end"] + setup_time).OnlyEnforceIf([t1["presence"], t2["presence"], before])
                        model.Add(t1["start"] >= t2["end"] + setup_time).OnlyEnforceIf([t1["presence"], t2["presence"], before.Not()])

        # ---- 3d. Tardiness per job: max(0, completion - due_date).
        for job in self.problem["jobs"]:
            job_id = job["job_id"]
            completion = self._job_completion[job_id]
            due_date = job["due_date_minute"]

            tardiness = model.NewIntVar(0, horizon, f"tardiness_j{job_id}")
            # tardiness >= completion - due_date, and tardiness >= 0
            # (the NewIntVar lower bound already guarantees >= 0).
            model.Add(tardiness >= completion - due_date)
            self._job_tardiness[job_id] = tardiness

        # ---- 3e. Makespan: the finish time of the very last task, over
        # all jobs.
        makespan = model.NewIntVar(0, horizon, "makespan")
        model.AddMaxEquality(makespan, list(self._job_completion.values()))
        self._makespan = makespan

        # ---- 3f. Objective: weighted makespan + weighted, priority-
        # scaled tardiness. Priority-weighting means a high-priority
        # job (priority_weight=10) that slips gets penalized far more
        # than a low-priority job slipping by the same amount — this
        # is how the solver naturally favors urgent/valuable jobs
        # when machines are contended.
        weighted_tardiness_terms = []
        for job in self.problem["jobs"]:
            job_id = job["job_id"]
            weighted_tardiness_terms.append(
                job["priority_weight"] * self._job_tardiness[job_id]
            )

        model.Minimize(
            self.config.makespan_weight * makespan
            + self.config.tardiness_weight * sum(weighted_tardiness_terms)
        )

    # -----------------------------------------------------------------
    def solve(self) -> SolveResult:
        self.build()

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.config.max_solve_seconds
        solver.parameters.num_search_workers = self.config.num_search_workers
        # Log progress to stdout during development; disable in prod
        # or route through structured logging.
        solver.parameters.log_search_progress = False

        status = solver.Solve(self.model)
        status_name = solver.StatusName(status)

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return SolveResult(
                status=status_name,
                makespan_minutes=None,
                total_tardiness_minutes=None,
                objective_value=None,
                assignments=[],
            )

        assignments: List[TaskAssignment] = []
        for job in self.problem["jobs"]:
            for task in job["tasks"]:
                task_id = task["task_id"]
                chosen_machine_id = None
                for option in task["eligible_machines"]:
                    machine_id = option["machine_id"]
                    lit = self._task_presence[(task_id, machine_id)]
                    if solver.Value(lit):
                        chosen_machine_id = machine_id
                        break
                assert chosen_machine_id is not None, "solver produced no machine choice"

                assignments.append(
                    TaskAssignment(
                        task_id=task_id,
                        job_id=job["job_id"],
                        machine_id=chosen_machine_id,
                        start_minute=solver.Value(self._task_start[task_id]),
                        end_minute=solver.Value(self._task_end[task_id]),
                    )
                )

        total_tardiness = sum(
            solver.Value(t) for t in self._job_tardiness.values()
        )

        return SolveResult(
            status=status_name,
            makespan_minutes=solver.Value(self._makespan),
            total_tardiness_minutes=total_tardiness,
            objective_value=solver.ObjectiveValue(),
            assignments=sorted(assignments, key=lambda a: (a.machine_id, a.start_minute)),
        )


# =====================================================================
# 4. DEMO ENTRYPOINT
# =====================================================================

def _print_schedule(result: SolveResult) -> None:
    print(f"\nSolver status: {result.status}")
    if not result.assignments:
        print("No feasible schedule found.")
        return

    print(f"Makespan: {result.makespan_minutes} minutes")
    print(f"Total weighted objective value: {result.objective_value}")
    print(f"Total (unweighted) tardiness across all jobs: {result.total_tardiness_minutes} minutes\n")

    print(f"{'Machine':<8}{'Job':<8}{'Task':<8}{'Start':<8}{'End':<8}")
    print("-" * 40)
    for a in result.assignments:
        print(f"{a.machine_id:<8}{a.job_id:<8}{a.task_id:<8}{a.start_minute:<8}{a.end_minute:<8}")


if __name__ == "__main__":
    problem = load_scheduling_data()

    # Example: UI's "Maximize Speed" toggle would set tardiness_weight
    # low/0; "Maximize Profit/On-Time" would raise tardiness_weight and
    # optionally fold profit_value into a per-job weight too (left as
    # a Phase 2 extension once the profit objective variant is added).
    config = OptimizationConfig(
        makespan_weight=1,
        tardiness_weight=5,
        max_solve_seconds=15.0,
        num_search_workers=8,
    )

    scheduler = FlexibleJobShopScheduler(problem, config)
    result = scheduler.solve()
    _print_schedule(result)
