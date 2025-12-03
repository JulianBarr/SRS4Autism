import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/**
 * Chinese Word Recognition Component (CUMA Naming)
 * 
 * For verbal training - focuses on listening and speaking, not reading/writing.
 * Configurations:
 * - User Type: Verbal / Non-verbal
 * - Script: Simplified + Pinyin / Traditional + Bopomofo
 * - Caregiver manages mastered list
 * - Can add custom words
 */
const ChineseWordRecognition = ({ profile, onProfileUpdate }) => {
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedNotes, setSelectedNotes] = useState(new Set());
  const [expandedNote, setExpandedNote] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState(null);
  
  // Configuration states
  const [userType, setUserType] = useState('verbal'); // 'verbal' or 'non-verbal'
  const [scriptType, setScriptType] = useState('simplified-pinyin'); // 'simplified-pinyin' or 'traditional-bopomofo'
  
  // Add custom word state
  const [showAddWordDialog, setShowAddWordDialog] = useState(false);
  const [newWord, setNewWord] = useState({
    word: '',
    concept: '',
    pinyin: '',
    bopomofo: '',
    image: null
  });

  useEffect(() => {
    if (profile?.id) {
      loadNotes();
    }
  }, [profile?.id]);

  const loadNotes = async () => {
    if (!profile?.id) return;
    
    setLoading(true);
    try {
      const response = await axios.get(`${API_BASE}/word-recognition/notes`, {
        params: { profile_id: profile.id }
      });
      setNotes(response.data.notes || []);
      setSyncResult(null);
    } catch (error) {
      console.error('Error loading Chinese word recognition notes:', error);
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
      alert('请先选择要标记为已掌握的词汇');
      return;
    }

    const selectedWords = notes
      .filter(note => selectedNotes.has(note.note_id))
      .map(note => note.word);

    try {
      await axios.post(`${API_BASE}/profiles/${profile.id}/mastered-words`, {
        words: selectedWords,
        language: 'zh'
      });

      alert(`✅ 成功标记 ${selectedWords.length} 个词汇为已掌握`);
      
      // Reload notes to reflect the filter
      loadNotes();
      setSelectedNotes(new Set());
      
      // Notify parent to update profile
      if (onProfileUpdate) {
        onProfileUpdate();
      }
    } catch (error) {
      console.error('Error marking as mastered:', error);
      alert(`❌ 标记失败: ${error.response?.data?.detail || error.message}`);
    }
  };

  const syncToAnki = async () => {
    if (selectedNotes.size === 0) {
      alert('请先选择要同步的词汇');
      return;
    }

    if (!window.confirm(`确定要同步 ${selectedNotes.size} 个词汇到 Anki 吗？`)) {
      return;
    }

    setSyncing(true);
    setSyncResult(null);
    
    try {
      // Determine config based on script type
      const config = scriptType === 'simplified-pinyin' ? 'simplified' : 'traditional';
      
      const response = await axios.post(`${API_BASE}/chinese-naming/sync`, {
        profile_id: profile.id,
        note_ids: Array.from(selectedNotes),
        deck_name: '中文命名',
        config: config,
        user_type: userType,
        script_type: scriptType
      });

      setSyncResult({
        success: true,
        message: `成功同步 ${response.data.cards_created} 张卡片`,
        details: response.data
      });
      
      // Clear selection after successful sync
      setSelectedNotes(new Set());
      
      // Reload notes to reflect updated mastered list
      await loadNotes();
      
      alert(`✅ 同步成功！\n创建了 ${response.data.cards_created} 张卡片\n来自 ${response.data.notes_synced} 个词汇`);
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

  const handleAddCustomWord = async () => {
    if (!newWord.word || !newWord.concept) {
      alert('请填写词汇和概念');
      return;
    }
    
    try {
      const formData = new FormData();
      formData.append('word', newWord.word);
      formData.append('concept', newWord.concept);
      formData.append('pinyin', newWord.pinyin);
      formData.append('bopomofo', newWord.bopomofo);
      if (newWord.image) {
        formData.append('image', newWord.image);
      }
      
      await axios.post(`${API_BASE}/word-recognition/add-custom`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      alert('自定义词汇已添加！');
      setShowAddWordDialog(false);
      setNewWord({ word: '', concept: '', pinyin: '', bopomofo: '', image: null });
      loadNotes(); // Reload notes
    } catch (error) {
      console.error('Error adding custom word:', error);
      alert(`添加失败: ${error.response?.data?.detail || error.message}`);
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
        alignItems: 'flex-start',
        marginBottom: '20px'
      }}>
        <h2 style={{ margin: 0 }}>词汇识别 (概念 ⇔ 词)</h2>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', alignItems: 'flex-end' }}>
          {/* Configuration Section */}
          <div style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>
            {/* User Type Selection */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <label style={{ fontSize: '14px', fontWeight: 'bold', color: '#666' }}>
                用户类型:
              </label>
              <select 
                value={userType} 
                onChange={(e) => setUserType(e.target.value)}
                style={{ 
                  padding: '6px 12px', 
                  borderRadius: '4px', 
                  border: '1px solid #ddd',
                  fontSize: '14px',
                  cursor: 'pointer'
                }}
              >
                <option value="verbal">口语用户</option>
                <option value="non-verbal">非口语用户</option>
              </select>
            </div>
            
            {/* Script Type Selection */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <label style={{ fontSize: '14px', fontWeight: 'bold', color: '#666' }}>
                文字系统:
              </label>
              <select 
                value={scriptType} 
                onChange={(e) => setScriptType(e.target.value)}
                style={{ 
                  padding: '6px 12px', 
                  borderRadius: '4px', 
                  border: '1px solid #ddd',
                  fontSize: '14px',
                  cursor: 'pointer'
                }}
              >
                <option value="simplified-pinyin">简体 + 拼音</option>
                <option value="traditional-bopomofo">繁体 + 注音</option>
              </select>
            </div>
          </div>
          
          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <button
              onClick={loadNotes}
              disabled={loading}
              style={{
                padding: '8px 16px',
                backgroundColor: '#4CAF50',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: loading ? 'not-allowed' : 'pointer',
                fontSize: '14px',
                fontWeight: '500'
              }}
            >
              {loading ? '加载中...' : '刷新'}
            </button>
            
            <button
              onClick={() => setShowAddWordDialog(true)}
              style={{
                padding: '8px 16px',
                backgroundColor: '#2196F3',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: '500'
              }}
            >
              ➕ 添加自定义词汇
            </button>
            
            <button
              onClick={selectAll}
              style={{
                padding: '8px 16px',
                backgroundColor: '#2196F3',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
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
                backgroundColor: '#FF9800',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
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
                backgroundColor: selectedNotes.size === 0 ? '#ccc' : '#4CAF50',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: selectedNotes.size === 0 ? 'not-allowed' : 'pointer',
                fontSize: '14px',
                fontWeight: '500'
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
                fontSize: '14px',
                fontWeight: '500'
              }}
            >
              {syncing ? '同步中...' : `同步到 Anki (${selectedNotes.size})`}
            </button>
          </div>
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
          <p>没有找到词汇识别笔记，或所有词汇都已掌握。</p>
        </div>
      ) : (
        <div>
          <p style={{ marginBottom: '20px', color: '#666' }}>
            共 {notes.length} 个词汇（已过滤已掌握的词汇）
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
                  <div style={{ fontSize: '24px', fontWeight: 'bold', minWidth: '100px' }}>
                    {note.word}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '14px', color: '#666', marginBottom: '4px' }}>
                      笔记 ID: {note.note_id}
                    </div>
                    <div style={{ fontSize: '16px', color: '#333', fontWeight: '500' }}>
                      概念: {note.concept}
                    </div>
                    {note.fields.Pinyin && (
                      <div style={{ fontSize: '14px', color: '#666', marginTop: '4px' }}>
                        拼音: {note.fields.Pinyin}
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
                                <div 
                                  dangerouslySetInnerHTML={{ __html: fieldValue }}
                                  className="word-preview-img-container"
                                />
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
      
      {/* Add Custom Word Dialog */}
      {showAddWordDialog && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 2000
        }}>
          <div style={{
            backgroundColor: 'white', padding: '30px', borderRadius: '8px',
            maxWidth: '500px', width: '90%', position: 'relative'
          }}>
            <button onClick={() => setShowAddWordDialog(false)} style={{
              position: 'absolute', top: '10px', right: '10px',
              border: 'none', background: 'none', fontSize: '24px', cursor: 'pointer'
            }}>×</button>
            
            <h3 style={{ marginTop: 0 }}>添加自定义词汇</h3>
            
            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                中文词汇 *
              </label>
              <input
                type="text"
                value={newWord.word}
                onChange={(e) => setNewWord({...newWord, word: e.target.value})}
                placeholder="例如: 狮子"
                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ddd' }}
              />
            </div>
            
            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                英文概念 *
              </label>
              <input
                type="text"
                value={newWord.concept}
                onChange={(e) => setNewWord({...newWord, concept: e.target.value})}
                placeholder="例如: Lion"
                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ddd' }}
              />
            </div>
            
            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                拼音 (Pinyin)
              </label>
              <input
                type="text"
                value={newWord.pinyin}
                onChange={(e) => setNewWord({...newWord, pinyin: e.target.value})}
                placeholder="例如: shī zi"
                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ddd' }}
              />
            </div>
            
            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                注音 (Bopomofo)
              </label>
              <input
                type="text"
                value={newWord.bopomofo}
                onChange={(e) => setNewWord({...newWord, bopomofo: e.target.value})}
                placeholder="例如: ㄕ ㄗ˙"
                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ddd' }}
              />
            </div>
            
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                图片 (可选)
              </label>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setNewWord({...newWord, image: e.target.files[0]})}
                style={{ width: '100%' }}
              />
            </div>
            
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowAddWordDialog(false)}
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#ccc',
                  color: '#333',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
              >
                取消
              </button>
              <button
                onClick={handleAddCustomWord}
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#4CAF50',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
              >
                添加
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChineseWordRecognition;
