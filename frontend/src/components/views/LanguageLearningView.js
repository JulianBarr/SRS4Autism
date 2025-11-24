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
  
  return (
    <div style={{ padding: theme.spacing.lg }}>
      <ProfileManager 
        profiles={profiles}
        onProfilesChange={onProfilesChange}
      />
    </div>
  );
};

export default LanguageLearningView;

