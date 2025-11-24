import React, { useState } from 'react';
import { useLanguage } from '../../i18n/LanguageContext';
import BaseWidget from '../widgets/BaseWidget';
import ProfileManager from '../ProfileManager';
import theme from '../../styles/theme';

/**
 * Language Learning View
 * Contains Chinese/English vocabulary and grammar
 */
const LanguageLearningView = ({ profiles, onProfilesChange }) => {
  const { t } = useLanguage();
  const [activeSubCategory, setActiveSubCategory] = useState('vocabulary');
  
  const subCategories = [
    { id: 'vocabulary', label: t('chineseVocabulary'), icon: '📝' },
    { id: 'english', label: t('englishVocabulary'), icon: '📝' },
    { id: 'grammar', label: t('chineseGrammar'), icon: '📖' },
    { id: 'englishGrammar', label: t('englishGrammar'), icon: '📖' }
  ];
  
  return (
    <div style={{ padding: theme.spacing.lg }}>
      {/* Sub-category Navigation */}
      <div style={{
        display: 'flex',
        gap: theme.spacing.sm,
        marginBottom: theme.spacing.lg,
        flexWrap: 'wrap'
      }}>
        {subCategories.map(sub => (
          <button
            key={sub.id}
            onClick={() => setActiveSubCategory(sub.id)}
            style={{
              padding: `${theme.spacing.sm} ${theme.spacing.md}`,
              border: `2px solid ${activeSubCategory === sub.id ? theme.categories.language.primary : theme.ui.border}`,
              backgroundColor: activeSubCategory === sub.id 
                ? theme.categories.language.background 
                : theme.ui.background,
              color: activeSubCategory === sub.id 
                ? theme.categories.language.primary 
                : theme.ui.text.primary,
              borderRadius: theme.borderRadius.md,
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: activeSubCategory === sub.id ? '600' : '400',
              transition: 'all 0.2s ease'
            }}
          >
            <span style={{ marginRight: theme.spacing.xs }}>{sub.icon}</span>
            {sub.label}
          </button>
        ))}
      </div>
      
      {/* Content Area */}
      <div>
        {activeSubCategory === 'vocabulary' && (
          <BaseWidget 
            title={t('chineseVocabulary')}
            category="language"
          >
            <ProfileManager 
              profiles={profiles}
              onProfilesChange={onProfilesChange}
              showOnly="chinese-vocab"
            />
          </BaseWidget>
        )}
        
        {activeSubCategory === 'english' && (
          <BaseWidget 
            title={t('englishVocabulary')}
            category="language"
          >
            <ProfileManager 
              profiles={profiles}
              onProfilesChange={onProfilesChange}
              showOnly="english-vocab"
            />
          </BaseWidget>
        )}
        
        {activeSubCategory === 'grammar' && (
          <BaseWidget 
            title={t('chineseGrammar')}
            category="language"
          >
            <ProfileManager 
              profiles={profiles}
              onProfilesChange={onProfilesChange}
              showOnly="chinese-grammar"
            />
          </BaseWidget>
        )}
        
        {activeSubCategory === 'englishGrammar' && (
          <BaseWidget 
            title={t('englishGrammar')}
            category="language"
          >
            <ProfileManager 
              profiles={profiles}
              onProfilesChange={onProfilesChange}
              showOnly="english-grammar"
            />
          </BaseWidget>
        )}
      </div>
    </div>
  );
};

export default LanguageLearningView;

