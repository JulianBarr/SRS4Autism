import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const CharacterRecognition = ({ profile, onProfileUpdate }) => {
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
      const response = await axios.get(`${API_BASE}/character-recognition/notes`, {
        params: { profile_id: profile.id }
      });
      setNotes(response.data.notes || []);
      setSyncResult(null);
    } catch (error) {
      console.error('Error loading character recognition notes:', error);
      alert(`加载失败: ${error.response?.data?.detail || error.message}`);
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
      alert('请先选择要标记为已掌握的字符');
      return;
    }

    const selectedChars = notes
      .filter(note => selectedNotes.has(note.note_id))
      .map(note => note.character);

    try {
      const response = await axios.post(`${API_BASE}/character-recognition/master`, {
        profile_id: profile.id,
        characters: selectedChars
      });

      alert(`✅ 成功标记 ${response.data.added} 个字符为已掌握`);
      
      // Reload notes to reflect the filter
      loadNotes();
      setSelectedNotes(new Set());
    } catch (error) {
      console.error('Error marking as mastered:', error);
      alert(`❌ 标记失败: ${error.response?.data?.detail || error.message}`);
    }
  };

  const syncToAnki = async () => {
    if (selectedNotes.size === 0) {
      alert('请先选择要同步的字符');
      return;
    }

    if (!window.confirm(`确定要同步 ${selectedNotes.size} 个字符到 Anki 吗？每个字符将创建 7 张卡片。`)) {
      return;
    }

    setSyncing(true);
    setSyncResult(null);
    
    try {
      const response = await axios.post(`${API_BASE}/character-recognition/sync`, {
        profile_id: profile.id,
        note_ids: Array.from(selectedNotes),
        deck_name: '识字'
      });

      setSyncResult({
        success: true,
        message: `成功同步 ${response.data.cards_created} 张卡片`,
        details: response.data
      });
      
      // Clear selection after successful sync
      setSelectedNotes(new Set());
      
      alert(`✅ 同步成功！\n创建了 ${response.data.cards_created} 张卡片\n来自 ${response.data.notes_synced} 个字符`);
    } catch (error) {
      console.error('Error syncing to Anki:', error);
      setSyncResult({
        success: false,
        message: `同步失败: ${error.response?.data?.detail || error.message}`
      });
      alert(`❌ 同步失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      setSyncing(false);
    }
  };

  const selectAll = () => {
    setSelectedNotes(new Set(notes.map(note => note.note_id)));
  };

  const deselectAll = () => {
    setSelectedNotes(new Set());
  };

  return (
    <div style={{ padding: '20px' }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        marginBottom: '20px'
      }}>
        <h2 style={{ margin: 0 }}>汉字识别</h2>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={loadNotes}
            disabled={loading}
            style={{
              padding: '8px 16px',
              backgroundColor: '#4CAF50',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: loading ? 'not-allowed' : 'pointer'
            }}
          >
            {loading ? '加载中...' : '刷新'}
          </button>
          <button
            onClick={selectAll}
            style={{
              padding: '8px 16px',
              backgroundColor: '#2196F3',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            全选
          </button>
          <button
            onClick={deselectAll}
            style={{
              padding: '8px 16px',
              backgroundColor: '#FF9800',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            取消全选
          </button>
          <button
            onClick={markAsMastered}
            disabled={selectedNotes.size === 0}
            style={{
              padding: '8px 16px',
              backgroundColor: selectedNotes.size === 0 ? '#ccc' : '#4CAF50',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: selectedNotes.size === 0 ? 'not-allowed' : 'pointer',
              fontWeight: 'bold'
            }}
          >
            标记为已掌握 ({selectedNotes.size})
          </button>
          <button
            onClick={syncToAnki}
            disabled={syncing || selectedNotes.size === 0}
            style={{
              padding: '8px 16px',
              backgroundColor: syncing || selectedNotes.size === 0 ? '#ccc' : '#9C27B0',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: syncing || selectedNotes.size === 0 ? 'not-allowed' : 'pointer',
              fontWeight: 'bold'
            }}
          >
            {syncing ? '同步中...' : `同步到 Anki (${selectedNotes.size})`}
          </button>
        </div>
      </div>

      {syncResult && (
        <div style={{
          padding: '12px',
          marginBottom: '20px',
          backgroundColor: syncResult.success ? '#d4edda' : '#f8d7da',
          border: `1px solid ${syncResult.success ? '#c3e6cb' : '#f5c6cb'}`,
          borderRadius: '4px',
          color: syncResult.success ? '#155724' : '#721c24'
        }}>
          {syncResult.message}
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <p>加载中...</p>
        </div>
      ) : notes.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <p>没有找到字符识别笔记，或所有字符都已掌握。</p>
        </div>
      ) : (
        <div>
          <p style={{ marginBottom: '20px', color: '#666' }}>
            共 {notes.length} 个字符（已过滤已掌握的字符）
          </p>
          
          <div style={{ display: 'grid', gap: '12px' }}>
            {notes.map((note) => (
              <div
                key={note.note_id}
                style={{
                  border: '1px solid #ddd',
                  borderRadius: '8px',
                  padding: '16px',
                  backgroundColor: selectedNotes.has(note.note_id) ? '#e3f2fd' : 'white',
                  cursor: 'pointer'
                }}
                onClick={() => toggleNoteSelection(note.note_id)}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <input
                    type="checkbox"
                    checked={selectedNotes.has(note.note_id)}
                    onChange={() => toggleNoteSelection(note.note_id)}
                    onClick={(e) => e.stopPropagation()}
                    style={{ width: '20px', height: '20px', cursor: 'pointer' }}
                  />
                  <div style={{ fontSize: '32px', fontWeight: 'bold', minWidth: '60px' }}>
                    {note.character}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '14px', color: '#666', marginBottom: '4px' }}>
                      笔记 ID: {note.note_id}
                    </div>
                    {note.fields.Concept && (
                      <div style={{ fontSize: '14px', color: '#333' }}>
                        概念: {note.fields.Concept.substring(0, 100)}
                        {note.fields.Concept.length > 100 ? '...' : ''}
                      </div>
                    )}
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleExpandNote(note.note_id);
                    }}
                    style={{
                      padding: '6px 12px',
                      backgroundColor: '#f5f5f5',
                      border: '1px solid #ddd',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                  >
                    {expandedNote === note.note_id ? '收起' : '查看字段'}
                  </button>
                </div>

                {expandedNote === note.note_id && (
                  <div
                    style={{
                      marginTop: '16px',
                      padding: '12px',
                      backgroundColor: '#f9f9f9',
                      borderRadius: '4px',
                      border: '1px solid #e0e0e0'
                    }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <h4 style={{ marginTop: 0, marginBottom: '12px' }}>字段详情:</h4>
                    <div style={{ display: 'grid', gap: '8px' }}>
                      {Object.entries(note.fields).map(([fieldName, fieldValue]) => (
                        <div key={fieldName} style={{ display: 'flex', gap: '12px' }}>
                          <strong style={{ minWidth: '120px', color: '#666' }}>
                            {fieldName}:
                          </strong>
                          <div style={{ 
                            flex: 1, 
                            wordBreak: 'break-word',
                            whiteSpace: 'pre-wrap'
                          }}>
                            {fieldValue ? (
                              fieldValue.includes('<img') || fieldValue.includes('<div') ? (
                                <div dangerouslySetInnerHTML={{ __html: fieldValue }} />
                              ) : (
                                fieldValue
                              )
                            ) : (
                              <span style={{ color: '#999', fontStyle: 'italic' }}>（空）</span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default CharacterRecognition;

