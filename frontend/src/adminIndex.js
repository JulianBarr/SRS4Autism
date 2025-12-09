import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import PinyinGapFillAdminApp from './PinyinGapFillAdminApp';
import { LanguageProvider } from './i18n/LanguageContext';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <LanguageProvider>
      <PinyinGapFillAdminApp />
    </LanguageProvider>
  </React.StrictMode>
);

