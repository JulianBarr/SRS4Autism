import React, { useState } from 'react';
import api from '../utils/api';
import { useLanguage } from '../i18n/LanguageContext'; // Assume this exists for language context

/**
 * Adaptive parent survey card — distinct from daily quest cards (soft purple panel).
 */
function SurveyFeedCard({ question, childId, onAnswerSubmitted }) {
  const { language } = useLanguage();
  const [selectedOptionUri, setSelectedOptionUri] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!question?.question_uri) {
    return null;
  }

  const { question_uri: questionUri, promptTemplate, options = [] } = question;

  const handleSubmit = async () => {
    if (!selectedOptionUri || isSubmitting) return;

    const selectedOption = options.find(opt => (opt.option_uri || opt.stateAction) === selectedOptionUri);
    if (!selectedOption) return;

    if (!childId || String(childId).trim() === '') {
      console.error('survey answer: child_id is required');
      return;
    }
    setIsSubmitting(true);
    try {
      await api.post('/api/survey/answer', {
        question_uri: questionUri,
        stateAction: selectedOption.stateAction,
        child_id: childId,
      });
      // Ensure onAnswerSubmitted is awaited for proper parent state management
      await onAnswerSubmitted?.();
      setSelectedOptionUri(null); // Clear selection for the next question
    } catch (e) {
      console.error('survey answer failed', e);
    } finally {
      setIsSubmitting(false); // MUST reset here!
    }
  };

  return (
    <div
      className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden"
    >
      <div className="px-5 pt-4 pb-3">
        <h2 className="font-bold text-lg text-gray-800 mb-4">
          {language === 'zh' || language === 'cn' ? '📝 基础能力测评' : '📝 Basic Ability Assessment'}
        </h2>
        <p className="text-base text-gray-700 leading-relaxed whitespace-pre-wrap">
          {promptTemplate}
        </p>
      </div>

      <div className="px-5 pb-4">
        <ul className="space-y-2">
          {options.map((opt) => {
            const id = opt.option_uri || opt.stateAction;
            return (
              <li key={id}>
                <label
                  htmlFor={id}
                  className={`
                    flex items-center p-3 rounded-lg cursor-pointer
                    transition-colors duration-200
                    ${selectedOptionUri === id ? 'bg-indigo-50 border-indigo-200 ring-1 ring-indigo-300' : 'bg-white border border-gray-200 hover:bg-gray-50'}
                  `}
                >
                  <input
                    type="radio"
                    id={id}
                    name="survey_option"
                    value={id}
                    checked={selectedOptionUri === id}
                    onChange={() => setSelectedOptionUri(id)}
                    className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 mr-3"
                    disabled={isSubmitting}
                  />
                  <span className="text-base text-gray-700">{opt.optionText}</span>
                </label>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="px-5 pb-4 text-right">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!selectedOptionUri || isSubmitting}
          className={`
            px-6 py-2 rounded-lg font-medium text-white transition-all
            ${!selectedOptionUri || isSubmitting ? 'bg-gray-300 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-700'}
          `}
        >
          {isSubmitting ? (language === 'zh' || language === 'cn' ? '提交中…' : 'Submitting…') : (language === 'zh' || language === 'cn' ? '提交' : 'Submit')}
        </button>
      </div>
    </div>
  );
}

export default SurveyFeedCard;
