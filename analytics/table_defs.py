import uuid
import datetime
from pydantic import BaseModel
from typing import Optional

class ConfigRow(BaseModel):
    id: uuid.UUID
    dataset: str
    baseline: str

    def __repr__(self) -> str:
        return f"ConfigRow(id={self.id}, dataset={self.dataset}, baseline={self.baseline})"

    def __str__(self) -> str:
        return self.__repr__()

class SummaryRow(BaseModel):
    id: uuid.UUID
    config_id: uuid.UUID
    duration_seconds: float
    overall_success_rate: float
    total_tasks: int
    total_instances: int

    def __repr__(self) -> str:
        return f"SummaryRow(id={self.id}, config_id={self.config_id}, duration_seconds={self.duration_seconds}, overall_success_rate={self.overall_success_rate}, total_tasks={self.total_tasks}, total_instances={self.total_instances})"

    def __str__(self) -> str:
        return self.__repr__()

class TaskRow(BaseModel):
    id: uuid.UUID
    summary_id: uuid.UUID
    task_id: str
    name: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[str] = None
    success_rate: float
    avg_latency_ms: float
    instance_count: int

class MetricRow(BaseModel):
    id: uuid.UUID
    config_id: uuid.UUID
    task_name: str
    method: str
    model: str
    notes: str
    timestamp: datetime.datetime

class MetricResultRow(BaseModel):
    id: uuid.UUID
    metric_id: uuid.UUID
    name: str
    value: str | float
    unit: str
    timestamp: datetime.datetime