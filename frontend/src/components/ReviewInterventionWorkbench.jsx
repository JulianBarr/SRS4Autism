import React, { useState } from 'react';
import DailyDeck from './DailyDeck';
import ParentReviewDashboard from './ParentReviewDashboard';

/**
 * 家长/教师共用：「今日备课」与「开始干预」分段切换。
 * dailyDeckProps 会原样传入 DailyDeck（如 scheduleSource、showDemoButton 等）。
 */
function ReviewInterventionWorkbench({ dailyDeckProps = {} }) {
  const [activeTab, setActiveTab] = useState('review');

  return (
    <div className="w-full max-w-4xl mx-auto mt-6">
      <div className="flex justify-center mb-8">
        <div className="bg-gray-100/80 p-1.5 rounded-xl flex space-x-1 shadow-inner">
          <button
            type="button"
            onClick={() => setActiveTab('review')}
            className={`px-8 py-2.5 rounded-lg text-sm font-semibold transition-all duration-300 ${
              activeTab === 'review'
                ? 'bg-white text-blue-600 shadow-sm ring-1 ring-black/5'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200/50'
            }`}
          >
            💡 今日备课
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('deck')}
            className={`px-8 py-2.5 rounded-lg text-sm font-semibold transition-all duration-300 ${
              activeTab === 'deck'
                ? 'bg-white text-blue-600 shadow-sm ring-1 ring-black/5'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200/50'
            }`}
          >
            🚀 开始干预
          </button>
        </div>
      </div>

      <div className="min-h-[70vh]">
        {activeTab === 'review' ? (
          <ParentReviewDashboard
            childId={dailyDeckProps?.childId}
            childName={dailyDeckProps?.childName}
          />
        ) : (
          <DailyDeck {...dailyDeckProps} />
        )}
      </div>
    </div>
  );
}

export default ReviewInterventionWorkbench;
