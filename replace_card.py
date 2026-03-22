import re

with open('frontend/src/components/DailyDeck.jsx', 'r') as f:
    content = f.read()

# The ExpandableQuestCard code
new_card_code = """
const ExpandableQuestCard = ({ quest, isCompleted, showButtons, submitting, onRecordFeedback, onOpenChat }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const isSubmitting = submitting === quest.quest_id;
  const pep3Items = quest.pep3_items || [];
  
  const title = quest.label || quest.title || "(未命名任务)";
  
  const badges = [];
  if (quest.badges) {
    badges.push(...quest.badges);
  } else if (quest.pep3_standard) {
    badges.push(`PEP-3: ${quest.pep3_standard}`);
  }
  
  let conditions = quest.conditions || "";
  if (!conditions && quest.ecumenical_integration?.assessment?.content) {
    conditions = quest.ecumenical_integration.assessment.content;
  }
  
  let materials = quest.suggested_materials || quest.materials || "";
  
  let steps = quest.teaching_steps || quest.steps || "";
  if (!steps && quest.ecumenical_integration?.teaching?.content) {
    steps = quest.ecumenical_integration.teaching.content;
  }
  
  let generalization = quest.home_generalization || quest.generalization || "";
  if (!generalization && quest.ecumenical_integration?.generalization?.content) {
    generalization = quest.ecumenical_integration.generalization.content;
  }

  return (
    <div className={`bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden transition-all duration-300 ${isCompleted ? 'opacity-60 bg-slate-50' : ''}`}>
      {/* Header */}
      <div 
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-slate-50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3 flex-1 flex-wrap">
          <h2 className="text-lg font-bold text-slate-800">
            {title}
          </h2>
          {badges.map((badge, idx) => (
            <span key={idx} className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-100">
              {badge}
            </span>
          ))}
          {quest.pep3_standard && !quest.badges && (
             <Pep3Tooltip pep3Standard={quest.pep3_standard} pep3Items={pep3Items} />
          )}
        </div>
        <div className="flex items-center justify-center w-8 h-8 rounded-full bg-slate-100 text-slate-500">
          <svg 
            className={`w-5 h-5 transition-transform duration-300 ${isExpanded ? 'rotate-180' : ''}`} 
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* Body */}
      <div 
        className={`transition-all duration-500 ease-in-out overflow-hidden ${isExpanded ? 'max-h-[2000px] opacity-100' : 'max-h-0 opacity-0'}`}
      >
        <div className="p-5 pt-0 border-t border-slate-100 bg-slate-50/50">
          
          <div className="space-y-6 mt-4">
            {/* 区块 A - 🎯 核心目标 & 条件 */}
            {(conditions || quest.ecumenical_integration?.prerequisite?.content) && (
              <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm">
                <h3 className="text-sm font-bold text-slate-700 mb-2 flex items-center gap-2">
                  <span>🎯</span> 核心目标 & 条件
                </h3>
                <div className="text-sm text-slate-600 leading-relaxed whitespace-pre-wrap">
                  {conditions}
                  {quest.ecumenical_integration?.prerequisite?.content && (
                    <div className="mt-2 pt-2 border-t border-slate-100 text-xs text-slate-500">
                      前置能力: {quest.ecumenical_integration.prerequisite.content}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* 区块 B - 🛠️ 教具与步骤 */}
            {(materials || steps) && (
              <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm">
                <h3 className="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
                  <span>🛠️</span> 教具与步骤
                </h3>
                {materials && (
                  <div className="mb-3 p-3 bg-amber-50 rounded-md border border-amber-100 text-sm text-amber-900">
                    <span className="font-semibold">教具准备：</span> {materials}
                  </div>
                )}
                {steps && (
                  <div className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
                    {steps}
                  </div>
                )}
              </div>
            )}

            {/* 区块 C - 🏡 家庭泛化 */}
            {generalization && (
              <blockquote className="border-l-4 border-emerald-400 bg-emerald-50 p-4 rounded-r-lg">
                <h3 className="text-sm font-bold text-emerald-800 mb-1 flex items-center gap-2">
                  <span>🏡</span> 家庭泛化建议
                </h3>
                <p className="text-sm text-emerald-700 leading-relaxed whitespace-pre-wrap">
                  {generalization}
                </p>
              </blockquote>
            )}
          </div>

          {/* Action Area */}
          <div className="mt-6 pt-5 border-t border-slate-200">
            <div className="flex justify-end gap-3 mb-5">
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
      </div>
    </div>
  );
};
"""

# Place ExpandableQuestCard before DailyDeck
content = content.replace("function DailyDeck(", new_card_code + "\nfunction DailyDeck(")

# Now find the old QuestCard and remove it
quest_card_pattern = re.compile(r"  const QuestCard = \(\{ quest, isCompleted, showButtons \}\) => \{[\s\S]*?  \};\n\n  return \(", re.MULTILINE)

content = quest_card_pattern.sub("  return (", content)

# Now find all usages of QuestCard and replace with ExpandableQuestCard
content = content.replace("<QuestCard", """<ExpandableQuestCard
                    submitting={submitting}
                    onRecordFeedback={recordFeedback}
                    onOpenChat={openChat}""")

content = content.replace("</QuestCard>", "</ExpandableQuestCard>")

# Wait, the closing tag of QuestCard was self-closing in the original:
# <QuestCard key={quest.quest_id} quest={quest} isCompleted={false} showButtons={true} />

with open('frontend/src/components/DailyDeck.jsx', 'w') as f:
    f.write(content)

print("Done")
