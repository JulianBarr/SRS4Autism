import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/**
 * English Word Recognition Component
 * 
 * For verbal training - focuses on listening and speaking, not reading/writing.
 * Cards emphasize:
 * - Audio pronunciation (listening)
 * - Picture selection (visual comprehension)
 * - Verbal response (speaking)
 * - Text is optional, only for non-verbal users to reply
 */
const EnglishWordRecognition = ({ profile, onProfileUpdate }) => {
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedNotes, setSelectedNotes] = useState(new Set());
  const [expandedNote, setExpandedNote] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState(null);

  useEffect(() => {
    if (profile?.id) {
      loadNotes();
    }
  }, [profile?.id]);

  const loadNotes = async () => {
    if (!profile?.id) return;
    
    setLoading(true);
    try {
      const response = await axios.get(`${API_BASE}/english-word-recognition/notes`, {
        params: { profile_id: profile.id }
      });
      setNotes(response.data.notes || []);
      setSyncResult(null);
    } catch (error) {
      console.error('Error loading English word recognition notes:', error);
      alert(`Failed to load: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const toggleNoteSelection = (noteId) => {
    const newSelected = new Set(selectedNotes);
    if (newSelected.has(noteId)) {
      newSelected.delete(noteId);
    } else {
      newSelected.add(noteId);
    }
    setSelectedNotes(newSelected);
  };

  const toggleExpandNote = (noteId) => {
    setExpandedNote(expandedNote === noteId ? null : noteId);
  };

  const markAsMastered = async () => {
    if (selectedNotes.size === 0) {
      alert('Please select words to mark as mastered');
      return;
    }

    const selectedWords = notes
      .filter(note => selectedNotes.has(note.note_id))
      .map(note => note.word);

    try {
      // Use the existing mastered words endpoint for English
      const response = await axios.post(`${API_BASE}/profiles/${profile.id}/mastered-words`, {
        words: selectedWords,
        language: 'en'
      });

      alert(`✅ Successfully marked ${selectedWords.length} words as mastered`);
      
      // Reload notes to reflect the filter
      loadNotes();
      setSelectedNotes(new Set());
      
      // Notify parent to update profile
      if (onProfileUpdate) {
        onProfileUpdate();
      }
    } catch (error) {
      console.error('Error marking as mastered:', error);
      alert(`❌ Failed to mark: ${error.response?.data?.detail || error.message}`);
    }
  };

  const syncToAnki = async () => {
    if (selectedNotes.size === 0) {
      alert('Please select words to sync');
      return;
    }

    setSyncing(true);
    try {
      const response = await axios.post(`${API_BASE}/english-word-recognition/sync`, {
        profile_id: profile.id,
        note_ids: Array.from(selectedNotes),
        deck_name: "English Naming"
      });

      setSyncResult(response.data);
      alert(`✅ Successfully synced ${response.data.notes_synced} notes (${response.data.cards_created} cards) to Anki`);
      
      // Reload notes to reflect the filter (synced words are marked as mastered)
      loadNotes();
      setSelectedNotes(new Set());
      
      // Notify parent to update profile
      if (onProfileUpdate) {
        onProfileUpdate();
      }
    } catch (error) {
      console.error('Error syncing to Anki:', error);
      alert(`❌ Sync failed: ${error.response?.data?.detail || error.message}`);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div style={{ padding: '20px' }}>
      <h2 style={{ marginBottom: '20px' }}>📝 Word Recognition (Concept ⇔ Word) - English</h2>
      
      {/* Action Buttons */}
      <div style={{ marginBottom: '20px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
        <button
          onClick={loadNotes}
          disabled={loading}
          className="btn"
          style={{
            backgroundColor: '#4CAF50',
            color: 'white',
            padding: '8px 16px',
            border: 'none',
            borderRadius: '4px',
            cursor: loading ? 'not-allowed' : 'pointer'
          }}
        >
          {loading ? 'Loading...' : '🔄 Refresh'}
        </button>
        
        <button
          onClick={() => {
            const allSelected = notes.length > 0 && selectedNotes.size === notes.length;
            if (allSelected) {
              setSelectedNotes(new Set());
            } else {
              setSelectedNotes(new Set(notes.map(n => n.note_id)));
            }
          }}
          className="btn"
          style={{
            backgroundColor: '#2196F3',
            color: 'white',
            padding: '8px 16px',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          {selectedNotes.size === notes.length && notes.length > 0 ? '❌ Deselect All' : '✓ Select All'}
        </button>
        
        <button
          onClick={markAsMastered}
          disabled={selectedNotes.size === 0}
          className="btn"
          style={{
            backgroundColor: selectedNotes.size === 0 ? '#ccc' : '#FF9800',
            color: 'white',
            padding: '8px 16px',
            border: 'none',
            borderRadius: '4px',
            cursor: selectedNotes.size === 0 ? 'not-allowed' : 'pointer'
          }}
        >
          Mark as Mastered ({selectedNotes.size})
        </button>
        
        <button
          onClick={syncToAnki}
          disabled={selectedNotes.size === 0 || syncing}
          className="btn"
          style={{
            backgroundColor: selectedNotes.size === 0 || syncing ? '#ccc' : '#9C27B0',
            color: 'white',
            padding: '8px 16px',
            border: 'none',
            borderRadius: '4px',
            cursor: selectedNotes.size === 0 || syncing ? 'not-allowed' : 'pointer'
          }}
        >
          {syncing ? 'Syncing...' : `Sync to Anki (${selectedNotes.size})`}
        </button>
      </div>

      {/* Notes List */}
      {loading ? (
        <p>Loading notes...</p>
      ) : notes.length === 0 ? (
        <p style={{ color: '#666', fontStyle: 'italic' }}>
          No English word recognition notes found, or all words have been mastered.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {notes.map((note) => {
            const isSelected = selectedNotes.has(note.note_id);
            const isExpanded = expandedNote === note.note_id;
            const fields = note.fields || {};
            
            return (
              <div
                key={note.note_id}
                style={{
                  border: `2px solid ${isSelected ? '#2196F3' : '#ddd'}`,
                  borderRadius: '8px',
                  padding: '15px',
                  backgroundColor: isSelected ? '#f0f8ff' : 'white',
                  cursor: 'pointer'
                }}
                onClick={() => toggleNoteSelection(note.note_id)}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleNoteSelection(note.note_id)}
                    onClick={(e) => e.stopPropagation()}
                    style={{ cursor: 'pointer' }}
                  />
                  <strong style={{ fontSize: '18px' }}>{note.word}</strong>
                  <span style={{ color: '#666' }}>({note.concept})</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleExpandNote(note.note_id);
                    }}
                    style={{
                      marginLeft: 'auto',
                      padding: '4px 8px',
                      fontSize: '12px',
                      backgroundColor: '#f0f0f0',
                      border: '1px solid #ddd',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                  >
                    {isExpanded ? '▼ Hide' : '▶ Show'} Fields
                  </button>
                </div>
                
                {isExpanded && (
                  <div style={{ marginTop: '10px', padding: '10px', backgroundColor: '#f9f9f9', borderRadius: '4px' }}>
                    {Object.entries(fields).map(([key, value]) => (
                      <div key={key} style={{ marginBottom: '8px' }}>
                        <strong>{key}:</strong>
                        <div 
                          style={{ 
                            marginTop: '4px',
                            padding: '8px',
                            backgroundColor: 'white',
                            borderRadius: '4px',
                            border: '1px solid #ddd'
                          }}
                          dangerouslySetInnerHTML={{ __html: value || '' }}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default EnglishWordRecognition;








