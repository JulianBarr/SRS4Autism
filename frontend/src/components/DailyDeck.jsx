import React, { useState, useEffect, useCallback, useRef } from 'react';
import api, { API_BASE, cloudApi } from '../utils/api';
import AICard from './AICard';

//       onMouseEnter={() => setShow(true)}
//       onMouseLeave={() => setShow(false)}
//     >
//       <span
//         style={{
//           display: 'inline-flex',
//           alignItems: 'center',
//           justifyContent: 'center',
//           width: '20px',
//           height: '20px',
//           fontSize: '14px',
//           fontWeight: 700,
//           color: '#4338ca',
//           backgroundColor: '#e0e7ff',
//           borderRadius: '50%',
//           border: '1px solid #818cf8'
//         }}
//       >
//         i
//       </span>
//       {show && (
//         <div
//           style={{
//             position: 'absolute',
//             zIndex: 50,
//             left: 0,
//             top: '100%',
//             marginTop: '6px',
//             width: '280px',
//             maxWidth: '90vw',
//             padding: '12px',
//             fontSize: '13px',
//             textAlign: 'left',
//             backgroundColor: '#1e293b',
//             color: '#e2e8f0',
//             borderRadius: '8px',
//             boxShadow: '0 10px 25px rgba(0,0,0,0.2)',
//             border: '1px solid #334155'
//           }}
//           role="tooltip"
//         >
//           <div style={{ fontWeight: 600, color: '#a5b4fc', marginBottom: '8px' }}>PEP-3 评估项描述</div>
//           <ul style={{ margin: 0, paddingLeft: '18px', lineHeight: 1.6 }}>
//             {details.map((item, i) => (
//               <li key={i} style={{ marginBottom: '4px' }}>{item}</li>
//             ))}
//           </ul>
//         </div>
//       )}
//     </span>
//   );
// }

/** PEP3 悬停提示：鼠标悬停显示完整描述 */
function Pep3Tooltip({ pep3Standard, pep3Items }) {
  const [show, setShow] = useState(false);
  if (!pep3Standard) return null;
  const hasDetails = pep3Items && pep3Items.length > 0;
  return (
    <span
      className="relative inline-block"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <span
        className={`
          ml-2 text-xs cursor-help border-b border-dotted
          ${hasDetails ? 'border-indigo-400 text-indigo-700 hover:border-indigo-600' : 'border-slate-400 text-slate-600'}
        `}
      >
        {pep3Standard}
      </span>
      {hasDetails && (
        <>
          <span className="ml-1 text-indigo-500 text-xs">ⓘ</span>
          {show && (
            <div
              className="absolute z-10 left-0 top-full mt-1 w-72 max-w-[90vw] p-3 text-xs text-left bg-slate-800 text-slate-100 rounded-lg shadow-lg border border-slate-600"
              role="tooltip"
            >
              <div className="font-medium text-indigo-200 mb-2">PEP-3 评估项描述</div>
              <ul className="space-y-1 list-disc list-inside">
                {pep3Items.map((item, i) => (
                  <li key={i} className="leading-relaxed">{item}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </span>
  );
}


/** Topic Chat 沟通与记录模态框 - 家校接力 */
function QuestTopicChatModal({ quest, childName, childId, onClose }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [resolvedChildId, setResolvedChildId] = useState(null);
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    let active = true;
    const resolveId = async () => {
      try {
        if (typeof childId === 'number' || (typeof childId === 'string' && childId.trim() !== '' && !isNaN(Number(childId)))) {
          if (active) setResolvedChildId(Number(childId));
          return;
        }
        const res = await cloudApi.get('/api/v1/children/me');
        if (!active) return;
        
        const safeChildName = (childName || '').trim();
        const normalize = (str) => str ? str.replace(/\s+/g, '').toLowerCase() : '';
        const match = childName ? res.data.find(c => normalize(c.name) === normalize(childName)) : null;
        
        if (match && match.id) {
          if (active) setResolvedChildId(match.id);
        } else if (res.data && res.data.length > 0) {
          if (childName) {
            console.warn('Name mismatch, fallback to first child. Wanted:', safeChildName, 'Got:', res.data[0].name);
          }
          if (active) setResolvedChildId(res.data[0].id);
        } else {
          console.warn('Could not resolve integer childId from cloudApi for:', childName);
          if (active) setLoading(false); // Unblock loading state if resolution fails
        }
      } catch (err) {
        console.error('Failed to resolve child ID:', err);
        if (active) setLoading(false); // Unblock loading on error
      }
    };
    resolveId();
    return () => { active = false; };
  }, [childName, childId]);

  const fetchLogs = useCallback(async (silent = false) => {
    if (!quest?.quest_id || !resolvedChildId) return;
    if (!silent) setLoading(true);
    try {
      const res = await cloudApi.get(`/api/v1/children/${resolvedChildId}/logs`);
      const data = res.data;
      
      const mappedLogs = data.map(log => {
        let mappedRole = log.sender_role;
        if (mappedRole === 'agent') mappedRole = 'ai';
        if (mappedRole === 'qcq_admin') mappedRole = 'admin';
        return {
          role: mappedRole || 'parent',
          content: log.content,
          timestamp: log.created_at,
          file_url: null,
          file_type: null
        };
      });
      
      const newLogs = mappedLogs.reverse();
      setLogs(prev => {
        if (prev.length === newLogs.length) {
          // Check if any message content changed (e.g. streaming update)
          const hasChanged = prev.some((log, i) => 
            log.content !== newLogs[i].content || 
            log.role !== newLogs[i].role
          );
          if (!hasChanged) return prev;
        }
        return newLogs;
      });
    } catch {
      if (!silent) setLogs([]);
    } finally {
      if (!silent) setLoading(false);
    }
  }, [quest?.quest_id, resolvedChildId]);

  useEffect(() => {
    fetchLogs();
    const intervalId = setInterval(() => {
      fetchLogs(true);
    }, 3000);
    return () => clearInterval(intervalId);
  }, [fetchLogs]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handleSend = async () => {
    const content = input.trim();
    if (!content || sending || !resolvedChildId) return;
    setSending(true);
    try {
      const res = await cloudApi.post(`/api/v1/children/${resolvedChildId}/logs`, { content });
      setInput('');
      setSelectedFile(null);
      await fetchLogs(true);
    } catch (err) {
      console.error('发送失败:', err);
    } finally {
      setSending(false);
    }
  };

  const roleLabel = { parent: '家长', teacher: '老师', ai: 'AI' };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0, left: 0, width: '100vw', height: '100vh',
        backgroundColor: 'rgba(0, 0, 0, 0.6)',
        zIndex: 99999,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        padding: '20px',
        boxSizing: 'border-box'
      }}
      onClick={onClose}
      role="dialog"
    >
      {/* 弹窗本体：宽90%（最大800px），高85vh */}
      <div
        style={{
          backgroundColor: '#ffffff',
          borderRadius: '16px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          width: '90%',
          maxWidth: '800px',
          height: '85vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header：左右两端对齐，X在右上角 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 24px', borderBottom: '1px solid #f1f5f9', backgroundColor: '#f8fafc', flexShrink: 0 }}>
          <h3 style={{ fontWeight: 600, fontSize: '1.125rem', color: '#1e293b', margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            💬 沟通与记录 — {quest?.label || ''}
          </h3>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', fontSize: '1.5rem', cursor: 'pointer', color: '#64748b', padding: '4px 8px', borderRadius: '8px' }}
          >
            ✕
          </button>
        </div>

        {/* Chat Body：保留原有的渲染逻辑 */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px', backgroundColor: '#f8fafc', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {loading ? (
            <div style={{ color: '#64748b', fontSize: '14px', textAlign: 'center', padding: '32px 0' }}>加载中...</div>
          ) : logs.length === 0 ? (
            <div style={{ color: '#94a3b8', fontSize: '14px', textAlign: 'center', padding: '32px 0' }}>暂无记录，可在此添加沟通内容</div>
          ) : (
            logs.map((log, i) => {
              if (log.role === 'system') {
                return (
                  <div key={i} style={{ alignSelf: 'center', backgroundColor: '#f1f5f9', color: '#64748b', padding: '6px 16px', borderRadius: '999px', fontSize: '12px', marginTop: '8px' }}>
                    {log.content}
                  </div>
                );
              }
              const isParent = log.role === 'parent';
              
              let textContent = log.content;
              let parsedData = null;
              if (log.role === 'ai' && log.content.includes('```json')) {
                try {
                  const parts = log.content.split('```json');
                  textContent = parts[0].trim();
                  const jsonStr = parts[1].split('```')[0].trim();
                  parsedData = JSON.parse(jsonStr);
                } catch (e) {
                  // Fallback to original content on parse error
                  textContent = log.content;
                  parsedData = null;
                }
              }

              return (
                <div key={i} style={{
                  alignSelf: isParent ? 'flex-end' : 'flex-start',
                  backgroundColor: isParent ? '#dcfce7' : (log.role === 'ai' ? '#ede9fe' : '#dbeafe'),
                  color: isParent ? '#064e3b' : (log.role === 'ai' ? '#4c1d95' : '#1e3a8a'),
                  padding: '12px 16px',
                  borderRadius: '16px',
                  borderBottomRightRadius: isParent ? '4px' : '16px',
                  borderBottomLeftRadius: !isParent ? '4px' : '16px',
                  maxWidth: '80%',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
                }}>
                  <span style={{ fontSize: '12px', opacity: 0.6, display: 'block', marginBottom: '6px' }}>
                    {roleLabel[log.role] || log.role}
                  </span>
                  <div style={{ fontSize: '14px', lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>{textContent}</div>
                  {parsedData && <AICard data={parsedData} />}
                  {log.file_url && (
                    <>
                      {log.file_type && log.file_type.startsWith('image/') && (
                        <img
                          src={API_BASE + log.file_url}
                          alt=""
                          style={{ maxWidth: '100%', borderRadius: '8px', marginTop: '8px', display: 'block' }}
                        />
                      )}
                      {log.file_type && log.file_type.startsWith('video/') && (
                        <video
                          controls
                          src={API_BASE + log.file_url}
                          style={{ maxWidth: '100%', borderRadius: '8px', marginTop: '8px', display: 'block' }}
                        />
                      )}
                    </>
                  )}
                  <span style={{ fontSize: '11px', opacity: 0.5, display: 'block', marginTop: '8px', textAlign: 'right' }}>
                    {log.timestamp?.slice(0, 16).replace('T', ' ')}
                  </span>
                </div>
              );
            })
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area：多行文本框 */}
        <div style={{ padding: '16px 24px', borderTop: '1px solid #e2e8f0', backgroundColor: '#ffffff', display: 'flex', flexDirection: 'column', gap: '12px', flexShrink: 0 }}>
          <input
            type="file"
            ref={fileInputRef}
            accept="image/*,video/*"
            style={{ display: 'none' }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) setSelectedFile(f);
              e.target.value = '';
            }}
          />
          {selectedFile && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', backgroundColor: '#f1f5f9', borderRadius: '8px', fontSize: '13px', color: '#475569' }}>
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{selectedFile.name}</span>
              <button
                type="button"
                onClick={() => setSelectedFile(null)}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '14px', color: '#64748b', padding: '2px 6px' }}
              >
                ✕
              </button>
            </div>
          )}
          <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>

          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#e2e8f0'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
            style={{ background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '18px', padding: '8px', borderRadius: '6px' }}
            title="上传图片或视频"
          >
            📎
          </button>

          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="输入沟通内容... (按 Cmd/Ctrl + Enter 快捷发送)"
            rows={3}
            style={{ flex: 1, padding: '12px', borderRadius: '8px', border: '1px solid #cbd5e1', outline: 'none', resize: 'none', fontFamily: 'inherit', fontSize: '14px', lineHeight: '1.5' }}
          />

          <button
            onClick={handleSend}
            disabled={sending || !input.trim()}
            style={{ padding: '10px 24px', backgroundColor: '#334155', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 500, alignSelf: 'stretch', opacity: (sending || !input.trim()) ? 0.5 : 1 }}
          >
            发送
          </button>
          </div>
        </div>
      </div>
    </div>
  );
}


const ExpandableQuestCard = ({ quest, isCompleted, showButtons, submitting, onRecordFeedback, onOpenChat }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const isSubmitting = submitting === quest.quest_id;
  const pep3Items = quest.pep3_items || [];
  
  const title = quest.label || quest.title || "(未命名任务)";
  const isHhs = (quest.source || '').toLowerCase() === 'hhs' || quest.content_source === 'HHS';
  const hhsModuleText = (quest.hhs_module || '').trim() || '未分配模块';
  
  const badges = [];
  if (quest.badges) {
    badges.push(...quest.badges);
  } else if (isHhs) {
    const ageText = quest.age_group || '通用';
    badges.push(`协康会 HHS | 模块: ${hhsModuleText} | 适用年龄: ${ageText}`);
  } else if (quest.pep3_standard) {
    badges.push(`PEP-3: ${quest.pep3_standard}`);
  }
  
  let conditions = quest.conditions || quest.ecumenical_integration?.assessment?.content || "";
  let prerequisite = quest.prerequisite || quest.ecumenical_integration?.prerequisite?.content || "";
  const normalizeList = (value) => {
    if (Array.isArray(value)) return value.filter(Boolean).map((item) => String(item).trim()).filter(Boolean);
    if (typeof value === 'string') {
      const txt = value.trim();
      return txt ? [txt] : [];
    }
    return [];
  };

  const materialItems = normalizeList(quest.suggested_materials).length
    ? normalizeList(quest.suggested_materials)
    : normalizeList(quest.materials || quest.ecumenical_integration?.teaching?.materials);
  const activityItems = normalizeList(quest.activities);
  const precautionItems = normalizeList(quest.precautions);
  const fallbackStepText = quest.teaching_steps || quest.steps || quest.ecumenical_integration?.teaching?.steps || quest.ecumenical_integration?.teaching?.content || "";
  const renderedSteps = [...activityItems, ...precautionItems].length > 0
    ? [...activityItems.map((a) => `活动: ${a}`), ...precautionItems.map((p) => `注意: ${p}`)].join('\n')
    : fallbackStepText;
  let generalization = quest.home_generalization || quest.generalization || quest.ecumenical_integration?.generalization?.content || "";

  return (
    <div className={`border border-slate-200 rounded-xl bg-white overflow-hidden shadow-sm ${isCompleted ? 'opacity-60 bg-slate-50' : ''}`}>
      {/* Header */}
      <div 
        className="cursor-pointer p-4 hover:bg-slate-50 transition-colors flex justify-between items-start"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex-1">
          <h2 className="text-lg font-bold text-slate-800">
            {title}
          </h2>
          <div className="flex flex-wrap gap-2 mt-2">
            {badges.map((badge, idx) => (
              <span key={idx} className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-100">
                {badge}
              </span>
            ))}
            {!isHhs && quest.pep3_standard && !quest.badges && (
               <Pep3Tooltip pep3Standard={quest.pep3_standard} pep3Items={pep3Items} />
            )}
          </div>
        </div>
        <div className="flex items-center justify-center w-8 h-8 rounded-full bg-slate-100 text-slate-500 ml-4">
          <svg 
            className={`w-5 h-5 shrink-0 text-slate-400 transition-transform duration-300 ${isExpanded ? 'rotate-180' : ''}`} 
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
            width="20" height="20" style={{ minWidth: '20px', minHeight: '20px' }}
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* Body */}
      {isExpanded && (
        <div className="p-4 border-t border-slate-100 space-y-4 bg-slate-50/50">
          
          {/* 区块 A - 🎯 核心目标 */}
          {conditions && (
            <div className="bg-blue-50 text-blue-800 p-3 rounded-lg">
              <h3 className="font-bold mb-1 flex items-center gap-2">
                <span>🎯</span> 核心目标
              </h3>
              <div className="whitespace-pre-wrap leading-relaxed text-sm">
                {conditions}
              </div>
            </div>
          )}

          {/* 区块 B - 🧠 前置能力 */}
          {prerequisite && (
            <div className="bg-purple-50 text-purple-800 p-3 rounded-lg text-sm">
              <h3 className="font-bold mb-1 flex items-center gap-2">
                <span>🧠</span> 前置能力 (VB-MAPP)
              </h3>
              <div className="whitespace-pre-wrap leading-relaxed">
                {prerequisite}
              </div>
            </div>
          )}

          {/* 区块 C - 🛠️ 教具与步骤 */}
          {(materialItems.length > 0 || renderedSteps) && (
            <div className="bg-white border border-slate-100 p-3 rounded-lg">
              <h3 className="font-bold text-slate-700 mb-2 flex items-center gap-2">
                <span>🛠️</span> 教具与步骤
              </h3>
              {materialItems.length > 0 && (
                <div className="mb-2 text-sm text-slate-700">
                  <span className="font-semibold text-slate-800">教具准备：</span>
                  <ul className="mt-1 list-disc list-inside">
                    {materialItems.map((item, idx) => (
                      <li key={idx}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
              {renderedSteps && (
                <div className="text-sm text-slate-600 whitespace-pre-wrap leading-relaxed">
                  {renderedSteps}
                </div>
              )}
            </div>
          )}

          {/* 区块 D - 🏡 家庭泛化 */}
          {generalization && (
            <div className="bg-amber-50 text-amber-900 p-3 rounded-lg border-l-4 border-amber-400">
              <h3 className="font-bold mb-1 flex items-center gap-2">
                <span>🏡</span> 家庭泛化
              </h3>
              <div className="text-sm whitespace-pre-wrap leading-relaxed">
                {generalization}
              </div>
            </div>
          )}

          {/* Action Area */}
          <div className="pt-2">
            <div className="flex justify-end gap-3 mb-4">
              <button
                type="button"
                className="text-sm bg-white text-slate-700 border border-slate-300 px-4 py-2 rounded-lg hover:bg-slate-50 transition font-medium flex items-center gap-2"
                onClick={(e) => { e.stopPropagation(); }}
              >
                <span>📹</span> 示范视频 (待添加)
              </button>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); onOpenChat(quest); }}
                className="text-sm bg-indigo-50 text-indigo-700 border border-indigo-100 px-4 py-2 rounded-lg hover:bg-indigo-100 transition font-medium flex items-center gap-2"
              >
                <span>💬</span> 沟通与记录
              </button>
            </div>

            {showButtons ? (
              <div className="flex gap-4">
                <button
                  onClick={(e) => { e.stopPropagation(); onRecordFeedback(quest.quest_id, '全辅助'); }}
                  disabled={isSubmitting}
                  className={`flex-1 bg-red-50 text-red-600 border border-red-200 px-4 py-3 rounded-xl hover:bg-red-500 hover:text-white transition-all font-bold shadow-sm ${isSubmitting ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  🟥 全辅助
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onRecordFeedback(quest.quest_id, '部分辅助'); }}
                  disabled={isSubmitting}
                  className={`flex-1 bg-amber-50 text-amber-600 border border-amber-200 px-4 py-3 rounded-xl hover:bg-amber-500 hover:text-white transition-all font-bold shadow-sm ${isSubmitting ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  🟨 部分辅助
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onRecordFeedback(quest.quest_id, '独立完成'); }}
                  disabled={isSubmitting}
                  className={`flex-1 bg-emerald-50 text-emerald-600 border border-emerald-200 px-4 py-3 rounded-xl hover:bg-emerald-500 hover:text-white transition-all font-bold shadow-sm ${isSubmitting ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  🟩 独立完成
                </button>
              </div>
            ) : (
              <div className="flex justify-between items-center bg-white border border-slate-200 p-4 rounded-xl shadow-sm">
                <div className="flex items-center gap-2 text-emerald-600 font-bold">
                  <span className="text-xl">✅</span>
                  今日已完成
                </div>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onOpenChat(quest); }}
                  className="text-sm bg-slate-50 border border-slate-200 text-slate-700 px-4 py-2 rounded-lg hover:bg-slate-100 transition font-medium"
                >
                  💬 补充记录
                </button>
              </div>
            )}
          </div>

        </div>
      )}
    </div>
  );
};

function DailyDeck({
  childName = null,
  childId,
  scheduleSource = 'qcq',
  showDemoButton = true,
}) {
  const [pending, setPending] = useState([]);
  const [completedToday, setCompletedToday] = useState([]);
  const [historyQuests, setHistoryQuests] = useState([]);
  const [weakestDomainInfo, setWeakestDomainInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(null); // quest_id when submitting
  const [questCount, setQuestCount] = useState(3);
  const [currentChatQuest, setCurrentChatQuest] = useState(null);

  // Prevent background scroll when modal is open; always restore on unmount
  useEffect(() => {
    if (currentChatQuest) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [currentChatQuest]);

  const openChat = (quest) => setCurrentChatQuest(quest);
  const closeChat = () => setCurrentChatQuest(null);

  const DEMO_MOCK_DATA = {
    quest_id: "demo_1057",
    label: "(3) 特征相同和不同（颜色、形状）",
    badges: ["PEP-3 认知", "VB-MAPP"],
    ecumenical_integration: {
      assessment: { content: "颜色相同、形状不同的物件配对" },
      prerequisite: { content: "【VB-MAPP】视觉表现与配对 6-M：配对20个相同的物品或图片" },
      teaching: {
        materials: "积木片、珠子、雪花片（颜色相同、形状不同的一组）",
        steps: "1. 导师拿出颜色相同、形状不同的一组物件...\n2. 引导儿童说出“XX是相同的”..."
      },
      generalization: { content: "收拾衣服，按长短袖整理，引导儿童观察并说出：“这些衣服是一样的，都是短袖。”" }
    }
  };

  const fetchDailyQuests = useCallback(async () => {
    if (!childName) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await api.get('/api/daily_quests', {
        params: {
          child_name: childName,
          count: questCount,
          source: scheduleSource,
        },
      });
      const data = res.data;
      setPending(data.pending || []);
      setCompletedToday(data.completed_today || []);
      setHistoryQuests(data.history_quests || []);
      setWeakestDomainInfo(data.weakest_domain_info || null);
    } catch (err) {
      setError(err.message || '获取课表失败');
      setPending([]);
      setCompletedToday([]);
      setHistoryQuests([]);
    } finally {
      setLoading(false);
    }
  }, [childName, questCount, scheduleSource]);

  useEffect(() => {
    fetchDailyQuests();
  }, [fetchDailyQuests]);

  const recordFeedback = async (questId, promptLevel) => {
    if (submitting) return;
    setSubmitting(questId);
    try {
      const res = await api.post(`/api/record_feedback`, {
          child_name: childName,
          quest_id: questId,
          prompt_level: promptLevel,
      });
      const data = res.data;
      if (data.status !== 'success') throw new Error('记录失败');

      // 打卡成功后重新拉取数据，将任务从 pending 移到 completed_today
      await fetchDailyQuests();
    } catch (err) {
      setError(err.message || '记录反馈失败');
    } finally {
      setSubmitting(null);
    }
  };

  const totalCount = questCount;
  const completedCount = completedToday.length;
  const allDone = totalCount > 0 && completedCount >= totalCount;

  if (!childName) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-slate-600 text-lg">请先选择儿童档案</div>
      </div>
    );
  }

  const deckHeadline =
    scheduleSource === 'hhs'
      ? `今天的${childName} HHS 靶向课表`
      : scheduleSource === 'mixed'
        ? `今天的${childName} 靶向课表（QCQ+HHS）`
        : `今天的${childName} QCQ 靶向课表`;

  if (loading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-slate-600 text-lg">加载今日课表...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-lg p-6 max-w-md text-center">
          <p className="text-red-600 mb-4">{error}</p>
          <button
            onClick={fetchDailyQuests}
            className="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600"
          >
            重试
          </button>
        </div>
      </div>
    );
  }

  if (allDone && pending.length === 0) {
    return (
      <div className="min-h-screen bg-white flex flex-col">
        <div className="flex flex-col items-center justify-center p-6 shrink-0">
          <div className="text-6xl mb-4">🎉</div>
          <h2 className="text-2xl font-bold text-slate-800 mb-2">
            今天的靶向干预已全部完成！
          </h2>
          <p className="text-slate-600 mb-6">继续保持，明天见～</p>
          <button
            onClick={fetchDailyQuests}
            className="px-6 py-3 bg-amber-500 text-white rounded-xl hover:bg-amber-600 font-medium"
          >
            刷新课表
          </button>
        </div>
        {completedToday.length > 0 && (
          <div className="max-w-2xl mx-auto w-full px-4 pb-8">
            <h2 className="text-base font-semibold text-slate-600 mb-4">✅ 今日已打卡</h2>
            <div className="space-y-4">
              {completedToday.map((quest) => (
                <div
                  key={quest.quest_id}
                  className="card opacity-60 bg-slate-50 p-4 rounded-lg"
                >
                  <h3 className="font-semibold text-slate-700">{quest.label}</h3>
                  {((quest.source || '').toLowerCase() === 'hhs' || quest.content_source === 'HHS') ? (
                    <p className="text-sm text-slate-500 mt-1">
                      协康会 HHS | 模块: {(quest.hhs_module || '').trim() || '未分配模块'} | 适用年龄: {quest.age_group || '通用'}
                    </p>
                  ) : quest.pep3_standard ? (
                    <p className="text-sm text-slate-500 mt-1">PEP-3: {quest.pep3_standard}</p>
                  ) : null}
                  <hr className="my-4 border-gray-100" />
                  <div className="flex justify-between items-center bg-gray-50 p-3 rounded-lg">
                    <div className="flex items-center gap-2 text-emerald-700 font-bold">
                      <span>✅</span>
                      今日已打卡
                    </div>
                    <button
                      type="button"
                      onClick={() => openChat(quest)}
                      className="text-sm bg-white border border-gray-200 text-gray-700 px-3 py-1.5 rounded-md hover:bg-gray-50 transition font-medium"
                    >
                      💬 补充记录
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        {historyQuests.length > 0 && (
          <div className="max-w-2xl mx-auto w-full px-4 pb-8">
            <h2 className="text-base font-semibold text-slate-600 mb-4">🕰️ 历史干预记录 (History)</h2>
            <div className="space-y-2">
              {historyQuests.map((item) => (
                <div
                  key={item.quest?.quest_id || item.last_review}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    backgroundColor: '#f8fafc',
                    borderRadius: '8px',
                    border: '1px solid #e2e8f0'
                  }}
                >
                  <div>
                    <span style={{ fontWeight: 500, color: '#334155' }}>{item.quest?.label || item.quest?.quest_id}</span>
                    <span style={{ fontSize: '12px', color: '#64748b', marginLeft: '8px' }}>{item.last_review}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => openChat(item.quest)}
                    style={{
                      fontSize: '12px',
                      padding: '4px 10px',
                      backgroundColor: '#e0e7ff',
                      color: '#4338ca',
                      border: 'none',
                      borderRadius: '6px',
                      cursor: 'pointer'
                    }}
                  >
                    💬 查看记录
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
        {currentChatQuest && (
          <QuestTopicChatModal
            quest={currentChatQuest}
            childName={childName}
            childId={childId}
            onClose={closeChat}
          />
        )}
      </div>
    );
  }

  if (pending.length === 0 && completedToday.length === 0) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-slate-600 text-lg">今日暂无任务</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white flex flex-col">
      <header className="bg-white border-b border-slate-200 px-4 py-3 shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-lg font-semibold text-slate-800">
              {deckHeadline}
            </h1>
            {weakestDomainInfo && (
              <p className="text-sm text-amber-700 mt-1">
                🚨 靶向短板：{weakestDomainInfo.domain_name}
              </p>
            )}
            <p className="text-sm text-slate-500 mt-1">
              进度: {completedCount} / {totalCount} 已完成
            </p>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-slate-600">任务数量：</label>
            <select
              value={questCount}
              onChange={(e) => setQuestCount(Number(e.target.value))}
              className="text-sm border border-slate-300 rounded-lg px-2 py-1"
            >
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                <option key={n} value={n}>{n} 个</option>
              ))}
            </select>
            <button
              onClick={fetchDailyQuests}
              className="text-sm px-3 py-1 bg-slate-200 hover:bg-slate-300 rounded-lg"
            >
              刷新
            </button>
            {showDemoButton && scheduleSource === 'qcq' ? (
              <button
                type="button"
                onClick={() => {
                  setPending([DEMO_MOCK_DATA]);
                  setCompletedToday([]);
                }}
                className="text-sm px-4 py-1.5 bg-indigo-600 text-white hover:bg-indigo-700 rounded-lg font-bold shadow-md transition-all ml-2"
              >
                ✨ 载入大一统 Demo
              </button>
            ) : null}
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-auto p-4 bg-white">
        <div className="max-w-2xl mx-auto space-y-8">
          {/* 今日待完成 */}
          {pending.length > 0 && (
            <section>
              <h2 className="text-base font-semibold text-slate-700 mb-4 flex items-center gap-2">
                📌 今日待完成 (Pending)
              </h2>
              <div className="space-y-4">
                {pending.map((quest) => (
                  <ExpandableQuestCard
                    submitting={submitting}
                    onRecordFeedback={recordFeedback}
                    onOpenChat={openChat}
                    key={quest.quest_id}
                    quest={quest}
                    isCompleted={false}
                    showButtons={true}
                  />
                ))}
              </div>
            </section>
          )}

          {/* 今日已打卡 */}
          {completedToday.length > 0 && (
            <section>
              <h2 className="text-base font-semibold text-slate-600 mb-4 flex items-center gap-2">
                ✅ 今日已打卡 (Completed)
              </h2>
              <div className="space-y-4">
                {completedToday.map((quest) => (
                  <ExpandableQuestCard
                    submitting={submitting}
                    onRecordFeedback={recordFeedback}
                    onOpenChat={openChat}
                    key={quest.quest_id}
                    quest={quest}
                    isCompleted={true}
                    showButtons={false}
                  />
                ))}
              </div>
            </section>
          )}

          {/* 历史干预记录 */}
          {historyQuests.length > 0 && (
            <section>
              <h2 className="text-base font-semibold text-slate-600 mb-4 flex items-center gap-2">
                🕰️ 历史干预记录 (History)
              </h2>
              <div className="space-y-2">
                {historyQuests.map((item) => (
                  <div
                    key={item.quest?.quest_id || item.last_review}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '8px 12px',
                      backgroundColor: '#f8fafc',
                      borderRadius: '8px',
                      border: '1px solid #e2e8f0'
                    }}
                  >
                    <div>
                      <span style={{ fontWeight: 500, color: '#334155' }}>{item.quest?.label || item.quest?.quest_id}</span>
                      <span style={{ fontSize: '12px', color: '#64748b', marginLeft: '8px' }}>{item.last_review}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => openChat(item.quest)}
                      style={{
                        fontSize: '12px',
                        padding: '4px 10px',
                        backgroundColor: '#e0e7ff',
                        color: '#4338ca',
                        border: 'none',
                        borderRadius: '6px',
                        cursor: 'pointer'
                      }}
                    >
                      💬 查看记录
                    </button>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      </main>

      {currentChatQuest && (
        <QuestTopicChatModal
          quest={currentChatQuest}
          childName={childName}
          childId={childId}
          onClose={closeChat}
        />
      )}
    </div>
  );
}

export default DailyDeck;
