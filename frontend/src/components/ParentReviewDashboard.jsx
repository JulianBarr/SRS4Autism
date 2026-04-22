import React, { useState, useEffect } from 'react';
import api from '../utils/api';
import { Check, X, Edit3, Save, CheckCircle2, HeartHandshake, Sparkles, Info } from 'lucide-react';

const ParentReviewDashboard = ({ childId, childName }) => {
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState(null);
  const [localizingId, setLocalizingId] = useState(null);
  const [editFormData, setEditFormData] = useState({});
  const getDraftId = (draft) => draft?.quest_id || draft?.id || draft?.draft_id;
  const normalizeQuest = (q) => {
    return {
      ...q,
      quest_title: q.quest_title || q.label || '自定义任务',
      objective: q.objective || '',
      steps: Array.isArray(q.steps) ? q.steps : [],
    };
  };

  useEffect(() => {
    fetchDrafts();
  }, [childId, childName]);

  const fetchDrafts = async () => {
    setLoading(true);
    try {
      const response = await api.get('/api/quests/drafts', {
        params: {
          child_id: childId || undefined,
          child_name: childName || undefined,
        },
      });
      const draftItems = (response.data || []).map(normalizeQuest);
      setDrafts(draftItems);
    } catch (error) {
      console.error("Failed to fetch drafts", error);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (draftId) => {
    // Save any pending edits before approving
    if (editingId === draftId) {
       await handleSaveEdit(draftId);
    }
    
    // Find the current draft data to send
    const draftToApprove = drafts.find(d => getDraftId(d) === draftId) || {};

    try {
      await api.post(`/api/quests/drafts/${draftId}/approve`, {
        ...draftToApprove,
        child_id: childId || draftToApprove.child_id,
        child_name: childName || draftToApprove.child_name,
      });
      setDrafts(prev => prev.filter(d => getDraftId(d) !== draftId));
    } catch (error) {
      console.error("Failed to approve draft", error);
    }
  };

  const handleReject = async (draftId) => {
    try {
      await api.post(`/api/quests/drafts/${draftId}/reject`);
      setDrafts(prev => prev.filter(d => getDraftId(d) !== draftId));
    } catch (error) {
      console.error("Failed to reject draft", error);
    }
  };

  const startEdit = (draft) => {
    setEditingId(getDraftId(draft));
    setEditFormData({
      quest_title: draft.quest_title,
      steps: [...(draft.steps || [])] 
    });
  };

  const handleSaveEdit = async (draftId) => {
    const nextDraft = drafts.find((d) => getDraftId(d) === draftId);
    const payload = {
      quest_title: editFormData.quest_title,
      objective: nextDraft?.objective,
      steps: editFormData.steps,
      child_id: childId || nextDraft?.child_id,
      child_name: childName || nextDraft?.child_name,
    };
    try {
      await api.put(`/api/quests/drafts/${draftId}`, payload);
    } catch (error) {
      console.error("Failed to save draft edit", error);
    }
    setDrafts(prev => prev.map(d => {
      if (getDraftId(d) === draftId) {
        return { ...d, ...payload };
      }
      return d;
    }));
    setEditingId(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
  };

  const handleStepChange = (index, value) => {
     const newSteps = [...editFormData.steps];
     newSteps[index] = value;
     setEditFormData({ ...editFormData, steps: newSteps });
  };

  const handleAutoGenerateQuest = async () => {
    if (!childId || String(childId).trim() === '') {
      console.error(
        'Cannot auto-generate quest: stable child_id (profiles.id) is required — pick a child in the header.',
      );
      return;
    }
    setLoading(true);
    try {
        await api.post('/api/quests/auto-generate', {
            child_id: childId,
            child_name: childName || undefined,
        });
        fetchDrafts(); // Refresh drafts to show the newly generated one
    } catch (error) {
        console.error("Failed to auto-generate quest:", error);
        alert(error.response?.data?.detail || "生成备课失败，请重试。");
    } finally {
        setLoading(false);
    }
  };

  const handleLocalize = async (draft) => {
    if (!childId || String(childId).trim() === '') {
      alert('请先在顶部选择儿童档案，才能进行个性化适配。');
      return;
    }
    const draftId = getDraftId(draft);
    setLocalizingId(draftId);
    
    try {
      let response;
      if (draft.milestone_uri) {
        response = await api.post('/api/quests/generate', {
          milestone_uri: draft.milestone_uri,
          child_id: childId,
          child_name: childName || undefined,
        });
      } else {
        response = await api.post('/api/quests/auto-generate', {
          child_id: childId,
          child_name: childName || undefined,
        });
      }
      
      const newDraft = normalizeQuest(response.data);
      
      // Quietly reject the old draft
      api.post(`/api/quests/drafts/${draftId}/reject`).catch(e => console.error('Failed to reject old draft:', e));
      
      // Update the current draft in place
      setDrafts(prev => prev.map(d => getDraftId(d) === draftId ? newDraft : d));
      
    } catch (error) {
      console.error("Failed to localize quest:", error);
      alert(error.response?.data?.detail || '个性化适配失败，请重试。');
    } finally {
      setLocalizingId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64 text-sky-400">
        <Sparkles className="animate-spin mr-2" size={24} />
        <span className="text-gray-500 font-medium">正在为您准备今天的专属教案...</span>
      </div>
    );
  }

  if (drafts.length === 0) {
    return (
      <div className="bg-white rounded-2xl shadow-sm p-12 text-center flex flex-col items-center justify-center border border-sky-100">
        <div className="bg-sky-50 p-5 rounded-full mb-5">
          <CheckCircle2 className="text-sky-400" size={48} />
        </div>
        <h3 className="text-2xl font-medium text-gray-800 mb-3">🎉 今天的备课已经完成啦！</h3>
        <p className="text-gray-500 text-lg mb-6">去和孩子享受美好的互动时光吧，数字助手明天会继续为您准备新的教案。</p>
        <button
            onClick={handleAutoGenerateQuest}
            className="px-6 py-3 bg-indigo-500 hover:bg-indigo-600 text-white shadow-md hover:shadow-lg rounded-xl font-medium transition-all active:scale-95 flex items-center gap-2"
        >
            <Sparkles size={20} />
            生成新的备课
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="mb-8">
        <h2 className="text-2xl font-semibold text-gray-800 flex items-center gap-2">
           <HeartHandshake className="text-orange-400" /> 
           家长参谋台
        </h2>
        <p className="text-gray-500 mt-2">
          以下是数字 BCBA 为您和孩子量身定制的居家互动游戏。您可以直接采纳，或点击文本根据孩子今天的兴趣稍作修改。
        </p>
      </div>

      <div className="space-y-6">
        {drafts.map((draft) => {
          const draftId = getDraftId(draft);
          const isEditing = editingId === draftId;

          return (
            <div key={draftId} className="bg-white rounded-2xl shadow-sm border border-sky-100 overflow-hidden transition-all hover:shadow-md">
              <div className="p-6">
                {/* Header */}
                <div className="flex justify-between items-start mb-4">
                  <div className="w-full">
                    <span className="inline-block px-3 py-1 bg-emerald-50 text-emerald-600 rounded-full text-sm font-medium mb-3">
                      {draft.domain || "综合能力"}
                    </span>
                    {isEditing ? (
                        <input 
                           type="text" 
                           value={editFormData.quest_title}
                           onChange={(e) => setEditFormData({...editFormData, quest_title: e.target.value})}
                           className="block w-full text-2xl font-bold text-gray-800 border-b-2 border-sky-200 focus:border-sky-400 focus:outline-none bg-transparent pb-1"
                           placeholder="输入游戏名称..."
                        />
                    ) : (
                        <h3 
                          className="text-2xl font-bold text-gray-800 flex items-center gap-2 group cursor-pointer hover:text-sky-600 transition-colors" 
                          onClick={() => startEdit(draft)}
                          title="点击修改游戏名称"
                        >
                          {draft.quest_title}
                          <Edit3 size={16} className="text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity" />
                        </h3>
                    )}
                  </div>
                </div>

                {/* Objective */}
                <div className="bg-orange-50 rounded-xl p-4 mb-5 border border-orange-100/50 relative group cursor-help">
                  <p className="text-orange-800 flex items-start sm:items-center">
                    <span className="font-semibold mr-2 flex items-center shrink-0">
                      🎯 训练目的：
                      {draft.hhs_source_label && (
                        <Info size={16} className="ml-1 mr-1 text-orange-400 opacity-80" />
                      )}
                    </span>
                    <span>{draft.objective}</span>
                  </p>
                  
                  {/* Tooltip */}
                  {draft.hhs_source_label && (
                    <div className="absolute bottom-full left-4 mb-2 px-3 py-2 bg-gray-800 text-white text-sm rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 shadow-lg max-w-sm">
                      📚 专业来源：协康会 - {draft.hhs_source_label}
                      <div className="absolute -bottom-1 left-6 w-2 h-2 bg-gray-800 rotate-45"></div>
                    </div>
                  )}
                </div>

                {/* Steps */}
                <div className="space-y-3">
                  <h4 className="font-medium text-gray-700">怎么玩：</h4>
                  {isEditing ? (
                      <ol className="space-y-3 pl-0">
                         {editFormData.steps.map((step, idx) => (
                             <li key={idx} className="flex gap-3 items-start">
                                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-sky-100 text-sky-600 flex items-center justify-center text-sm font-medium mt-1">
                                  {idx + 1}
                                </span>
                                <textarea
                                   value={step}
                                   onChange={(e) => handleStepChange(idx, e.target.value)}
                                   className="w-full bg-gray-50 border border-gray-200 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-sky-200 resize-none min-h-[60px] text-gray-700"
                                />
                             </li>
                         ))}
                      </ol>
                  ) : (
                      <ol className="space-y-3 pl-0">
                        {draft.steps?.map((step, idx) => (
                          <li 
                            key={idx} 
                            className="flex gap-3 items-start text-gray-600 group cursor-pointer hover:bg-gray-50 p-2 -ml-2 rounded-lg transition-colors" 
                            onClick={() => startEdit(draft)}
                            title="点击修改步骤"
                          >
                            <span className="flex-shrink-0 w-6 h-6 rounded-full bg-sky-50 text-sky-500 flex items-center justify-center text-sm font-medium mt-0.5">
                              {idx + 1}
                            </span>
                            <span className="leading-relaxed">{step}</span>
                          </li>
                        ))}
                      </ol>
                  )}
                </div>
              </div>

              {/* Action Area */}
              <div className="bg-gray-50/80 p-4 px-6 border-t border-gray-100 flex justify-end gap-3 items-center">
                {isEditing ? (
                    <>
                      <button 
                        onClick={cancelEdit}
                        className="px-4 py-2 text-gray-500 hover:bg-gray-200 rounded-xl font-medium transition-colors"
                        disabled={localizingId === draftId}
                      >
                        取消
                      </button>
                      <button 
                        onClick={() => handleSaveEdit(draftId)}
                        className="px-4 py-2 bg-gray-800 text-white hover:bg-gray-700 rounded-xl font-medium transition-colors flex items-center gap-2"
                        disabled={localizingId === draftId}
                      >
                        <Save size={18} />
                        保存修改
                      </button>
                    </>
                ) : (
                    <>
                        <button 
                          onClick={() => handleReject(draftId)}
                          className="px-4 py-2.5 text-gray-500 hover:bg-red-50 hover:text-red-500 rounded-xl font-medium transition-colors flex items-center gap-2"
                          disabled={localizingId === draftId}
                        >
                          <X size={18} />
                          换一个
                        </button>
                        <button 
                          onClick={() => handleLocalize(draft)}
                          className="px-5 py-2.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-600 rounded-xl font-medium transition-colors flex items-center gap-2 disabled:opacity-50"
                          disabled={localizingId === draftId}
                        >
                          {localizingId === draftId ? (
                            <Sparkles size={18} className="animate-spin" />
                          ) : (
                            <Sparkles size={18} />
                          )}
                          {localizingId === draftId ? '生成中...' : '✨ 个性化适配'}
                        </button>
                        <button 
                          onClick={() => handleApprove(draftId)}
                          className="px-6 py-2.5 bg-sky-500 hover:bg-sky-600 text-white shadow-sm hover:shadow-md rounded-xl font-medium transition-all flex items-center gap-2 active:scale-95 disabled:opacity-50"
                          disabled={localizingId === draftId}
                        >
                          <Check size={18} />
                          采纳并加入今天任务
                        </button>
                    </>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ParentReviewDashboard;