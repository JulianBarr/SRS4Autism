import React from 'react';
import PinyinGapFillSuggestions from './PinyinGapFillSuggestions';
import './PinyinGapFillAdmin.css';

/**
 * Pinyin Gap Fill Admin Interface
 * 
 * Separate admin interface for managing pinyin gap fill suggestions.
 * This is a data preparation tool, separate from the main CUMA learning interface.
 */
const PinyinGapFillAdmin = () => {
  // For admin interface, we don't need a profile - it's just data management
  const dummyProfile = { id: 'admin', name: 'Admin' };

  return (
    <div className="pinyin-gap-fill-admin">
      <div className="admin-header">
        <h1>拼音音节填充建议管理</h1>
        <p className="admin-subtitle">Pinyin Syllable Gap Fill Suggestions Management</p>
        <p className="admin-description">
          数据准备工具 - 用于管理和审核拼音音节填充建议
          <br />
          Data Preparation Tool - For managing and reviewing pinyin syllable gap fill suggestions
        </p>
      </div>
      
      <div className="admin-content">
        <PinyinGapFillSuggestions 
          profile={dummyProfile} 
          onProfileUpdate={() => {}}
        />
      </div>
    </div>
  );
};

export default PinyinGapFillAdmin;

