import React, { useState, useEffect, useCallback } from 'react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const PROMPT_LEVELS = [
  { key: '全辅助', label: '全辅助', short: 'Full', color: 'red', emoji: '🟥' },
  { key: '部分辅助', label: '部分辅助', short: 'Partial', color: 'yellow', emoji: '🟨' },
  { key: '独立完成', label: '独立完成', short: 'Independent', color: 'green', emoji: '🟩' },
];

function DailyDeck({ childName = '小明' }) {
  const [quests, setQuests] = useState([]);
  const [weakestDomainInfo, setWeakestDomainInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(null); // quest_id when submitting
  const [completedTasks, setCompletedTasks] = useState({}); // { [quest_id]: true }
  const [questCount, setQuestCount] = useState(3);

  const fetchDailyQuests = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/daily_quests?child_name=${encodeURIComponent(childName)}&count=${questCount}`
      );
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setQuests(data.quests || []);
      setWeakestDomainInfo(data.weakest_domain_info || null);
      setCompletedTasks({});
    } catch (err) {
      setError(err.message || '获取课表失败');
      setQuests([]);
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

      setCompletedTasks((prev) => ({ ...prev, [questId]: true }));
    } catch (err) {
      setError(err.message || '记录反馈失败');
    } finally {
      setSubmitting(null);
    }
  };

  const completedCount = Object.keys(completedTasks).filter(Boolean).length;
  const allDone = quests.length > 0 && completedCount >= quests.length;

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center">
        <div className="text-slate-600 text-lg">加载今日课表...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center p-4">
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

  if (allDone) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-amber-50 to-orange-100 flex flex-col items-center justify-center p-6">
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
    );
  }

  if (quests.length === 0) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center">
        <div className="text-slate-600 text-lg">今日暂无任务</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col">
      {/* 顶部状态栏 */}
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
              进度: {completedCount} / {quests.length} 已完成
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
          </div>
        </div>
      </header>

      {/* 垂直任务列表 */}
      <main className="flex-1 overflow-auto p-4">
        <div className="max-w-2xl mx-auto space-y-4">
          {quests.map((quest) => {
            const isCompleted = completedTasks[quest.quest_id];
            const isSubmitting = submitting === quest.quest_id;

            return (
              <div
                key={quest.quest_id}
                className={`
                  w-full bg-white rounded-2xl shadow-lg p-6 transition-all duration-200
                  ${isCompleted
                    ? 'opacity-75 bg-slate-50 border-2 border-green-200'
                    : 'hover:shadow-xl'
                  }
                `}
              >
                <h2 className="text-xl font-semibold text-slate-800 mb-4">
                  {quest.label}
                </h2>

                <div className="space-y-3">
                  {/* PEP-3 标准：弱化显示 */}
                  {quest.pep3_standard && (
                    <p className="text-xs text-slate-400">
                      PEP-3: {quest.pep3_standard}
                    </p>
                  )}

                  {/* 推荐教具：弱化 */}
                  {quest.suggested_materials && (
                    <p className="text-sm text-slate-500">
                      <span className="font-medium text-slate-400">推荐教具：</span>
                      {quest.suggested_materials}
                    </p>
                  )}

                  {/* 教学步骤：核心内容，突出显示 */}
                  {quest.teaching_steps && (
                    <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-slate-100">
                      <p className="font-medium text-slate-600 mb-2">教学步骤</p>
                      <div className="text-slate-700 text-sm whitespace-pre-wrap leading-relaxed">
                        {quest.teaching_steps}
                      </div>
                    </div>
                  )}

                  {/* 集体课泛化 */}
                  {quest.group_class_generalization && (
                    <div className="p-3 rounded-lg bg-blue-50 border-l-4 border-blue-400">
                      <p className="font-medium text-blue-800 text-xs mb-1">👥 集体课泛化建议</p>
                      <p className="text-blue-900 text-sm whitespace-pre-wrap">
                        {quest.group_class_generalization}
                      </p>
                    </div>
                  )}

                  {/* 家庭泛化：Callout 样式 */}
                  {quest.home_generalization && (
                    <div className="p-3 rounded-lg bg-orange-50 border-l-4 border-orange-400">
                      <p className="font-medium text-orange-800 text-xs mb-1">🏠 家庭泛化建议</p>
                      <p className="text-orange-900 text-sm whitespace-pre-wrap">
                        {quest.home_generalization}
                      </p>
                    </div>
                  )}
                </div>

                {/* 操作区：评价按钮 */}
                <div className="mt-6 flex flex-wrap justify-end gap-3">
                  {isCompleted ? (
                    <div className="flex items-center gap-2 px-4 py-2 bg-green-100 text-green-800 rounded-xl font-medium">
                      <span>✅</span>
                      <span>已打卡</span>
                    </div>
                  ) : (
                    PROMPT_LEVELS.map(({ key, label, emoji }) => (
                      <button
                        key={key}
                        onClick={() => recordFeedback(quest.quest_id, key)}
                        disabled={isSubmitting}
                        className={`
                          py-3 px-4 rounded-xl font-medium text-sm
                          transition-all duration-200 shadow-sm
                          hover:scale-105 active:scale-95
                          ${isSubmitting ? 'opacity-60 cursor-not-allowed' : ''}
                          ${key === '全辅助' && 'bg-red-100 text-red-800 hover:bg-red-200 hover:shadow'}
                          ${key === '部分辅助' && 'bg-amber-100 text-amber-800 hover:bg-amber-200 hover:shadow'}
                          ${key === '独立完成' && 'bg-green-100 text-green-800 hover:bg-green-200 hover:shadow'}
                        `}
                      >
                        <span className="block text-lg mb-0.5">{emoji}</span>
                        {label}
                      </button>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </main>
    </div>
  );
}

export default DailyDeck;
