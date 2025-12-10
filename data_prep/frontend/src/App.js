import React from 'react';
import PinyinGapFillSuggestions from './components/PinyinGapFillSuggestions';
import './App.css';

function App() {
  return (
    <div className="App">
      <header style={{ padding: '20px', backgroundColor: '#f5f5f5', borderBottom: '1px solid #ddd' }}>
        <h1>Data Preparation Tool</h1>
        <p>Pinyin Syllable Gap Fill Suggestions Management</p>
      </header>
      <main style={{ padding: '20px' }}>
        <PinyinGapFillSuggestions />
      </main>
    </div>
  );
}

export default App;

