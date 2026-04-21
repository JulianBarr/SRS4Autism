from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import func

Base = declarative_base()

class ChildProfile(Base):
    __tablename__ = 'child_profiles'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, unique=True, nullable=False)
    created_at = Column(DateTime, default=func.now())

    milestone_progress = relationship("MilestoneProgress", back_populates="child")

class MilestoneProgress(Base):
    __tablename__ = 'milestone_progress'

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey('child_profiles.id'), nullable=False)
    milestone_uri = Column(String, index=True, nullable=False)
    status = Column(String, nullable=False)  # e.g., 'PASS', 'FAIL', 'PROMPT_DEPENDENT', 'ASSUMED_MASTERED'
    source = Column(String, nullable=False)  # e.g., 'SURVEY', 'INTERVENTION'
    created_at = Column(DateTime, default=func.now(), onupdate=func.now())

    child = relationship("ChildProfile", back_populates="milestone_progress")

    __table_args__ = (UniqueConstraint('child_id', 'milestone_uri', name='_child_milestone_uc'),)
