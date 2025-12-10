import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/**
 * Image component with fallback paths (similar to PinyinGapFillSuggestions)
 */
const ImageWithFallback = ({ src, alt, style, className }) => {
  const [currentPathIndex, setCurrentPathIndex] = React.useState(0);
  const [imageKey, setImageKey] = React.useState(0);
  
  // Extract filename from src (could be just filename or full path)
  const filename = src.includes('/') ? src.split('/').pop() : src;
  
  // List of alternative paths to try
  const alternativePaths = [
    `${API_BASE}/media/visual_images/${filename}`,
    `${API_BASE}/media/pinyin/${filename}`,
    `${API_BASE}/media/character_recognition/${filename}`,
    `${API_BASE}/media/chinese_word_recognition/${filename}`,
    `${API_BASE}/media/images/${filename}`,
    `${API_BASE}/media/${filename}`,
    `${API_BASE}/${filename}`
  ];
  
  const currentSrc = alternativePaths[currentPathIndex] || alternativePaths[0];
  
  const handleError = () => {
    if (currentPathIndex < alternativePaths.length - 1) {
      setCurrentPathIndex(currentPathIndex + 1);
      setImageKey(imageKey + 1); // Force re-render
    }
  };
  
  const handleLoad = (e) => {
    e.target.style.display = 'block';
    e.target.style.visibility = 'visible';
  };
  
  return (
    <img
      key={`${filename}-${imageKey}-${currentPathIndex}`}
      src={currentSrc}
      alt={alt}
      style={style}
      className={className}
      onError={handleError}
      onLoad={handleLoad}
    />
  );
};

/**
 * Pinyin Learning Component
 * 
 * Manages two types of pinyin notes:
 * 1. Pinyin Elements (initial/final teaching cards)
 * 2. Pinyin Syllables (whole syllable with 5 cards)
 * 
 * Located under Cognition Cove for non-verbal children who may need pinyin as an effective output means.
 */
const PinyinLearning = ({ profile, onProfileUpdate }) => {
  const [activeTab, setActiveTab] = useState('elements'); // 'elements' or 'syllables'
  const [elementNotes, setElementNotes] = useState([]);
  const [syllableNotes, setSyllableNotes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedNotes, setSelectedNotes] = useState(new Set());
  const [expandedNote, setExpandedNote] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [showMastered, setShowMastered] = useState(false); // Filter toggle for mastered items

  useEffect(() => {
    if (profile?.id) {
      loadNotes();
    }
  }, [profile?.id, activeTab]);

  const loadNotes = async () => {
    if (!profile?.id) return;
    
    setLoading(true);
    try {
      if (activeTab === 'elements') {
        const response = await axios.get(`${API_BASE}/pinyin/elements`, {
          params: { profile_id: profile.id },
          timeout: 10000 // 10 second timeout
        });
        setElementNotes(response.data.notes || []);
      } else {
        const response = await axios.get(`${API_BASE}/pinyin/syllables`, {
          params: { profile_id: profile.id },
          timeout: 10000 // 10 second timeout
        });
        setSyllableNotes(response.data.notes || []);
      }
      setSyncResult(null);
    } catch (error) {
      console.error('Error loading pinyin notes:', error);
      const errorMsg = error.code === 'ECONNABORTED' 
        ? '请求超时，请检查后端服务是否正常运行'
        : error.response?.data?.detail || error.message;
      alert(`加载失败: ${errorMsg}`);
      // Set empty arrays on error to prevent infinite loading
      if (activeTab === 'elements') {
        setElementNotes([]);
      } else {
        setSyllableNotes([]);
      }
    } finally {
      setLoading(false);
    }
  };

  // Get mastered items from profile (stored as comma-separated string)
  const getMasteredItems = () => {
    if (activeTab === 'elements') {
      const masteredStr = profile?.mastered_pinyin_elements || '';
      return new Set(masteredStr.split(/[,\s，]+/).map(s => s.trim()).filter(s => s));
    } else {
      const masteredStr = profile?.mastered_pinyin_syllables || '';
      return new Set(masteredStr.split(/[,\s，]+/).map(s => s.trim()).filter(s => s));
    }
  };

  const masteredItems = getMasteredItems();
  
  // Filter notes based on mastered status
  const currentNotesRaw = activeTab === 'elements' ? elementNotes : syllableNotes;
  const currentNotes = showMastered 
    ? currentNotesRaw 
    : currentNotesRaw.filter(note => {
        const identifier = activeTab === 'elements' ? note.element : note.syllable;
        return !masteredItems.has(identifier);
      });

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

  const deleteSelectedNotes = async () => {
    if (selectedNotes.size === 0) {
      alert('请先选择要删除的笔记');
      return;
    }

    if (!window.confirm(`确定要删除 ${selectedNotes.size} 个笔记吗？此操作不可撤销。`)) {
      return;
    }

    setDeleting(true);
    try {
      const noteIds = Array.from(selectedNotes);
      
      // Filter by active tab
      const notesToDelete = activeTab === 'elements' 
        ? noteIds.filter(id => elementNotes.some(n => n.note_id === id))
        : noteIds.filter(id => syllableNotes.some(n => n.note_id === id));

      if (notesToDelete.length === 0) {
        alert('没有找到要删除的笔记');
        return;
      }

      // Delete syllable notes
      if (activeTab === 'syllables') {
        const response = await axios.delete(`${API_BASE}/pinyin/syllables`, {
          data: { note_ids: notesToDelete },
          timeout: 10000
        });
        alert(`✅ 成功删除 ${response.data.deleted_count} 个拼音音节笔记`);
      } else {
        // For elements, we'd need a similar endpoint - for now just show message
        alert('删除拼音元素功能暂未实现，请删除拼音音节');
        return;
      }

      // Clear selection
      setSelectedNotes(new Set());
      
      // Reload notes
      loadNotes();
    } catch (error) {
      console.error('Error deleting notes:', error);
      const errorMsg = error.response?.data?.detail || error.message;
      alert(`删除失败: ${errorMsg}`);
    } finally {
      setDeleting(false);
    }
  };

  const syncToAnki = async () => {
    if (selectedNotes.size === 0) {
      alert('请先选择要同步的笔记');
      return;
    }

    setSyncing(true);
    setSyncResult(null);

    try {
      // Collect notes from both tabs - separate element and syllable note IDs
      // This allows syncing both types together in the same deck, preserving .apkg order
      const elementNoteIds = Array.from(selectedNotes).filter(id => 
        elementNotes.some(n => n.note_id === id)
      );
      const syllableNoteIds = Array.from(selectedNotes).filter(id => 
        syllableNotes.some(n => n.note_id === id)
      );

      // Sync both types together in the same deck, preserving order from display_order
      const response = await axios.post(`${API_BASE}/pinyin/sync`, {
        profile_id: profile.id,
        element_note_ids: elementNoteIds,
        syllable_note_ids: syllableNoteIds,
        deck_name: '拼音'
      });

      setSyncResult(response.data);
      alert(`✅ 成功同步 ${response.data.notes_synced} 个笔记，创建了 ${response.data.cards_created} 张卡片`);
      
      // Clear selection
      setSelectedNotes(new Set());
      
      // Reload notes
      loadNotes();
    } catch (error) {
      console.error('Error syncing pinyin notes:', error);
      const errorMsg = error.response?.data?.detail || error.message;
      alert(`同步失败: ${errorMsg}`);
      setSyncResult({ errors: [{ error: errorMsg }] });
    } finally {
      setSyncing(false);
    }
  };

  // Helper function to render field values, especially for Picture fields
  const renderFieldValue = (fieldName, fieldValue) => {
    if (!fieldValue) {
      return <span style={{ color: '#999', fontStyle: 'italic' }}>（空）</span>;
    }
    
    // If it's HTML (contains img or div tags), extract image src and use ImageWithFallback
    if (fieldValue.includes('<img')) {
      // Extract image src from HTML
      const imgMatch = fieldValue.match(/<img[^>]*\s+src=["']([^"']+)["'][^>]*>/i);
      if (imgMatch) {
        const imgSrc = imgMatch[1];
        // Extract filename (could be just filename or full path)
        const filename = imgSrc.includes('/') ? imgSrc.split('/').pop() : imgSrc;
        
        return (
          <div className="word-preview-img-container">
            <ImageWithFallback
              src={filename}
              alt={fieldName}
              style={{
                maxWidth: '100px',
                maxHeight: '100px',
                borderRadius: '4px',
                border: '1px solid #ddd',
                objectFit: 'contain',
                backgroundColor: '#f5f5f5'
              }}
            />
          </div>
        );
      }
      // Fallback: render as HTML if we can't extract src
      return (
        <div 
          dangerouslySetInnerHTML={{ __html: fieldValue }}
          className="word-preview-img-container"
        />
      );
    }
    
    // Special handling for Picture field - convert filename to img tag
    const isPictureField = fieldName.toLowerCase() === 'picture';
    if (isPictureField) {
      // Check if it looks like a filename (has extension or no spaces)
      const looksLikeFilename = fieldValue.match(/\.(jpg|jpeg|png|gif|webp|svg|bmp)$/i) || 
                                (!fieldValue.includes(' ') && fieldValue.length < 100);
      
      if (looksLikeFilename) {
        // Extract filename (remove any path)
        const filename = fieldValue.includes('/') ? fieldValue.split('/').pop() : fieldValue;
        
        return (
          <div style={{ position: 'relative' }}>
            <ImageWithFallback
              src={filename}
              alt={fieldName}
              style={{
                maxWidth: '100px',
                maxHeight: '100px',
                borderRadius: '4px',
                border: '1px solid #ddd',
                objectFit: 'contain',
                backgroundColor: '#f5f5f5'
              }}
            />
          </div>
        );
      }
      
      // If not a filename, try to render as HTML
      if (fieldValue.includes('<img')) {
        const imgMatch = fieldValue.match(/<img[^>]*\s+src=["']([^"']+)["'][^>]*>/i);
        if (imgMatch) {
          const imgSrc = imgMatch[1];
          const filename = imgSrc.includes('/') ? imgSrc.split('/').pop() : imgSrc;
          return (
            <div style={{ position: 'relative' }}>
              <ImageWithFallback
                src={filename}
                alt={fieldName}
                style={{
                  maxWidth: '100px',
                  maxHeight: '100px',
                  borderRadius: '4px',
                  border: '1px solid #ddd',
                  objectFit: 'contain',
                  backgroundColor: '#f5f5f5'
                }}
              />
            </div>
          );
        }
      }
      
      // Fallback: return as plain text or HTML
      return (
        <div 
          dangerouslySetInnerHTML={{ __html: fieldValue }}
          style={{ wordBreak: 'break-word' }}
        />
      );
    }
    
    // Default: return as plain text
    return <span style={{ wordBreak: 'break-word' }}>{fieldValue}</span>;
  };

  const renderNoteCard = (note) => {
    const isExpanded = expandedNote === note.note_id;
    const isSelected = selectedNotes.has(note.note_id);
    const identifier = activeTab === 'elements' ? note.element : note.syllable;
    const isMastered = masteredItems.has(identifier);

    if (activeTab === 'elements') {
      return (
        <div
          key={note.note_id}
          className={`note-card ${isSelected ? 'selected' : ''}`}
          style={{
            border: '1px solid #ddd',
            borderRadius: '8px',
            padding: '15px',
            marginBottom: '10px',
            cursor: 'pointer',
            backgroundColor: isSelected ? '#e3f2fd' : '#fff'
          }}
          onClick={() => toggleNoteSelection(note.note_id)}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <input
              type="checkbox"
              checked={isSelected}
              onChange={() => toggleNoteSelection(note.note_id)}
              onClick={(e) => e.stopPropagation()}
            />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 'bold', fontSize: '1.2em', marginBottom: '5px' }}>
                {note.element} ({note.element_type})
              </div>
              {isExpanded && (
                <div style={{
                  marginTop: '16px',
                  padding: '12px',
                  backgroundColor: '#f9f9f9',
                  borderRadius: '4px',
                  border: '1px solid #e0e0e0'
                }}>
                  <h4 style={{ marginTop: 0, marginBottom: '12px', fontSize: '14px', fontWeight: 'bold' }}>字段详情:</h4>
                  <div style={{ display: 'grid', gap: '8px' }}>
                    {Object.entries(note.fields || {}).map(([fieldName, fieldValue]) => {
                      const isPictureField = fieldName.toLowerCase() === 'picture';
                      return (
                        <div key={fieldName} style={{ 
                          display: 'flex', 
                          gap: '12px',
                          alignItems: isPictureField ? 'flex-start' : 'center'
                        }}>
                          <strong style={{ minWidth: '120px', color: '#666', fontSize: '0.9em' }}>
                            {fieldName}:
                          </strong>
                          <div style={{ 
                            flex: 1, 
                            wordBreak: 'break-word',
                            whiteSpace: 'pre-wrap',
                            fontSize: '0.9em'
                          }}>
                            {renderFieldValue(fieldName, fieldValue)}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                toggleExpandNote(note.note_id);
              }}
              style={{ padding: '5px 10px' }}
            >
              {isExpanded ? '收起' : '展开'}
            </button>
          </div>
        </div>
      );
    } else {
      return (
        <div
          key={note.note_id}
          className={`note-card ${isSelected ? 'selected' : ''}`}
          style={{
            border: '1px solid #ddd',
            borderRadius: '8px',
            padding: '15px',
            marginBottom: '10px',
            cursor: 'pointer',
            backgroundColor: isSelected ? '#e3f2fd' : (isMastered ? '#f5f5f5' : '#fff'),
            opacity: isMastered && !showMastered ? 0.5 : 1
          }}
          onClick={() => toggleNoteSelection(note.note_id)}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <input
              type="checkbox"
              checked={isSelected}
              onChange={() => toggleNoteSelection(note.note_id)}
              onClick={(e) => e.stopPropagation()}
            />
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '5px' }}>
                <div style={{ fontWeight: 'bold', fontSize: '1.2em' }}>
                  {note.syllable} {note.word && `(${note.word})`}
                </div>
                {isMastered && (
                  <span style={{ 
                    fontSize: '0.8em', 
                    color: '#4caf50', 
                    backgroundColor: '#e8f5e9',
                    padding: '2px 8px',
                    borderRadius: '12px'
                  }}>
                    ✓ 已掌握
                  </span>
                )}
              </div>
              {note.concept && (
                <div style={{ fontSize: '0.9em', color: '#666', marginBottom: '5px' }}>
                  {note.concept}
                </div>
              )}
              {isExpanded && (
                <div style={{
                  marginTop: '16px',
                  padding: '12px',
                  backgroundColor: '#f9f9f9',
                  borderRadius: '4px',
                  border: '1px solid #e0e0e0'
                }}>
                  <h4 style={{ marginTop: 0, marginBottom: '12px', fontSize: '14px', fontWeight: 'bold' }}>字段详情:</h4>
                  <div style={{ display: 'grid', gap: '8px' }}>
                    {Object.entries(note.fields || {}).map(([fieldName, fieldValue]) => {
                      const isPictureField = fieldName.toLowerCase() === 'picture';
                      return (
                        <div key={fieldName} style={{ 
                          display: 'flex', 
                          gap: '12px',
                          alignItems: isPictureField ? 'flex-start' : 'center'
                        }}>
                          <strong style={{ minWidth: '120px', color: '#666', fontSize: '0.9em' }}>
                            {fieldName}:
                          </strong>
                          <div style={{ 
                            flex: 1, 
                            wordBreak: 'break-word',
                            whiteSpace: 'pre-wrap',
                            fontSize: '0.9em'
                          }}>
                            {renderFieldValue(fieldName, fieldValue)}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                toggleExpandNote(note.note_id);
              }}
              style={{ padding: '5px 10px' }}
            >
              {isExpanded ? '收起' : '展开'}
            </button>
          </div>
        </div>
      );
    }
  };

  return (
    <div style={{ padding: '20px' }}>
      <h2>拼音学习 (Pinyin Learning)</h2>
      <p style={{ color: '#666', marginBottom: '20px' }}>
        拼音学习功能，适合非语言儿童使用拼音作为有效的输出方式。
      </p>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '10px', marginBottom: '20px', borderBottom: '2px solid #ddd' }}>
        <button
          onClick={() => {
            // Don't clear selection when switching tabs - allow selecting from both
            setActiveTab('elements');
            setExpandedNote(null);
          }}
          style={{
            padding: '10px 20px',
            border: 'none',
            borderBottom: activeTab === 'elements' ? '3px solid #2196f3' : '3px solid transparent',
            backgroundColor: 'transparent',
            cursor: 'pointer',
            fontWeight: activeTab === 'elements' ? 'bold' : 'normal'
          }}
        >
          拼音元素 ({elementNotes.length})
        </button>
        <button
          onClick={() => {
            // Don't clear selection when switching tabs - allow selecting from both
            setActiveTab('syllables');
            setExpandedNote(null);
          }}
          style={{
            padding: '10px 20px',
            border: 'none',
            borderBottom: activeTab === 'syllables' ? '3px solid #2196f3' : '3px solid transparent',
            backgroundColor: 'transparent',
            cursor: 'pointer',
            fontWeight: activeTab === 'syllables' ? 'bold' : 'normal'
          }}
        >
          拼音音节 ({syllableNotes.length})
        </button>
      </div>

      {/* Display count info */}
      {!showMastered && masteredItems.size > 0 && (
        <div style={{ 
          padding: '8px 12px', 
          marginBottom: '15px', 
          backgroundColor: '#e3f2fd', 
          borderRadius: '4px',
          fontSize: '0.9em',
          color: '#1976d2'
        }}>
          已隐藏 {masteredItems.size} 个已掌握项目。勾选上方"显示已掌握"可查看全部。
        </div>
      )}

      {/* Filter and Action buttons */}
      <div style={{ display: 'flex', gap: '10px', marginBottom: '20px', alignItems: 'center', flexWrap: 'wrap' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showMastered}
            onChange={(e) => setShowMastered(e.target.checked)}
            style={{ cursor: 'pointer' }}
          />
          <span>显示已掌握 ({masteredItems.size})</span>
        </label>
        <div style={{ flex: 1 }}></div>
        <button
          onClick={deleteSelectedNotes}
          disabled={selectedNotes.size === 0 || deleting}
          style={{
            padding: '10px 20px',
            backgroundColor: selectedNotes.size > 0 ? '#f44336' : '#ccc',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: selectedNotes.size > 0 ? 'pointer' : 'not-allowed',
            marginRight: '10px'
          }}
        >
          {deleting ? '删除中...' : `删除选中 (${selectedNotes.size} 个)`}
        </button>
        <button
          onClick={syncToAnki}
          disabled={selectedNotes.size === 0 || syncing}
          style={{
            padding: '10px 20px',
            backgroundColor: selectedNotes.size > 0 ? '#4caf50' : '#ccc',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: selectedNotes.size > 0 ? 'pointer' : 'not-allowed'
          }}
        >
          {syncing ? '同步中...' : `同步到 Anki (${selectedNotes.size} 个)`}
        </button>
        <button
          onClick={loadNotes}
          disabled={loading}
          style={{
            padding: '10px 20px',
            backgroundColor: '#2196f3',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          {loading ? '加载中...' : '刷新'}
        </button>
      </div>

      {/* Sync result */}
      {syncResult && (
        <div style={{
          padding: '10px',
          marginBottom: '20px',
          backgroundColor: syncResult.errors?.length > 0 ? '#ffebee' : '#e8f5e9',
          borderRadius: '4px'
        }}>
          {syncResult.message && <div>{syncResult.message}</div>}
          {syncResult.errors && syncResult.errors.length > 0 && (
            <div style={{ marginTop: '10px', color: '#c62828' }}>
              <strong>错误:</strong>
              <ul>
                {syncResult.errors.map((err, idx) => (
                  <li key={idx}>{err.note_id}: {err.error}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Notes list */}
      {loading ? (
        <div>加载中...</div>
      ) : currentNotes.length === 0 ? (
        <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
          没有找到笔记
        </div>
      ) : (
        <div>
          {currentNotes.map(note => renderNoteCard(note))}
        </div>
      )}
    </div>
  );
};

export default PinyinLearning;

