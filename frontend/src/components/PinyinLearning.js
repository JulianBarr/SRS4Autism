import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

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
          params: { profile_id: profile.id }
        });
        setElementNotes(response.data.notes || []);
      } else {
        const response = await axios.get(`${API_BASE}/pinyin/syllables`, {
          params: { profile_id: profile.id }
        });
        setSyllableNotes(response.data.notes || []);
      }
      setSyncResult(null);
    } catch (error) {
      console.error('Error loading pinyin notes:', error);
      alert(`加载失败: ${error.response?.data?.detail || error.message}`);
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
    
    // If it's HTML (contains img or div tags), fix image paths and render as HTML
    if (fieldValue.includes('<img') || fieldValue.includes('<div')) {
      // Fix image src paths to point to backend media directory
      let fixedHtml = fieldValue;
      // Replace relative image paths with full backend URLs
      // Match img tags with src attribute (flexible spacing)
      fixedHtml = fixedHtml.replace(
        /<img([^>]*?)\s+src=["']([^"']+)["']([^>]*)>/gi,
        (match, before, src, after) => {
          // Skip if already a full URL
          if (src.startsWith('http') || src.startsWith('data:') || src.startsWith('/media')) {
            // If it's /media, prepend API_BASE
            if (src.startsWith('/media')) {
              return `<img${before} src="${API_BASE}${src}"${after}>`;
            }
            return match;
          }
          // Convert relative path to backend media URL
          const filename = src.split('/').pop(); // Get just the filename
          const fullUrl = `${API_BASE}/media/pinyin/${filename}`;
          return `<img${before} src="${fullUrl}"${after}>`;
        }
      );
      
      return (
        <div 
          dangerouslySetInnerHTML={{ __html: fixedHtml }}
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
        // Try different paths for the image
        // 1. If it's already a full URL or path, use it as-is
        // 2. Try /media/pinyin/ (where pinyin images are stored)
        // 3. Try /media/visual_images/ (for other images)
        // 4. Try direct filename (for Anki media files)
        let imageSrc = fieldValue;
        if (!fieldValue.startsWith('http') && !fieldValue.startsWith('/')) {
          // Try pinyin media path first (most likely for pinyin notes)
          imageSrc = `${API_BASE}/media/pinyin/${fieldValue}`;
        } else if (fieldValue.startsWith('/') && !fieldValue.startsWith('/media')) {
          // If it's a relative path, prepend /media/pinyin/
          imageSrc = `${API_BASE}/media/pinyin${fieldValue}`;
        } else if (fieldValue.startsWith('/media')) {
          // If it already has /media, just prepend API_BASE
          imageSrc = `${API_BASE}${fieldValue}`;
        }
        
        return (
          <div style={{ position: 'relative' }}>
            <img 
              src={imageSrc}
              alt={fieldName}
              style={{
                maxWidth: '200px',
                maxHeight: '200px',
                borderRadius: '4px',
                border: '1px solid #ddd',
                objectFit: 'contain',
                backgroundColor: '#f5f5f5'
              }}
              onError={(e) => {
                // Try alternative paths if first attempt fails
                const currentSrc = e.target.src;
                const filename = fieldValue.includes('/') ? fieldValue.split('/').pop() : fieldValue;
                
                // Try alternative paths
                const alternatives = [
                  `${API_BASE}/media/visual_images/${filename}`,
                  `${API_BASE}/media/${filename}`,
                  `/${filename}`,
                  filename
                ];
                
                const currentIndex = alternatives.indexOf(currentSrc);
                if (currentIndex < alternatives.length - 1) {
                  // Try next alternative
                  e.target.src = alternatives[currentIndex + 1];
                } else {
                  // All alternatives failed, show fallback text
                  const parent = e.target.parentNode;
                  e.target.style.display = 'none';
                  if (!parent.querySelector('.image-fallback')) {
                    const span = document.createElement('span');
                    span.className = 'image-fallback';
                    span.style.cssText = 'color: #666; font-size: 0.9em; font-style: italic;';
                    span.textContent = `[图片: ${fieldValue}]`;
                    parent.appendChild(span);
                  }
                }
              }}
            />
          </div>
        );
      }
    }
    
    // Otherwise, render as plain text
    return <span>{fieldValue}</span>;
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

