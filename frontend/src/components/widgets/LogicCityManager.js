import React, { useState, useEffect } from 'react';
import axios from 'axios';
import theme from '../../styles/theme';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/**
 * Image component with fallback paths (similar to PinyinLearning)
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
    `${API_BASE}/media/visual_images/${filename}`,
    `${API_BASE}/media/pinyin/${filename}`,
    `${API_BASE}/media/character_recognition/${filename}`,
    `${API_BASE}/media/chinese_word_recognition/${filename}`,
    `${API_BASE}/media/images/${filename}`,
    `${API_BASE}/media/${filename}`
  );
  
  // If src was a relative path (not starting with /), try it with /media/ prefix
  if (!src.startsWith('/') && !src.startsWith('http')) {
    alternativePaths.push(`${API_BASE}/media/${src}`);
  }
  
  // Last resort: try direct filename at root (shouldn't work but might catch edge cases)
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
 * Logic City Manager Component (词汇进阶)
 * Full management tool for Logic City vocabulary with editing and sync capabilities
 */
const LogicCityManager = ({ profile, onClose }) => {
  const [vocabulary, setVocabulary] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  
  // Configuration toggles
  const [showPinyin, setShowPinyin] = useState(true);
  const [nonVerbalMode, setNonVerbalMode] = useState(false);
  const [hideMastered, setHideMastered] = useState(false);
  const [viewMode, setViewMode] = useState('list'); // 'list' or 'grid'
  
  // Edit state
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({});
  
  useEffect(() => {
    fetchVocabulary();
  }, [hideMastered, profile?.id, page]);
  
  const fetchVocabulary = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const params = {
        page: page,
        page_size: pageSize,
        filter_mastered: hideMastered,
        sort_order: 'anki_default'
      };
      
      if (profile?.id) {
        params.profile_id = profile.id;
      }
      
      const response = await axios.get(`${API_BASE}/literacy/logic-city/vocab`, { params });
      const data = response.data || {};
      
      // Handle new paginated response format
      if (data.items) {
        setVocabulary(data.items || []);
        setTotal(data.total || 0);
        setTotalPages(data.total_pages || 0);
      } else {
        // Fallback for old format (flat array)
        setVocabulary(Array.isArray(data) ? data : []);
        setTotal(Array.isArray(data) ? data.length : 0);
        setTotalPages(1);
      }
    } catch (err) {
      console.error('Error fetching Logic City vocabulary:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to load vocabulary');
    } finally {
      setLoading(false);
    }
  };
  
  const handleEdit = (item) => {
    setEditingId(item.word_id);
    setEditForm({
      custom_image_path: item.custom_image_path || '',
      chinese: item.chinese || '',
      pinyin: item.pinyin || '',
      notes: item.notes || ''
    });
  };
  
  const handleSave = async (wordId) => {
    try {
      await axios.put(`${API_BASE}/literacy/logic-city/vocab/${wordId}`, editForm);
      
      // Update local state with all edited fields
      setVocabulary(vocab => vocab.map(item => 
        item.word_id === wordId 
          ? { 
              ...item, 
              custom_image_path: editForm.custom_image_path || item.custom_image_path,
              chinese: editForm.chinese || item.chinese,
              pinyin: editForm.pinyin || item.pinyin,
              notes: editForm.notes || item.notes
            }
          : item
      ));
      
      setEditingId(null);
      setEditForm({});
    } catch (err) {
      console.error('Error updating vocabulary:', err);
      alert(err.response?.data?.detail || 'Failed to update vocabulary');
    }
  };
  
  const handleCancel = () => {
    setEditingId(null);
    setEditForm({});
  };
  
  const handleSync = async () => {
    try {
      const wordIds = vocabulary
        .filter(item => item.is_synced === false)
        .map(item => item.word_id);
      
      if (wordIds.length === 0) {
        alert('No items to sync');
        return;
      }
      
      const response = await axios.post(`${API_BASE}/literacy/logic-city/sync`, {
        word_ids: wordIds,
        deck_name: 'English Vocabulary Level 2'
      });
      
      alert(`Sync initiated for ${wordIds.length} words`);
      
      // Refresh vocabulary to update sync status
      fetchVocabulary();
    } catch (err) {
      console.error('Error syncing to Anki:', err);
      alert(err.response?.data?.detail || 'Failed to sync to Anki');
    }
  };
  
  const handleImageError = (e) => {
    if (e.target.dataset.errorHandled === 'true') {
      return;
    }
    e.target.dataset.errorHandled = 'true';
    e.target.style.display = 'none';
    
    const fallback = e.target.parentElement?.querySelector('.image-fallback');
    if (fallback) {
      fallback.style.display = 'flex';
    }
  };
  
  // Reset to page 1 when filters change
  useEffect(() => {
    if (page !== 1) {
      setPage(1);
    }
  }, [hideMastered]);
  
  if (loading) {
    return (
      <div style={{ padding: theme.spacing.xl, textAlign: 'center' }}>
        <div>Loading vocabulary...</div>
      </div>
    );
  }
  
  if (error) {
    return (
      <div style={{ padding: theme.spacing.xl, textAlign: 'center', color: 'red' }}>
        <div>Error: {error}</div>
        <button 
          onClick={fetchVocabulary}
          style={{
            marginTop: theme.spacing.md,
            padding: '8px 16px',
            backgroundColor: theme.categories.language.primary,
            color: 'white',
            border: 'none',
            borderRadius: theme.borderRadius.md,
            cursor: 'pointer'
          }}
        >
          Retry
        </button>
      </div>
    );
  }
  
  return (
    <div style={{ 
      padding: '20px',
      backgroundColor: theme.ui.background,
      minHeight: '100vh'
    }}>
      {/* Header - Full page style like PinyinLearning */}
      <div style={{
        marginBottom: theme.spacing.lg
      }}>
        <h2 style={{ 
          margin: '0 0 10px 0',
          fontSize: '24px',
          fontWeight: 'bold',
          color: theme.ui.text.primary
        }}>
          词汇进阶 (Advanced Vocabulary)
        </h2>
        <p style={{ 
          color: theme.ui.text.secondary, 
          marginBottom: '20px',
          fontSize: '14px'
        }}>
          逻辑城市词汇管理工具，支持编辑、同步和掌握状态跟踪。
        </p>
      </div>
      
      {/* Configuration Panel */}
      <div style={{
        display: 'flex',
        gap: theme.spacing.md,
        flexWrap: 'wrap',
        marginBottom: theme.spacing.lg,
        padding: theme.spacing.md,
        backgroundColor: theme.ui.surface,
        borderRadius: theme.borderRadius.md,
        border: `1px solid ${theme.ui.border}`
      }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showPinyin}
            onChange={(e) => setShowPinyin(e.target.checked)}
          />
          <span>Show Pinyin</span>
        </label>
        
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={nonVerbalMode}
            onChange={(e) => setNonVerbalMode(e.target.checked)}
          />
          <span>Non-Verbal Mode</span>
        </label>
        
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={hideMastered}
            onChange={(e) => setHideMastered(e.target.checked)}
          />
          <span>Hide Mastered</span>
        </label>
        
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
          <button
            onClick={() => setViewMode('list')}
            style={{
              padding: '6px 12px',
              backgroundColor: viewMode === 'list' ? theme.categories.language.primary : theme.ui.background,
              color: viewMode === 'list' ? 'white' : theme.ui.text.primary,
              border: `1px solid ${theme.ui.border}`,
              borderRadius: theme.borderRadius.sm,
              cursor: 'pointer',
              fontSize: '12px'
            }}
          >
            List
          </button>
          <button
            onClick={() => setViewMode('grid')}
            style={{
              padding: '6px 12px',
              backgroundColor: viewMode === 'grid' ? theme.categories.language.primary : theme.ui.background,
              color: viewMode === 'grid' ? 'white' : theme.ui.text.primary,
              border: `1px solid ${theme.ui.border}`,
              borderRadius: theme.borderRadius.sm,
              cursor: 'pointer',
              fontSize: '12px'
            }}
          >
            Grid
          </button>
        </div>
        
        <button
          onClick={handleSync}
          style={{
            padding: '8px 16px',
            backgroundColor: '#10b981',
            color: 'white',
            border: 'none',
            borderRadius: theme.borderRadius.md,
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 'bold'
          }}
        >
          Sync to Anki
        </button>
      </div>
      
      {/* Vocabulary List/Grid */}
      {vocabulary.length === 0 && !loading ? (
        <div style={{ 
          textAlign: 'center', 
          padding: theme.spacing.xl, 
          color: theme.ui.text.secondary 
        }}>
          No vocabulary items found.
        </div>
      ) : (
        <>
          <div style={{
            display: viewMode === 'grid' ? 'grid' : 'flex',
            gridTemplateColumns: viewMode === 'grid' ? 'repeat(auto-fill, minmax(300px, 1fr))' : 'none',
            flexDirection: viewMode === 'list' ? 'column' : 'row',
            gap: theme.spacing.md
          }}>
            {vocabulary.map((item) => {
            const isEditing = editingId === item.word_id;
            const imagePath = item.custom_image_path || item.image_path;
            const displayPinyin = item.pinyin || '';
            
            return (
              <div
                key={item.word_id}
                style={{
                  backgroundColor: theme.ui.surface,
                  borderRadius: theme.borderRadius.md,
                  padding: theme.spacing.md,
                  boxShadow: theme.shadows.sm,
                  border: `1px solid ${theme.ui.border}`,
                  opacity: item.is_mastered ? 0.6 : 1,
                  position: 'relative'
                }}
              >
                {/* Sync Status Indicator */}
                {item.is_synced && (
                  <div style={{
                    position: 'absolute',
                    top: '8px',
                    right: '8px',
                    width: '12px',
                    height: '12px',
                    borderRadius: '50%',
                    backgroundColor: '#10b981',
                    border: '2px solid white',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
                  }} title="Synced to Anki" />
                )}
                
                {/* Edit Button */}
                {!isEditing && (
                  <button
                    onClick={() => handleEdit(item)}
                    style={{
                      position: 'absolute',
                      top: '8px',
                      right: item.is_synced ? '28px' : '8px',
                      padding: '4px 8px',
                      backgroundColor: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '18px'
                    }}
                    title="Edit"
                  >
                    ✏️
                  </button>
                )}
                
                {/* Card Content */}
                <div style={{
                  display: 'flex',
                  flexDirection: viewMode === 'list' ? 'row' : 'column',
                  gap: theme.spacing.md,
                  alignItems: viewMode === 'list' ? 'center' : 'flex-start'
                }}>
                  {/* Image (Left) */}
                  <div style={{
                    width: viewMode === 'list' ? '150px' : '100%',
                    height: viewMode === 'list' ? '150px' : '200px',
                    backgroundColor: theme.ui.background,
                    borderRadius: theme.borderRadius.sm,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    overflow: 'hidden',
                    position: 'relative',
                    flexShrink: 0
                  }}>
                    {isEditing ? (
                      <div style={{
                        width: '100%',
                        height: '100%',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '8px',
                        border: `2px dashed ${theme.ui.border}`,
                        borderRadius: theme.borderRadius.sm
                      }}>
                        <input
                          type="text"
                          placeholder="Custom image path"
                          value={editForm.custom_image_path || ''}
                          onChange={(e) => setEditForm({ ...editForm, custom_image_path: e.target.value })}
                          style={{
                            width: '90%',
                            padding: '4px',
                            fontSize: '12px',
                            border: `1px solid ${theme.ui.border}`,
                            borderRadius: theme.borderRadius.sm
                          }}
                        />
                        <div style={{ fontSize: '12px', color: theme.ui.text.secondary }}>
                          Upload/Select Image
                        </div>
                      </div>
                    ) : imagePath ? (
                      <ImageWithFallback
                        src={imagePath}
                        alt={item.english}
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
                  
                  {/* Chinese + Pinyin (Center) */}
                  <div style={{
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: theme.spacing.xs,
                    alignItems: viewMode === 'list' ? 'flex-start' : 'center',
                    textAlign: viewMode === 'list' ? 'left' : 'center'
                  }}>
                    {isEditing ? (
                      <>
                        <input
                          type="text"
                          placeholder="Chinese (中文)"
                          value={editForm.chinese || ''}
                          onChange={(e) => setEditForm({ ...editForm, chinese: e.target.value })}
                          style={{
                            width: '100%',
                            padding: '6px',
                            fontSize: '16px',
                            border: `1px solid ${theme.ui.border}`,
                            borderRadius: theme.borderRadius.sm,
                            marginBottom: '8px'
                          }}
                        />
                        <input
                          type="text"
                          placeholder="Pinyin"
                          value={editForm.pinyin || ''}
                          onChange={(e) => setEditForm({ ...editForm, pinyin: e.target.value })}
                          style={{
                            width: '100%',
                            padding: '6px',
                            fontSize: '14px',
                            border: `1px solid ${theme.ui.border}`,
                            borderRadius: theme.borderRadius.sm,
                            marginBottom: '8px'
                          }}
                        />
                        <textarea
                          placeholder="Notes"
                          value={editForm.notes || ''}
                          onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                          style={{
                            width: '100%',
                            padding: '6px',
                            fontSize: '12px',
                            border: `1px solid ${theme.ui.border}`,
                            borderRadius: theme.borderRadius.sm,
                            minHeight: '60px',
                            resize: 'vertical',
                            marginBottom: '8px'
                          }}
                        />
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button
                            onClick={() => handleSave(item.word_id)}
                            style={{
                              padding: '4px 12px',
                              backgroundColor: '#10b981',
                              color: 'white',
                              border: 'none',
                              borderRadius: theme.borderRadius.sm,
                              cursor: 'pointer',
                              fontSize: '12px'
                            }}
                          >
                            Save
                          </button>
                          <button
                            onClick={handleCancel}
                            style={{
                              padding: '4px 12px',
                              backgroundColor: theme.ui.background,
                              color: theme.ui.text.primary,
                              border: `1px solid ${theme.ui.border}`,
                              borderRadius: theme.borderRadius.sm,
                              cursor: 'pointer',
                              fontSize: '12px'
                            }}
                          >
                            Cancel
                          </button>
                        </div>
                      </>
                    ) : (
                      <>
                        {item.chinese && (
                          <div style={{
                            fontSize: '24px',
                            fontWeight: 'bold',
                            color: theme.ui.text.primary
                          }}>
                            {item.chinese}
                          </div>
                        )}
                        {showPinyin && displayPinyin && (
                          <div style={{
                            fontSize: '16px',
                            fontStyle: 'italic',
                            color: theme.ui.text.secondary
                          }}>
                            {displayPinyin}
                          </div>
                        )}
                        {item.notes && (
                          <div style={{
                            fontSize: '12px',
                            color: theme.ui.text.secondary,
                            marginTop: '4px',
                            fontStyle: 'italic'
                          }}>
                            {item.notes}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                  
                  {/* English (Right) */}
                  <div style={{
                    fontSize: viewMode === 'list' ? '18px' : '20px',
                    fontWeight: 'bold',
                    color: theme.ui.text.primary,
                    textAlign: viewMode === 'list' ? 'right' : 'center',
                    minWidth: viewMode === 'list' ? '150px' : 'auto'
                  }}>
                    {item.english}
                  </div>
                </div>
              </div>
            );
          })}
          </div>
          
          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div style={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              gap: theme.spacing.md,
              marginTop: theme.spacing.xl,
              paddingTop: theme.spacing.lg,
              borderTop: `1px solid ${theme.ui.border}`
            }}>
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                style={{
                  padding: '8px 16px',
                  backgroundColor: page === 1 ? theme.ui.background : theme.categories.language.primary,
                  color: page === 1 ? theme.ui.text.secondary : 'white',
                  border: 'none',
                  borderRadius: theme.borderRadius.md,
                  cursor: page === 1 ? 'not-allowed' : 'pointer',
                  opacity: page === 1 ? 0.5 : 1,
                  fontSize: '14px',
                  fontWeight: '500'
                }}
              >
                ← Previous
              </button>
              
              <span style={{ 
                color: theme.ui.text.primary,
                fontSize: '14px',
                minWidth: '120px',
                textAlign: 'center'
              }}>
                Page {page} of {totalPages}
                <br />
                <span style={{ fontSize: '12px', color: theme.ui.text.secondary }}>
                  ({total} total items)
                </span>
              </span>
              
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                style={{
                  padding: '8px 16px',
                  backgroundColor: page >= totalPages ? theme.ui.background : theme.categories.language.primary,
                  color: page >= totalPages ? theme.ui.text.secondary : 'white',
                  border: 'none',
                  borderRadius: theme.borderRadius.md,
                  cursor: page >= totalPages ? 'not-allowed' : 'pointer',
                  opacity: page >= totalPages ? 0.5 : 1,
                  fontSize: '14px',
                  fontWeight: '500'
                }}
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default LogicCityManager;

