import React, { useState, useEffect, useCallback } from 'react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

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

function DailyDeck({ childName = '小明' }) {
  const [pending, setPending] = useState([]);
  const [completedToday, setCompletedToday] = useState([]);
  const [weakestDomainInfo, setWeakestDomainInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(null); // quest_id when submitting
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
      setPending(data.pending || []);
      setCompletedToday(data.completed_today || []);
      setWeakestDomainInfo(data.weakest_domain_info || null);
    } catch (err) {
      setError(err.message || '获取课表失败');
      setPending([]);
      setCompletedToday([]);
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
                </div>
              ))}
            </div>
          </div>
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

          {quest.teaching_steps && (
            <div className="mt-4 p-4 bg-slate-50 rounded-lg border border-slate-200">
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-emerald-100 text-emerald-800 border border-emerald-200 mb-3">教学步骤</span>
              <div className="text-slate-700 text-sm whitespace-pre-wrap leading-relaxed mt-2">
                {quest.teaching_steps}
              </div>
            </div>
          )}

          {quest.group_class_generalization && (
            <div className="p-3 rounded-lg bg-blue-50 border-l-4 border-blue-400">
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">👥 集体课泛化建议</span>
              <p className="text-blue-900 text-sm whitespace-pre-wrap mt-2">
                {quest.group_class_generalization}
              </p>
            </div>
          )}

          {quest.home_generalization && (
            <div className="p-3 rounded-lg bg-orange-50 border-l-4 border-orange-400">
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-orange-100 text-orange-800 border border-orange-200">🏠 家庭泛化建议</span>
              <p className="text-orange-900 text-sm whitespace-pre-wrap mt-2">
                {quest.home_generalization}
              </p>
            </div>
          )}

          <div className="pt-2 mb-6">
            <a
              href="#"
              className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
              onClick={(e) => e.preventDefault()}
            >
              📹 示范视频（待添加）
            </a>
          </div>
        </div>

        <div className="flex flex-wrap justify-end gap-6">
          {showButtons ? (
            PROMPT_LEVELS.map(({ key, label, emoji }) => (
              <button
                key={key}
                onClick={() => recordFeedback(quest.quest_id, key)}
                disabled={isSubmitting}
                className={`
                  btn
                  ${key === '全辅助' && 'btn-danger'}
                  ${key === '部分辅助' && 'btn-warning'}
                  ${key === '独立完成' && 'btn-success'}
                  ${isSubmitting ? 'opacity-60 cursor-not-allowed' : ''}
                `}
              >
                <span className="block text-lg mb-0.5">{emoji}</span>
                {label}
              </button>
            ))
          ) : (
            <div className="flex items-center gap-2 px-4 py-2 bg-slate-200 text-slate-600 rounded-lg font-medium">
              <span>✅</span>
              <span>已打卡</span>
            </div>
          )}
        </div>
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
        </div>
      </main>
    </div>
  );
}

export default DailyDeck;
