import React, { useState, useEffect, useCallback, useRef } from 'react';
import { VB_MAPP_SEEDS } from '../vbmapp_seeds';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const CLOUD_API_BASE = 'http://127.0.0.1:8080';

/** 大一统 Demo：PEP 评估项悬停提示，鼠标悬停显示详细描述 */
function AssessmentTooltip({ details }) {
  const [show, setShow] = useState(false);
  if (!details || details.length === 0) return null;
  return (
    <span
      style={{ position: 'relative', display: 'inline-flex', cursor: 'help' }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '20px',
          height: '20px',
          fontSize: '14px',
          fontWeight: 700,
          color: '#4338ca',
          backgroundColor: '#e0e7ff',
          borderRadius: '50%',
          border: '1px solid #818cf8'
        }}
      >
        i
      </span>
      {show && (
        <div
          style={{
            position: 'absolute',
            zIndex: 50,
            left: 0,
            top: '100%',
            marginTop: '6px',
            width: '280px',
            maxWidth: '90vw',
            padding: '12px',
            fontSize: '13px',
            textAlign: 'left',
            backgroundColor: '#1e293b',
            color: '#e2e8f0',
            borderRadius: '8px',
            boxShadow: '0 10px 25px rgba(0,0,0,0.2)',
            border: '1px solid #334155'
          }}
          role="tooltip"
        >
          <div style={{ fontWeight: 600, color: '#a5b4fc', marginBottom: '8px' }}>PEP-3 评估项描述</div>
          <ul style={{ margin: 0, paddingLeft: '18px', lineHeight: 1.6 }}>
            {details.map((item, i) => (
              <li key={i} style={{ marginBottom: '4px' }}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </span>
  );
}

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

const PROMPT_LEVELS = [
  { key: '全辅助', label: '全辅助', short: 'Full', color: 'red', emoji: '🟥' },
  { key: '部分辅助', label: '部分辅助', short: 'Partial', color: 'yellow', emoji: '🟨' },
  { key: '独立完成', label: '独立完成', short: 'Independent', color: 'green', emoji: '🟩' },
];

/** Topic Chat 沟通与记录模态框 - 家校接力 */
function QuestTopicChatModal({ quest, childName, onClose }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [sendRole, setSendRole] = useState('parent');
  const [selectedFile, setSelectedFile] = useState(null);
  const fileInputRef = useRef(null);

  const fetchLogs = useCallback(async () => {
    if (!quest?.quest_id) return;
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const headers = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch(
        `${CLOUD_API_BASE}/api/v1/children/1/logs`,
        { headers }
      );
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      
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
      
      setLogs(mappedLogs.reverse());
    } catch {
      setLogs([]);
    } finally {
      setLoading(false);
    }
  }, [quest?.quest_id, sendRole]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const handleSend = async () => {
    const content = input.trim();
    if (!content || sending) return;
    setSending(true);
    try {
      const token = localStorage.getItem('access_token');
      const headers = {
        'Content-Type': 'application/json'
      };
      if (token) headers['Authorization'] = `Bearer ${token}`;
      
      const res = await fetch(`${CLOUD_API_BASE}/api/v1/children/1/logs`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          content: content
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      setInput('');
      setSelectedFile(null);
      await fetchLogs();
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
                  <div style={{ fontSize: '14px', lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>{log.content}</div>
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

function DailyDeck({ childName = '小明' }) {
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

  // 提取真实的 VB-MAPP 节点作为底层图谱演示
  const vb19 = VB_MAPP_SEEDS.find(s => s.id === 'VB019') || { content: '将图片与实物配对（例如：真实的鞋子和鞋子的图片）。' };

  const DEMO_SUPER_NODE = {
    quest_id: "SUPER_NODE_001",
    label: "(3) 特征相同和不同（颜色、形状）",
    ecumenical_integration: {
      assessment: {
        title: "🎯 核心评估目标",
        badge: "PEP-3",
        content: "第 23 题：配对形状；第 106 题：根据特征分类",
        details: [
          "第 23 题（配对形状）：评估儿童是否能将相同形状的物体进行配对。",
          "第 106 题（根据特征分类）：评估儿童是否能根据颜色、形状等特征对物品进行分类。"
        ]
      },
      prerequisite: {
        title: "🧠 图谱前置能力",
        badge: "VB-MAPP 节点",
        content: `要求：${vb19.content}`
      },
      teaching: {
        title: "🛠️ 标准教学步骤",
        badge: "ABLLS-R 实操",
        content: `B5 - 匹配相同的物品
① 在桌上放一个苹果和一个香蕉。
② 递给儿童一个一样的苹果，指令「放一样的」。
③ 若做对，给予强烈强化；若做错，立即提供物理辅助。`
      },
      generalization: {
        title: "🏠 生活场景泛化",
        badge: "本土化经验",
        content: `收衣服时，按长短袖或颜色整理，引导儿童观察并说出：「这些衣服是一样的，都是红色的。」 或者玩超市购物游戏，找一样的零食。`
      }
    }
  };

  const fetchDailyQuests = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/daily_quests?child_name=${encodeURIComponent(childName)}&count=${questCount}`
      );
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
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
  }, [childName, questCount]);

  useEffect(() => {
    fetchDailyQuests();
  }, [fetchDailyQuests]);

  const recordFeedback = async (questId, promptLevel) => {
    if (submitting) return;
    setSubmitting(questId);
    try {
      const res = await fetch(`${API_BASE}/api/record_feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          child_name: childName,
          quest_id: questId,
          prompt_level: promptLevel,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
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
                  {quest.pep3_standard && (
                    <p className="text-sm text-slate-500 mt-1">PEP-3: {quest.pep3_standard}</p>
                  )}
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

  const QuestCard = ({ quest, isCompleted, showButtons }) => {
    const pep3Items = quest.pep3_items || [];
    const isSubmitting = submitting === quest.quest_id;
    return (
      <div
        key={quest.quest_id}
        className={`card ${isCompleted ? 'opacity-60 bg-slate-50' : ''}`}
        style={{ padding: '24px' }}
      >
        <h2 className="text-xl font-semibold text-slate-800 mb-4">
          {quest.label}
        </h2>

        <div className="space-y-3">
          {quest.pep3_standard && (
            <div>
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-indigo-100 text-indigo-800 border border-indigo-200">
                PEP-3：
              </span>
              <Pep3Tooltip pep3Standard={quest.pep3_standard} pep3Items={pep3Items} />
            </div>
          )}

          {quest.suggested_materials && (
            <p className="text-sm">
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-amber-100 text-amber-800 border border-amber-200 mb-1">推荐教具</span>
              <span className="ml-2 text-slate-700">{quest.suggested_materials}</span>
            </p>
          )}

          {quest.ecumenical_integration && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', margin: '24px 0' }}>

              {/* 1. 标准教学步骤 */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                  <span style={{ fontWeight: 700, fontSize: '16px', color: '#111827' }}>{quest.ecumenical_integration.teaching.title}</span>
                  <span style={{ fontSize: '12px', padding: '2px 8px', backgroundColor: '#f3f4f6', color: '#6b7280', borderRadius: '4px', fontFamily: 'monospace' }}>{quest.ecumenical_integration.teaching.badge}</span>
                </div>
                <div style={{ fontSize: '14px', color: '#374151', whiteSpace: 'pre-line', lineHeight: 1.6 }}>
                  {quest.ecumenical_integration.teaching.content}
                </div>
              </div>

              {/* 2. 生活场景泛化 */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                  <span style={{ fontWeight: 700, fontSize: '16px', color: '#111827' }}>{quest.ecumenical_integration.generalization.title}</span>
                  <span style={{ fontSize: '12px', padding: '2px 8px', backgroundColor: '#f3f4f6', color: '#6b7280', borderRadius: '4px', fontFamily: 'monospace' }}>{quest.ecumenical_integration.generalization.badge}</span>
                </div>
                <div style={{ fontSize: '14px', color: '#374151', whiteSpace: 'pre-line', lineHeight: 1.6 }}>
                  {quest.ecumenical_integration.generalization.content}
                </div>
              </div>

              {/* 3. 图谱前置能力 */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                  <span style={{ fontWeight: 700, fontSize: '16px', color: '#111827' }}>{quest.ecumenical_integration.prerequisite.title}</span>
                  <span style={{ fontSize: '12px', padding: '2px 8px', backgroundColor: '#f3f4f6', color: '#6b7280', borderRadius: '4px', fontFamily: 'monospace' }}>{quest.ecumenical_integration.prerequisite.badge}</span>
                </div>
                <div style={{ fontSize: '14px', color: '#374151', whiteSpace: 'pre-line', lineHeight: 1.6 }}>
                  {quest.ecumenical_integration.prerequisite.content}
                </div>
              </div>

              {/* 4. 核心评估目标 */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                  <span style={{ fontWeight: 700, fontSize: '16px', color: '#111827' }}>{quest.ecumenical_integration.assessment.title}</span>
                  <span style={{ fontSize: '12px', padding: '2px 8px', backgroundColor: '#f3f4f6', color: '#6b7280', borderRadius: '4px', fontFamily: 'monospace' }}>{quest.ecumenical_integration.assessment.badge}</span>
                  {quest.ecumenical_integration.assessment.details && quest.ecumenical_integration.assessment.details.length > 0 && (
                    <AssessmentTooltip details={quest.ecumenical_integration.assessment.details} />
                  )}
                </div>
                <div style={{ fontSize: '14px', color: '#374151', whiteSpace: 'pre-line', lineHeight: 1.6 }}>
                  {quest.ecumenical_integration.assessment.content}
                </div>
              </div>

            </div>
          )}

          {(!quest.ecumenical_integration && quest.teaching_steps) && (
            <div className="mt-4 p-4 bg-slate-50 rounded-lg border border-slate-200">
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-emerald-100 text-emerald-800 border border-emerald-200 mb-3">教学步骤</span>
              <div className="text-slate-700 text-sm whitespace-pre-wrap leading-relaxed mt-2">
                {quest.teaching_steps}
              </div>
            </div>
          )}

          {(!quest.ecumenical_integration && quest.group_class_generalization) && (
            <div className="p-3 rounded-lg bg-blue-50 border-l-4 border-blue-400">
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">👥 集体课泛化建议</span>
              <p className="text-blue-900 text-sm whitespace-pre-wrap mt-2">
                {quest.group_class_generalization}
              </p>
            </div>
          )}

          {(!quest.ecumenical_integration && quest.home_generalization) && (
            <div className="p-3 rounded-lg bg-orange-50 border-l-4 border-orange-400">
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-orange-100 text-orange-800 border border-orange-200">🏠 家庭泛化建议</span>
              <p className="text-orange-900 text-sm whitespace-pre-wrap mt-2">
                {quest.home_generalization}
              </p>
            </div>
          )}
        </div>

        {/* 1. Secondary Actions (Top right aligned below content) */}
        <div className="flex justify-end gap-3 mt-6">
          <button
            type="button"
            className="text-sm bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition font-medium flex items-center gap-1"
            onClick={(e) => e.preventDefault()}
          >
            📹 示范视频 (待添加)
          </button>
          <button
            type="button"
            onClick={() => openChat(quest)}
            className="text-sm bg-blue-50 text-blue-700 px-4 py-2 rounded-lg hover:bg-blue-100 transition font-medium flex items-center gap-1"
          >
            💬 沟通与记录 (Intervention Log)
          </button>
        </div>

        {/* 2. Divider */}
        <hr className="my-5 border-gray-200" />

        {/* 3. Primary Action: Grading Buttons (Left aligned or centered) */}
        {showButtons ? (
          <div className="flex gap-4">
            <button
              onClick={() => recordFeedback(quest.quest_id, '全辅助')}
              disabled={isSubmitting}
              className={`flex-1 bg-red-500 text-white px-4 py-3 rounded-lg hover:bg-red-600 transition font-bold shadow-sm ${isSubmitting ? 'opacity-60 cursor-not-allowed' : ''}`}
            >
              🟥 全辅助
            </button>
            <button
              onClick={() => recordFeedback(quest.quest_id, '部分辅助')}
              disabled={isSubmitting}
              className={`flex-1 bg-yellow-500 text-white px-4 py-3 rounded-lg hover:bg-yellow-600 transition font-bold shadow-sm ${isSubmitting ? 'opacity-60 cursor-not-allowed' : ''}`}
            >
              🟨 部分辅助
            </button>
            <button
              onClick={() => recordFeedback(quest.quest_id, '独立完成')}
              disabled={isSubmitting}
              className={`flex-1 bg-green-500 text-white px-4 py-3 rounded-lg hover:bg-green-600 transition font-bold shadow-sm ${isSubmitting ? 'opacity-60 cursor-not-allowed' : ''}`}
            >
              🟩 独立完成
            </button>
          </div>
        ) : (
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
        )}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-white flex flex-col">
      <header className="bg-white border-b border-slate-200 px-4 py-3 shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-lg font-semibold text-slate-800">
              今天的{childName}专属课表
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
            <button
              onClick={() => {
                setPending([DEMO_SUPER_NODE]);
                setCompletedToday([]);
              }}
              className="text-sm px-4 py-1.5 bg-indigo-600 text-white hover:bg-indigo-700 rounded-lg font-bold shadow-md transition-all ml-2"
            >
              ✨ 载入大一统 Demo
            </button>
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
                  <QuestCard
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
                  <QuestCard
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
          onClose={closeChat}
        />
      )}
    </div>
  );
}

export default DailyDeck;
