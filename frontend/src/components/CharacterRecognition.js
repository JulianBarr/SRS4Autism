import React, { useState, useEffect } from 'react';
import axios from 'axios';
import theme from '../styles/theme';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/**
 * Image component with fallback paths (similar to LogicCityManager)
 */
const ImageWithFallback = ({ src, alt, style, className }) => {
  const [currentPathIndex, setCurrentPathIndex] = React.useState(0);
  const [imageKey, setImageKey] = React.useState(0);
  
  if (!src) {
    return null;
  }
  
  // Extract filename from src (could be just filename or full path)
  const filename = src.includes('/') ? src.split('/').pop() : src;
  
  if (!filename) {
    return null;
  }
  
  // Build list of alternative paths to try
  const alternativePaths = [];
  
  // If src is already a full URL or starts with /media/, try it first
  if (src.startsWith('http://') || src.startsWith('https://')) {
    alternativePaths.push(src);
  } else if (src.startsWith('/media/')) {
    alternativePaths.push(`${API_BASE}${src}`);
  } else if (src.startsWith('/')) {
    alternativePaths.push(`${API_BASE}${src}`);
  }
  
  // Then try with extracted filename in various media directories
  alternativePaths.push(
    `${API_BASE}/media/character_recognition/${filename}`,
    `${API_BASE}/media/visual_images/${filename}`,
    `${API_BASE}/media/pinyin/${filename}`,
    `${API_BASE}/media/chinese_word_recognition/${filename}`,
    `${API_BASE}/media/images/${filename}`,
    `${API_BASE}/media/${filename}`
  );
  
  // If src was a relative path (not starting with /), try it with /media/ prefix
  if (!src.startsWith('/') && !src.startsWith('http')) {
    alternativePaths.push(`${API_BASE}/media/${src}`);
  }
  
  // Last resort: try direct filename at root
  alternativePaths.push(`${API_BASE}/${filename}`);
  
  // Remove duplicates while preserving order
  const uniquePaths = [...new Set(alternativePaths)];
  
  const currentSrc = uniquePaths[currentPathIndex] || uniquePaths[0];
  
  const handleError = () => {
    if (currentPathIndex < uniquePaths.length - 1) {
      setCurrentPathIndex(currentPathIndex + 1);
      setImageKey(imageKey + 1); // Force re-render
    } else {
      // All paths failed, show placeholder
      console.warn(`Image failed to load: ${src} (tried ${uniquePaths.length} paths)`);
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
 * Extract image source from HTML field value
 */
const extractImageSrc = (fieldValue) => {
  if (!fieldValue || typeof fieldValue !== 'string') return null;
  
  // Try to extract from <img> tag
  const imgMatch = fieldValue.match(/<img[^>]*\s+src=["']([^"']+)["'][^>]*>/i);
  if (imgMatch) {
    return imgMatch[1];
  }
  
  // If it's just a filename, return it
  if (fieldValue && !fieldValue.includes('<') && !fieldValue.includes('>')) {
    return fieldValue;
  }
  
  return null;
};

/**
 * Find image from character recognition note fields
 * Checks multiple possible field names
 */
const findImageFromFields = (fields) => {
  // Check common image field names (case-insensitive)
  const imageFieldNames = ['Image', 'image', 'Picture', 'picture', 'Representation', 'representation', 'REPRESENTATION'];
  
  for (const fieldName of imageFieldNames) {
    const fieldValue = fields[fieldName];
    if (fieldValue) {
      const imageSrc = extractImageSrc(fieldValue);
      if (imageSrc) {
        return imageSrc;
      }
    }
  }
  
  // Also check all fields for image tags
  for (const [fieldName, fieldValue] of Object.entries(fields)) {
    if (fieldValue && typeof fieldValue === 'string' && fieldValue.includes('<img')) {
      const imageSrc = extractImageSrc(fieldValue);
      if (imageSrc) {
        return imageSrc;
      }
    }
  }
  
  return null;
};

/**
 * Extract pinyin from fields
 */
const extractPinyin = (fields) => {
  return fields.Pinyin || fields.pinyin || '';
};

/**
 * Character Recognition Component
 * Refactored to match LogicCityManager design
 */
const CharacterRecognition = ({ profile, onProfileUpdate }) => {
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedNotes, setSelectedNotes] = useState(new Set());
  const [selectedNoteForDetail, setSelectedNoteForDetail] = useState(null);
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

  const handleEdit = (note) => {
    setSelectedNoteForDetail(note);
  };

  const closeDetailModal = () => {
    setSelectedNoteForDetail(null);
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
    <div style={{ padding: theme.spacing.lg }}>
      {/* Header */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        marginBottom: theme.spacing.lg
      }}>
        <h2 style={{ margin: 0, fontSize: '28px', fontWeight: 'bold', color: theme.ui.text.primary }}>
          汉字识认
        </h2>
        <div style={{ display: 'flex', gap: theme.spacing.sm, flexWrap: 'wrap' }}>
          <button
            onClick={loadNotes}
            disabled={loading}
            style={{
              padding: '8px 16px',
              backgroundColor: theme.actions.success,
              color: 'white',
              border: 'none',
              borderRadius: theme.borderRadius.md,
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              fontWeight: '500'
            }}
          >
            {loading ? '加载中...' : '刷新'}
          </button>
          <button
            onClick={selectAll}
            style={{
              padding: '8px 16px',
              backgroundColor: theme.actions.info,
              color: 'white',
              border: 'none',
              borderRadius: theme.borderRadius.md,
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: '500'
            }}
          >
            全选
          </button>
          <button
            onClick={deselectAll}
            style={{
              padding: '8px 16px',
              backgroundColor: theme.actions.warning,
              color: 'white',
              border: 'none',
              borderRadius: theme.borderRadius.md,
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: '500'
            }}
          >
            取消全选
          </button>
          <button
            onClick={markAsMastered}
            disabled={selectedNotes.size === 0}
            style={{
              padding: '8px 16px',
              backgroundColor: selectedNotes.size === 0 ? theme.ui.border : theme.actions.success,
              color: 'white',
              border: 'none',
              borderRadius: theme.borderRadius.md,
              cursor: selectedNotes.size === 0 ? 'not-allowed' : 'pointer',
              fontWeight: 'bold',
              fontSize: '14px'
            }}
          >
            标记为已掌握 ({selectedNotes.size})
          </button>
          <button
            onClick={syncToAnki}
            disabled={syncing || selectedNotes.size === 0}
            style={{
              padding: '8px 16px',
              backgroundColor: syncing || selectedNotes.size === 0 ? theme.ui.border : theme.categories.culture.primary,
              color: 'white',
              border: 'none',
              borderRadius: theme.borderRadius.md,
              cursor: syncing || selectedNotes.size === 0 ? 'not-allowed' : 'pointer',
              fontWeight: 'bold',
              fontSize: '14px'
            }}
          >
            {syncing ? '同步中...' : `同步到 Anki (${selectedNotes.size})`}
          </button>
        </div>
      </div>

      {syncResult && (
        <div style={{
          padding: theme.spacing.md,
          marginBottom: theme.spacing.lg,
          backgroundColor: syncResult.success ? theme.statusBackgrounds.success : theme.statusBackgrounds.error,
          border: `1px solid ${syncResult.success ? theme.status.success : theme.status.error}`,
          borderRadius: theme.borderRadius.md,
          color: syncResult.success ? theme.status.success : theme.status.error
        }}>
          {syncResult.message}
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: theme.spacing.xl }}>
          <p style={{ color: theme.ui.text.secondary }}>加载中...</p>
        </div>
      ) : notes.length === 0 ? (
        <div style={{ textAlign: 'center', padding: theme.spacing.xl }}>
          <p style={{ color: theme.ui.text.secondary }}>没有找到字符识别笔记，或所有字符都已掌握。</p>
        </div>
      ) : (
        <div>
          <p style={{ marginBottom: theme.spacing.lg, color: theme.ui.text.secondary, fontSize: '14px' }}>
            共 {notes.length} 个字符（已过滤已掌握的字符）
          </p>
          
          {/* Character List - Matching LogicCityManager Design */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: theme.spacing.md }}>
            {notes.map((note) => {
              const imageSrc = findImageFromFields(note.fields);
              const pinyin = extractPinyin(note.fields);
              
              return (
                <div
                  key={note.note_id}
                  style={{
                    backgroundColor: theme.ui.surface,
                    borderRadius: theme.borderRadius.md,
                    padding: theme.spacing.md,
                    boxShadow: theme.shadows.sm,
                    border: `1px solid ${theme.ui.border}`,
                    position: 'relative'
                  }}
                >
                  {/* Edit Button */}
                  <button
                    onClick={() => handleEdit(note)}
                    style={{
                      position: 'absolute',
                      top: '8px',
                      right: '8px',
                      padding: '4px 8px',
                      backgroundColor: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '18px'
                    }}
                    title="查看详情"
                  >
                    ✏️
                  </button>
                  
                  {/* Card Content */}
                  <div style={{
                    display: 'flex',
                    flexDirection: 'row',
                    gap: theme.spacing.md,
                    alignItems: 'center'
                  }}>
                    {/* Image (Left) */}
                    <div style={{
                      width: '150px',
                      height: '150px',
                      backgroundColor: theme.ui.background,
                      borderRadius: theme.borderRadius.sm,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      overflow: 'hidden',
                      position: 'relative',
                      flexShrink: 0
                    }}>
                      {imageSrc ? (
                        <ImageWithFallback
                          src={imageSrc}
                          alt={note.fields.Concept || note.character}
                          style={{
                            width: '100%',
                            height: '100%',
                            objectFit: 'cover'
                          }}
                        />
                      ) : (
                        <div style={{
                          color: theme.ui.text.secondary,
                          fontSize: '48px'
                        }}>
                          📷
                        </div>
                      )}
                    </div>
                    
                    {/* Character + Pinyin (Center) */}
                    <div style={{
                      flex: 1,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: theme.spacing.xs,
                      alignItems: 'flex-start',
                      textAlign: 'left'
                    }}>
                      <div style={{
                        fontSize: '32px',
                        fontWeight: 'bold',
                        color: theme.ui.text.primary
                      }}>
                        {note.character}
                      </div>
                      {pinyin && (
                        <div style={{
                          fontSize: '16px',
                          fontStyle: 'italic',
                          color: theme.ui.text.secondary
                        }}>
                          {pinyin}
                        </div>
                      )}
                      {note.fields.Concept && (
                        <div style={{
                          fontSize: '14px',
                          color: theme.ui.text.secondary,
                          marginTop: theme.spacing.xs
                        }}>
                          {note.fields.Concept}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {selectedNoteForDetail && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '20px'
        }} onClick={closeDetailModal}>
          <div style={{
            backgroundColor: 'white',
            borderRadius: theme.borderRadius.lg,
            maxWidth: '800px',
            width: '100%',
            maxHeight: '90vh',
            overflow: 'auto',
            boxShadow: theme.shadows.lg,
            position: 'relative'
          }} onClick={(e) => e.stopPropagation()}>
            {/* Header */}
            <div style={{
              background: `linear-gradient(135deg, ${theme.categories.culture.primary} 0%, ${theme.categories.culture.dark} 100%)`,
              padding: theme.spacing.lg,
              borderRadius: `${theme.borderRadius.lg} ${theme.borderRadius.lg} 0 0`,
              position: 'relative',
              overflow: 'hidden'
            }}>
              <div style={{
                position: 'absolute',
                top: '-50px',
                right: '-50px',
                width: '200px',
                height: '200px',
                backgroundColor: 'rgba(255,255,255,0.1)',
                borderRadius: '50%',
                filter: 'blur(40px)'
              }}></div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', position: 'relative', zIndex: 10 }}>
                <div>
                  <h2 style={{ fontSize: '32px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
                    {selectedNoteForDetail.character}
                  </h2>
                  {extractPinyin(selectedNoteForDetail.fields) && (
                    <p style={{ fontSize: '18px', color: 'rgba(255,255,255,0.9)', fontWeight: '500' }}>
                      {extractPinyin(selectedNoteForDetail.fields)}
                    </p>
                  )}
                </div>
              </div>
              <button 
                onClick={closeDetailModal}
                style={{
                  position: 'absolute',
                  top: '16px',
                  right: '16px',
                  backgroundColor: 'rgba(255,255,255,0.3)',
                  border: 'none',
                  borderRadius: '50%',
                  width: '40px',
                  height: '40px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '24px',
                  color: 'white',
                  zIndex: 20
                }}
              >
                ×
              </button>
            </div>

            {/* Content */}
            <div style={{ padding: theme.spacing.lg, backgroundColor: '#f9fafb' }}>
              <h4 style={{ marginTop: 0, marginBottom: theme.spacing.md, color: theme.ui.text.primary }}>
                字段详情
              </h4>
              <div style={{ display: 'grid', gap: theme.spacing.md }}>
                {Object.entries(selectedNoteForDetail.fields).map(([fieldName, fieldValue]) => {
                  const isImageField = fieldName.toLowerCase() === 'image' || 
                                      fieldName.toLowerCase() === 'picture' || 
                                      fieldName.toLowerCase() === 'representation';
                  const isAudioField = fieldName.toLowerCase() === 'audio';
                  const imageSrc = isImageField ? extractImageSrc(fieldValue) : null;
                  
                  return (
                    <div key={fieldName} style={{
                      padding: theme.spacing.md,
                      backgroundColor: 'white',
                      borderRadius: theme.borderRadius.sm,
                      border: `1px solid ${theme.ui.border}`
                    }}>
                      <strong style={{ 
                        display: 'block',
                        marginBottom: theme.spacing.xs,
                        color: theme.ui.text.secondary,
                        fontSize: '12px',
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px'
                      }}>
                        {fieldName}:
                      </strong>
                      <div style={{ 
                        wordBreak: 'break-word',
                        whiteSpace: 'pre-wrap',
                        color: theme.ui.text.primary
                      }}>
                        {fieldValue ? (
                          isImageField && imageSrc ? (
                            <div style={{ marginTop: theme.spacing.xs }}>
                              <ImageWithFallback
                                src={imageSrc}
                                alt={fieldName}
                                style={{
                                  maxWidth: '300px',
                                  maxHeight: '300px',
                                  borderRadius: theme.borderRadius.sm,
                                  border: `1px solid ${theme.ui.border}`,
                                  objectFit: 'contain',
                                  backgroundColor: theme.ui.background
                                }}
                              />
                            </div>
                          ) : isAudioField ? (
                            <div style={{ marginTop: theme.spacing.xs }}>
                              <audio controls style={{ width: '100%', maxWidth: '400px' }}>
                                <source src={`${API_BASE}/media/character_recognition/${extractImageSrc(fieldValue)}`} />
                                Your browser does not support the audio element.
                              </audio>
                            </div>
                          ) : fieldValue.includes('<img') || fieldValue.includes('<div') ? (
                            <div 
                              dangerouslySetInnerHTML={{ __html: fieldValue }}
                              className="char-preview-img-container"
                            />
                          ) : (
                            fieldValue
                          )
                        ) : (
                          <span style={{ color: theme.ui.text.disabled, fontStyle: 'italic' }}>（空）</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CharacterRecognition;
