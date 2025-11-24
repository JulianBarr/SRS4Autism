import React from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import theme from '../styles/theme';

/**
 * Content Category Navigation
 * Organizes content into: Language, Math, Common Knowledge, Culture
 */
const ContentCategoryNav = ({ activeCategory, onCategoryChange }) => {
  const { t } = useLanguage();
  
  const categories = [
    { id: 'language', label: t('language'), icon: '📚', color: theme.categories.language },
    { id: 'math', label: t('math'), icon: '🔢', color: theme.categories.math },
    { id: 'knowledge', label: t('commonKnowledge'), icon: '🌍', color: theme.categories.knowledge },
    { id: 'culture', label: t('culture'), icon: '🎭', color: theme.categories.culture }
  ];
  
  return (
    <nav style={{
      display: 'flex',
      gap: theme.spacing.sm,
      marginBottom: theme.spacing.lg,
      borderBottom: `2px solid ${theme.ui.border}`,
      paddingBottom: theme.spacing.md
    }}>
      {categories.map(category => (
        <button
          key={category.id}
          onClick={() => onCategoryChange(category.id)}
          style={{
            padding: `${theme.spacing.sm} ${theme.spacing.md}`,
            border: 'none',
            borderBottom: activeCategory === category.id 
              ? `3px solid ${category.color.primary}` 
              : '3px solid transparent',
            backgroundColor: activeCategory === category.id 
              ? category.color.background 
              : 'transparent',
            color: activeCategory === category.id 
              ? category.color.primary 
              : theme.ui.text.secondary,
            fontSize: '16px',
            fontWeight: activeCategory === category.id ? '600' : '400',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            borderRadius: `${theme.borderRadius.sm} ${theme.borderRadius.sm} 0 0`
          }}
        >
          <span style={{ marginRight: theme.spacing.xs }}>{category.icon}</span>
          {category.label}
        </button>
      ))}
    </nav>
  );
};

export default ContentCategoryNav;

