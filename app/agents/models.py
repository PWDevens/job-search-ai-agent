"""
Pydantic output models for agent responses.
Matches the skill-file contracts exactly.
"""
from pydantic import BaseModel
from typing import List, Optional


class JobMatch(BaseModel):
    """A single job recommendation with ranking and explanation."""
    rank: int
    title: str
    company: str
    location: str
    salary: Optional[str] = None
    url: Optional[str] = None
    why_it_fits: str


class JobMatchList(BaseModel):
    """List of job matches returned by job_matcher agent."""
    matches: List[JobMatch]


class ResumeRec(BaseModel):
    """A single resume improvement recommendation."""
    priority: str  # HIGH | MEDIUM | LOW
    title: str
    current_state: str
    fix: str
    why: str  # cites "Title — Company"
    impact: str


class ResumeRecList(BaseModel):
    """List of resume recommendations returned by resume_coach agent."""
    recommendations: List[ResumeRec]


class BlindSpot(BaseModel):
    """A skill gap or blind spot to address."""
    skill: str
    why: str  # cites 2-3 "Title — Company"
    remediation: str
    time_to_proficiency: str
    priority: str  # CRITICAL | HIGH | MEDIUM


class StrategyRec(BaseModel):
    """A strategic recommendation."""
    title: str
    evidence: str
    action: str


class CareerStrategy(BaseModel):
    """Career strategy and blind spots returned by career_strategist agent."""
    blind_spots: List[BlindSpot]
    strategy: List[StrategyRec]
