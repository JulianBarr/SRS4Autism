import React, { useState, useEffect } from 'react';
import { cloudApi } from '../utils/api';

const TeacherPendingDrafts = () => {
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState({ show: false, message: '', type: 'success' });
  const [editedContents, setEditedContents] = useState({});

  useEffect(() => {
    fetchPendingDrafts();
  }, []);

  const fetchPendingDrafts = async () => {
    setLoading(true);
    try {
      const response = await cloudApi.get('/api/v1/teacher/drafts/pending');
      setDrafts(response.data);
      
      const initialEdits = {};
      response.data.forEach(draft => {
        const id = draft.id || draft.draft_id;
        initialEdits[id] = draft.draft_content || '';
      });
      setEditedContents(initialEdits);
    } catch (error) {
      console.error('Failed to fetch pending drafts:', error);
      showToast(error.response?.data?.detail || '获取待审批草稿失败', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleEditChange = (id, newContent) => {
    setEditedContents(prev => ({
      ...prev,
      [id]: newContent
    }));
  };

  const handleApprove = async (draftId) => {
    try {
      const editedContent = editedContents[draftId];
      await cloudApi.post(`/api/v1/teacher/drafts/${draftId}/approve`, {
        edited_content: editedContent
      });
      
      showToast('✅ 审批成功并已发送', 'success');
      
      // Remove from list
      setDrafts(prev => prev.filter(d => (d.id || d.draft_id) !== draftId));
    } catch (error) {
      console.error('Failed to approve draft:', error);
      showToast(error.response?.data?.detail || '审批失败，请重试', 'error');
    }
  };

  const showToast = (message, type = 'success') => {
    setToast({ show: true, message, type });
    setTimeout(() => {
      setToast({ show: false, message: '', type: 'success' });
    }, 3000);
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center p-8 bg-white rounded-xl shadow-sm border border-slate-100 mb-6">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500"></div>
        <span className="ml-3 text-slate-500">加载待审批草稿中...</span>
      </div>
    );
  }

  if (drafts.length === 0) {
    return null; // Don't show anything if there are no pending drafts to save space
  }

  return (
    <div className="space-y-6 mb-8 w-full">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-slate-800 flex items-center">
          <span className="mr-2">📥</span> AI Copilot 审批工作台
        </h2>
        <span className="bg-purple-100 text-purple-700 px-3 py-1 rounded-full text-sm font-medium">
          {drafts.length} 个待审批
        </span>
      </div>

      {/* Toast Notification */}
      {toast.show && (
        <div className={`fixed top-4 right-4 px-6 py-3 rounded-lg shadow-lg z-50 transition-all ${
          toast.type === 'success' ? 'bg-emerald-500 text-white' : 'bg-red-500 text-white'
        }`}>
          {toast.message}
        </div>
      )}

      {/* Drafts List */}
      <div className="grid gap-6">
        {drafts.map((draft) => {
          const id = draft.id || draft.draft_id;
          return (
          <div key={id} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden hover:shadow-md transition-shadow">
            <div className="p-6">
              {/* Header */}
              <div className="flex justify-between items-center mb-4">
                <div className="flex items-center space-x-2">
                  <span className="text-lg font-bold text-slate-800">{draft.child_name || '未知儿童'}</span>
                </div>
                <span className="text-sm text-slate-500 bg-slate-100 px-3 py-1 rounded-full">
                  {new Date(draft.created_at || Date.now()).toLocaleString()}
                </span>
              </div>

              {/* Parent Original Request */}
              <div className="bg-slate-50 rounded-lg p-4 mb-6 border border-slate-100 relative">
                <div className="absolute -top-3 left-4 bg-slate-200 text-slate-700 px-3 py-0.5 rounded-full text-xs font-bold shadow-sm">
                  👤 家长求助
                </div>
                <div className="text-slate-700 whitespace-pre-wrap mt-2">{draft.parent_log_content}</div>
              </div>

              {/* AI Draft Area */}
              <div className="relative rounded-xl border-2 border-purple-200 bg-purple-50/30 p-1 mb-6 focus-within:border-purple-400 focus-within:ring-4 focus-within:ring-purple-100 transition-all">
                <div className="absolute -top-3 left-4 bg-gradient-to-r from-purple-500 to-indigo-500 text-white px-3 py-0.5 rounded-full text-xs font-bold flex items-center shadow-md">
                  <span className="mr-1">✨</span> AI 辅助起草
                </div>
                <textarea
                  className="w-full min-h-[120px] p-4 bg-transparent resize-none outline-none text-slate-800 leading-relaxed rounded-lg mt-2"
                  value={editedContents[id] !== undefined ? editedContents[id] : ''}
                  onChange={(e) => handleEditChange(id, e.target.value)}
                  placeholder="AI 草稿内容..."
                />
              </div>

              {/* Action Button */}
              <div className="flex justify-end border-t border-slate-100 pt-4 mt-2">
                <button
                  onClick={() => handleApprove(id)}
                  className="flex items-center px-6 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 text-white font-medium rounded-lg hover:from-purple-700 hover:to-indigo-700 shadow-sm hover:shadow active:scale-[0.98] transition-all"
                >
                  <span className="mr-2">🚀</span> 一键批准并发送
                </button>
              </div>
            </div>
          </div>
        )})}
      </div>
    </div>
  );
};

export default TeacherPendingDrafts;