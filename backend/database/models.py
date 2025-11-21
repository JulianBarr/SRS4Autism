"""
SQLAlchemy models for SRS4Autism database
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, String, Float, Text, DateTime, Integer, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Profile(Base):
    """User profile table"""
    __tablename__ = 'profiles'
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    dob = Column(String)
    gender = Column(String)
    address = Column(String)
    school = Column(String)
    neighborhood = Column(String)
    interests = Column(Text)  # JSON array stored as text
    character_roster = Column(Text)  # JSON array stored as text
    verbal_fluency = Column(String)
    passive_language_level = Column(String)
    mental_age = Column(Float)
    raw_input = Column(Text)
    extracted_data = Column(Text)  # JSON object stored as text
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    mastered_words = relationship("MasteredWord", back_populates="profile", cascade="all, delete-orphan")
    mastered_grammar = relationship("MasteredGrammar", back_populates="profile", cascade="all, delete-orphan")
    approved_cards = relationship("ApprovedCard", back_populates="profile", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="profile", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Profile(id='{self.id}', name='{self.name}')>"


class MasteredWord(Base):
    """Mastered words table (Chinese and English)"""
    __tablename__ = 'mastered_words'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(String, ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
    word = Column(String, nullable=False)
    language = Column(String, nullable=False)  # 'zh' or 'en'
    added_at = Column(DateTime, default=func.now())
    
    # Relationship
    profile = relationship("Profile", back_populates="mastered_words")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('profile_id', 'word', 'language', name='uq_profile_word_lang'),
        Index('idx_mastered_words_profile', 'profile_id'),
        Index('idx_mastered_words_language', 'language'),
    )
    
    def __repr__(self):
        return f"<MasteredWord(profile_id='{self.profile_id}', word='{self.word}', lang='{self.language}')>"


class MasteredGrammar(Base):
    """Mastered grammar points table"""
    __tablename__ = 'mastered_grammar'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(String, ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
    grammar_uri = Column(String, nullable=False)
    added_at = Column(DateTime, default=func.now())
    
    # Relationship
    profile = relationship("Profile", back_populates="mastered_grammar")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('profile_id', 'grammar_uri', name='uq_profile_grammar'),
        Index('idx_mastered_grammar_profile', 'profile_id'),
    )
    
    def __repr__(self):
        return f"<MasteredGrammar(profile_id='{self.profile_id}', grammar_uri='{self.grammar_uri}')>"


class ApprovedCard(Base):
    """Approved cards table"""
    __tablename__ = 'approved_cards'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(String, ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
    card_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)  # JSON object stored as text
    approved_at = Column(DateTime, default=func.now())
    
    # Relationship
    profile = relationship("Profile", back_populates="approved_cards")
    
    # Constraints
    __table_args__ = (
        Index('idx_approved_cards_profile', 'profile_id'),
    )
    
    def __repr__(self):
        return f"<ApprovedCard(id={self.id}, profile_id='{self.profile_id}', type='{self.card_type}')>"


class ChatMessage(Base):
    """Chat history table"""
    __tablename__ = 'chat_messages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(String, ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=func.now())
    
    # Relationship
    profile = relationship("Profile", back_populates="chat_messages")
    
    # Constraints
    __table_args__ = (
        Index('idx_chat_messages_profile', 'profile_id'),
        Index('idx_chat_messages_timestamp', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<ChatMessage(id={self.id}, profile_id='{self.profile_id}', role='{self.role}')>"


class AuditLog(Base):
    """Audit log table for tracking all changes"""
    __tablename__ = 'audit_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    table_name = Column(String, nullable=False)
    record_id = Column(String, nullable=False)
    action = Column(String, nullable=False)  # 'INSERT', 'UPDATE', 'DELETE'
    old_value = Column(Text)  # JSON stored as text
    new_value = Column(Text)  # JSON stored as text
    changed_at = Column(DateTime, default=func.now())
    changed_by = Column(String, default='system')  # 'system', 'user', 'migration', etc.
    
    # Constraints
    __table_args__ = (
        Index('idx_audit_log_table', 'table_name'),
        Index('idx_audit_log_timestamp', 'changed_at'),
        Index('idx_audit_log_record', 'table_name', 'record_id'),
    )
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, table='{self.table_name}', action='{self.action}')>"

