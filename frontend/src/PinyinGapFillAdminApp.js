import React from 'react';
import PinyinGapFillAdmin from './components/PinyinGapFillAdmin';
import './index.css';

/**
 * Standalone Admin App for Pinyin Gap Fill Suggestions
 * 
 * This is a separate entry point for the admin interface.
 * Access via: http://localhost:3000/admin/pinyin-gap-fill
 * Or as a standalone app if configured in routing.
 */
function PinyinGapFillAdminApp() {
  return (
    <div className="App">
      <PinyinGapFillAdmin />
    </div>
  );
}

export default PinyinGapFillAdminApp;

