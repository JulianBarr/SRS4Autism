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
    # Recommender configuration (per-child attention inventory)
    recommender_daily_capacity = Column(Integer, default=20)  # Daily attention slots
    recommender_vocab_ratio = Column(Float, default=0.5)  # Target ratio for vocabulary (0.0-1.0)
    recommender_grammar_ratio = Column(Float, default=0.5)  # Target ratio for grammar (0.0-1.0)
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
    status = Column(String, default='pending')  # 'pending', 'approved', 'rejected'
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


class CharacterRecognitionNote(Base):
    """Character recognition notes extracted from apkg file"""
    __tablename__ = 'character_recognition_notes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    note_id = Column(String, nullable=False, unique=True)  # Original Anki note ID
    character = Column(String, nullable=False)  # The Chinese character
    display_order = Column(Integer, nullable=False)  # Order in which characters should be displayed
    fields = Column(Text, nullable=False)  # JSON object storing all note fields
    created_at = Column(DateTime, default=func.now())
    
    # Constraints
    __table_args__ = (
        Index('idx_char_recog_note_id', 'note_id'),
        Index('idx_char_recog_character', 'character'),
        Index('idx_char_recog_order', 'display_order'),
    )
    
    def __repr__(self):
        return f"<CharacterRecognitionNote(note_id='{self.note_id}', character='{self.character}', order={self.display_order})>"


class ChineseWordRecognitionNote(Base):
    """Chinese word recognition notes extracted from apkg file (concept <=> word mapping)"""
    __tablename__ = 'chinese_word_recognition_notes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    note_id = Column(String, nullable=False, unique=True)  # Original Anki note ID
    word = Column(String, nullable=False)  # The Chinese word
    concept = Column(String, nullable=False)  # The English concept
    display_order = Column(Integer, nullable=False)  # Order in which words should be displayed
    fields = Column(Text, nullable=False)  # JSON object storing all note fields
    created_at = Column(DateTime, default=func.now())
    
    # Constraints
    __table_args__ = (
        Index('idx_word_recog_note_id', 'note_id'),
        Index('idx_word_recog_word', 'word'),
        Index('idx_word_recog_concept', 'concept'),
        Index('idx_word_recog_order', 'display_order'),
    )
    
    def __repr__(self):
        return f"<ChineseWordRecognitionNote(note_id='{self.note_id}', word='{self.word}', concept='{self.concept}', order={self.display_order})>"


class EnglishWordRecognitionNote(Base):
    """English word recognition notes (concept <=> word mapping for naming)"""
    __tablename__ = 'english_word_recognition_notes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    note_id = Column(String, nullable=False, unique=True)  # Generated note ID


class PinyinElementNote(Base):
    """Pinyin element notes (initial or final) - teaching cards"""
    __tablename__ = 'pinyin_element_notes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    note_id = Column(String, nullable=False, unique=True)  # Original Anki note ID
    element = Column(String, nullable=False)  # The pinyin element (initial or final)
    element_type = Column(String, nullable=False)  # "initial" or "final"
    display_order = Column(Integer, nullable=False)  # Order in which elements should be displayed
    fields = Column(Text, nullable=False)  # JSON object storing all note fields
    created_at = Column(DateTime, default=func.now())
    
    # Constraints
    __table_args__ = (
        Index('idx_pinyin_elem_note_id', 'note_id'),
        Index('idx_pinyin_elem_element', 'element'),
        Index('idx_pinyin_elem_order', 'display_order'),
    )
    
    def __repr__(self):
        return f"<PinyinElementNote(note_id='{self.note_id}', element='{self.element}', type='{self.element_type}', order={self.display_order})>"


class PinyinSyllableNote(Base):
    """Pinyin syllable notes - whole syllable with 5 cards"""
    __tablename__ = 'pinyin_syllable_notes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    note_id = Column(String, nullable=False, unique=True)  # Original Anki note ID
    syllable = Column(String, nullable=False)  # The pinyin syllable (e.g., "ma1", "shi2")
    word = Column(String, nullable=False)  # The Chinese word (from WordHanzi field)
    concept = Column(String, nullable=False)  # The concept/meaning (from WordPicture or derived)
    display_order = Column(Integer, nullable=False)  # Order in which syllables should be displayed
    fields = Column(Text, nullable=False)  # JSON object storing all note fields
    created_at = Column(DateTime, default=func.now())
    
    # Constraints
    __table_args__ = (
        Index('idx_pinyin_syl_note_id', 'note_id'),
        Index('idx_pinyin_syl_syllable', 'syllable'),
        Index('idx_pinyin_syl_order', 'display_order'),
    )
    
    def __repr__(self):
        return f"<PinyinSyllableNote(note_id='{self.note_id}', syllable='{self.syllable}', word='{self.word}', order={self.display_order})>"
    word = Column(String, nullable=False)  # The English word (same as concept for naming)
    concept = Column(String, nullable=False)  # The concept (same as word for naming)
    display_order = Column(Integer, nullable=False)  # Order in which words should be displayed
    fields = Column(Text, nullable=False)  # JSON object storing all note fields
    created_at = Column(DateTime, default=func.now())
    
    # Constraints
    __table_args__ = (
        Index('idx_eng_word_recog_note_id', 'note_id'),
        Index('idx_eng_word_recog_word', 'word'),
        Index('idx_eng_word_recog_concept', 'concept'),
        Index('idx_eng_word_recog_order', 'display_order'),
    )
    
    def __repr__(self):
        return f"<EnglishWordRecognitionNote(note_id='{self.note_id}', word='{self.word}', concept='{self.concept}', order={self.display_order})>"


class ChatSession(Base):
    """Persistent chat sessions for topic-specific conversations"""
    __tablename__ = 'chat_sessions'
    
    session_id = Column(String, primary_key=True)
    topic_id = Column(String, nullable=False)  # Grammar Point ID (e.g., en_grammar_101)
    roster_id = Column(String, nullable=False)  # Student profile ID (e.g., yiming)
    messages = Column(Text, nullable=False)  # JSON array of messages
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())
    created_at = Column(DateTime, default=func.now())
    
    # Constraints
    __table_args__ = (
        Index('idx_chat_sessions_topic_roster', 'topic_id', 'roster_id'),
        Index('idx_chat_sessions_roster', 'roster_id'),
        Index('idx_chat_sessions_topic', 'topic_id'),
        Index('idx_chat_sessions_updated', 'last_updated'),
    )
    
    def __repr__(self):
        return f"<ChatSession(session_id='{self.session_id}', topic_id='{self.topic_id}', roster_id='{self.roster_id}')>"

