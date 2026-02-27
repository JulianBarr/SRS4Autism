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
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [slideOut, setSlideOut] = useState(null); // 'left' | 'right' | null
  const [questCount, setQuestCount] = useState(3); // Default 3, user can change

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
      setCurrentIndex(0);
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
    setSubmitting(true);
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

      // 滑出动画：根据按钮位置决定方向（左/右）
      const levelIndex = PROMPT_LEVELS.findIndex((p) => p.key === promptLevel);
      const direction = levelIndex === 0 ? 'left' : levelIndex === 2 ? 'right' : 'right';
      setSlideOut(direction);

      setTimeout(() => {
        setSlideOut(null);
        setCurrentIndex((i) => i + 1);
        setSubmitting(false);
      }, 300);
    } catch (err) {
      setError(err.message || '记录反馈失败');
      setSubmitting(false);
    }
  };

  const currentQuest = quests[currentIndex];
  const allDone = quests.length > 0 && currentIndex >= quests.length;

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

  if (!currentQuest) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center">
        <div className="text-slate-600 text-lg">今日暂无任务</div>
      </div>
    );
  }

  const slideClass =
    slideOut === 'left'
      ? 'animate-slide-out-left'
      : slideOut === 'right'
      ? 'animate-slide-out-right'
      : '';

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

      {/* 任务卡片区 */}
      <main className="flex-1 flex flex-col items-center justify-center p-4 overflow-hidden">
        {/* 进度指示器 - 明显提示用户总任务数 */}
        <div className="mb-4 px-4 py-2 bg-slate-200 rounded-lg text-slate-700 font-semibold text-lg">
          进度: {currentIndex + 1} / {quests.length}
        </div>
        <div
          className={`w-full max-w-md bg-white rounded-2xl shadow-xl p-6 transition-transform duration-300 ${slideClass}`}
        >
          <h2 className="text-xl font-semibold text-slate-800 mb-4">
            {currentQuest.label}
          </h2>
          <div className="space-y-2 text-slate-600 text-sm">
            <p>
              <span className="font-medium text-slate-500">PEP-3 标准：</span>
              {currentQuest.pep3_standard}
            </p>
            <p>
              <span className="font-medium text-slate-500">推荐教具：</span>
              {currentQuest.suggested_materials}
            </p>
          </div>
        </div>
      </main>

      {/* 底部操作区 - Anki 风格 */}
      <footer className="bg-white border-t border-slate-200 px-4 py-4 shrink-0">
        <div className="flex justify-center gap-4 max-w-md mx-auto">
          {PROMPT_LEVELS.map(({ key, label, emoji }) => (
            <button
              key={key}
              onClick={() => recordFeedback(currentQuest.quest_id, key)}
              disabled={submitting}
              className={`
                flex-1 py-3 px-4 rounded-xl font-medium text-sm
                transition-all duration-200
                ${submitting ? 'opacity-60 cursor-not-allowed' : 'hover:scale-105 active:scale-95'}
                ${key === '全辅助' && 'bg-red-100 text-red-800 hover:bg-red-200'}
                ${key === '部分辅助' && 'bg-amber-100 text-amber-800 hover:bg-amber-200'}
                ${key === '独立完成' && 'bg-green-100 text-green-800 hover:bg-green-200'}
              `}
            >
              <span className="block text-lg mb-0.5">{emoji}</span>
              {label}
            </button>
          ))}
        </div>
      </footer>

      {/* 滑出动画 */}
      <style>{`
        @keyframes slideOutLeft {
          to {
            transform: translateX(-120%);
            opacity: 0;
          }
        }
        @keyframes slideOutRight {
          to {
            transform: translateX(120%);
            opacity: 0;
          }
        }
        .animate-slide-out-left {
          animation: slideOutLeft 0.3s ease-out forwards;
        }
        .animate-slide-out-right {
          animation: slideOutRight 0.3s ease-out forwards;
        }
      `}</style>
    </div>
  );
}

export default DailyDeck;
