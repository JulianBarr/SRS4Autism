"""
Database service layer for business logic
"""

import json
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from .models import Profile, MasteredWord, MasteredGrammar, ApprovedCard, ChatMessage, AuditLog


class ProfileService:
    """Service for profile operations"""
    
    @staticmethod
    def get_all(db: Session) -> List[Profile]:
        """Get all profiles"""
        return db.query(Profile).all()
    
    @staticmethod
    def get_by_id(db: Session, profile_id: str) -> Optional[Profile]:
        """Get profile by ID"""
        return db.query(Profile).filter(Profile.id == profile_id).first()
    
    @staticmethod
    def create(db: Session, profile_data: Dict[str, Any]) -> Profile:
        """Create new profile"""
        # Extract lists that need to be stored in separate tables
        mastered_words_zh = profile_data.pop('mastered_words_list', [])
        mastered_words_en = profile_data.pop('mastered_english_words_list', [])
        mastered_grammar_list = profile_data.pop('mastered_grammar_list', [])
        
        # Convert lists to JSON strings
        if 'interests' in profile_data and isinstance(profile_data['interests'], list):
            profile_data['interests'] = json.dumps(profile_data['interests'])
        if 'character_roster' in profile_data and isinstance(profile_data['character_roster'], list):
            profile_data['character_roster'] = json.dumps(profile_data['character_roster'])
        if 'extracted_data' in profile_data and isinstance(profile_data['extracted_data'], dict):
            profile_data['extracted_data'] = json.dumps(profile_data['extracted_data'])
        
        # Create profile
        profile = Profile(**profile_data)
        db.add(profile)
        db.flush()  # Get the profile ID
        
        # Add mastered words
        for word in mastered_words_zh:
            if word.strip():
                db.add(MasteredWord(profile_id=profile.id, word=word.strip(), language='zh'))
        for word in mastered_words_en:
            if word.strip():
                db.add(MasteredWord(profile_id=profile.id, word=word.strip(), language='en'))
        
        # Add mastered grammar
        for grammar_uri in mastered_grammar_list:
            if grammar_uri.strip():
                db.add(MasteredGrammar(profile_id=profile.id, grammar_uri=grammar_uri.strip()))
        
        db.commit()
        db.refresh(profile)
        
        # Create audit log
        db.add(AuditLog(
            table_name='profiles',
            record_id=profile.id,
            action='INSERT',
            new_value=json.dumps({'name': profile.name}),
            changed_by='api'
        ))
        db.commit()
        
        return profile
    
    @staticmethod
    def update(db: Session, profile_id: str, profile_data: Dict[str, Any]) -> Optional[Profile]:
        """Update existing profile"""
        profile = ProfileService.get_by_id(db, profile_id)
        if not profile:
            return None
        
        # Store old value for audit log
        old_value = json.dumps({'name': profile.name})
        
        # Extract lists
        mastered_words_zh = profile_data.pop('mastered_words_list', None)
        mastered_words_en = profile_data.pop('mastered_english_words_list', None)
        mastered_grammar_list = profile_data.pop('mastered_grammar_list', None)
        
        # Convert lists to JSON strings
        if 'interests' in profile_data and isinstance(profile_data['interests'], list):
            profile_data['interests'] = json.dumps(profile_data['interests'])
        if 'character_roster' in profile_data and isinstance(profile_data['character_roster'], list):
            profile_data['character_roster'] = json.dumps(profile_data['character_roster'])
        if 'extracted_data' in profile_data and isinstance(profile_data['extracted_data'], dict):
            profile_data['extracted_data'] = json.dumps(profile_data['extracted_data'])
        
        # Update profile fields
        for key, value in profile_data.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        
        # Update mastered words if provided
        if mastered_words_zh is not None:
            db.query(MasteredWord).filter_by(profile_id=profile_id, language='zh').delete()
            for word in mastered_words_zh:
                if word.strip():
                    db.add(MasteredWord(profile_id=profile_id, word=word.strip(), language='zh'))
        
        if mastered_words_en is not None:
            db.query(MasteredWord).filter_by(profile_id=profile_id, language='en').delete()
            for word in mastered_words_en:
                if word.strip():
                    db.add(MasteredWord(profile_id=profile_id, word=word.strip(), language='en'))
        
        # Update mastered grammar if provided
        if mastered_grammar_list is not None:
            db.query(MasteredGrammar).filter_by(profile_id=profile_id).delete()
            for grammar_uri in mastered_grammar_list:
                if grammar_uri.strip():
                    db.add(MasteredGrammar(profile_id=profile_id, grammar_uri=grammar_uri.strip()))
        
        db.commit()
        db.refresh(profile)
        
        # Create audit log
        db.add(AuditLog(
            table_name='profiles',
            record_id=profile_id,
            action='UPDATE',
            old_value=old_value,
            new_value=json.dumps({'name': profile.name}),
            changed_by='api'
        ))
        db.commit()
        
        return profile
    
    @staticmethod
    def delete(db: Session, profile_id: str) -> bool:
        """Delete profile"""
        profile = ProfileService.get_by_id(db, profile_id)
        if not profile:
            return False
        
        # Store for audit log
        old_value = json.dumps({'name': profile.name})
        
        db.delete(profile)  # Cascade will delete related records
        db.commit()
        
        # Create audit log
        db.add(AuditLog(
            table_name='profiles',
            record_id=profile_id,
            action='DELETE',
            old_value=old_value,
            changed_by='api'
        ))
        db.commit()
        
        return True
    
    @staticmethod
    def get_mastered_words(db: Session, profile_id: str, language: str = 'zh') -> List[str]:
        """Get list of mastered words for a profile"""
        words = db.query(MasteredWord.word).filter_by(
            profile_id=profile_id,
            language=language
        ).all()
        return [w[0] for w in words]
    
    @staticmethod
    def get_mastered_grammar(db: Session, profile_id: str) -> List[str]:
        """Get list of mastered grammar URIs for a profile"""
        grammar = db.query(MasteredGrammar.grammar_uri).filter_by(
            profile_id=profile_id
        ).all()
        return [g[0] for g in grammar]
    
    @staticmethod
    def profile_to_dict(db: Session, profile: Profile) -> Dict[str, Any]:
        """Convert Profile model to dictionary (API response format)"""
        # Get mastered words
        chinese_words = ProfileService.get_mastered_words(db, profile.id, 'zh')
        english_words = ProfileService.get_mastered_words(db, profile.id, 'en')
        grammar_uris = ProfileService.get_mastered_grammar(db, profile.id)
        
        # Parse JSON fields
        interests = json.loads(profile.interests) if profile.interests else []
        character_roster = json.loads(profile.character_roster) if profile.character_roster else []
        extracted_data = json.loads(profile.extracted_data) if profile.extracted_data else {}
        
        return {
            'id': profile.id,
            'name': profile.name,
            'dob': profile.dob,
            'gender': profile.gender,
            'address': profile.address,
            'school': profile.school,
            'neighborhood': profile.neighborhood,
            'interests': interests,
            'character_roster': character_roster,
            'verbal_fluency': profile.verbal_fluency,
            'passive_language_level': profile.passive_language_level,
            'mental_age': profile.mental_age,
            'raw_input': profile.raw_input,
            'mastered_words': ', '.join(chinese_words),
            'mastered_english_words': ', '.join(english_words),
            'mastered_grammar': ','.join(grammar_uris),
            'extracted_data': extracted_data
        }


class CardService:
    """Service for approved card operations"""
    
    @staticmethod
    def get_all_for_profile(db: Session, profile_id: str) -> List[ApprovedCard]:
        """Get all approved cards for a profile"""
        return db.query(ApprovedCard).filter_by(profile_id=profile_id).all()
    
    @staticmethod
    def create(db: Session, profile_id: str, card_type: str, content: Dict[str, Any]) -> ApprovedCard:
        """Create new approved card"""
        card = ApprovedCard(
            profile_id=profile_id,
            card_type=card_type,
            content=json.dumps(content)
        )
        db.add(card)
        db.commit()
        db.refresh(card)
        return card


class ChatService:
    """Service for chat message operations"""
    
    @staticmethod
    def get_history(db: Session, profile_id: str, limit: int = 100) -> List[ChatMessage]:
        """Get chat history for a profile"""
        return db.query(ChatMessage).filter_by(
            profile_id=profile_id
        ).order_by(ChatMessage.timestamp.desc()).limit(limit).all()
    
    @staticmethod
    def add_message(db: Session, profile_id: str, role: str, content: str) -> ChatMessage:
        """Add a chat message"""
        message = ChatMessage(
            profile_id=profile_id,
            role=role,
            content=content
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        return message

