import React, { useState } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import theme from '../styles/theme';

/**
 * Mario's World - Map-based view using actual map image
 * Captain mode only for now
 * Based on the 4-layer cognitive development model:
 * - Layer 0: Cognition Cove (基础认知)
 * - Layer 1: Symbol City (符号与工具)
 * - Layer 2: Logic Lab (结构与逻辑)
 * - Layer 3: Story Valley (场景与故事)
 */
const MariosWorld = ({ profile, onNavigateToContent }) => {
  const { t, language } = useLanguage();
  const [activeIsland, setActiveIsland] = useState(null);
  const [cognitionLanguage, setCognitionLanguage] = useState(null); // 'zh' or 'en' for Cognition Cove
  const [cognitionContentType, setCognitionContentType] = useState(null); // Content type based on language

  // Map image path - update this to the actual path of your map image
  const mapImagePath = '/marios-world-map.png'; // Place in public folder

  // Island coordinates based on actual click measurements
  // Using percentage coordinates for responsive layout
  const islands = [
    {
      id: 'cognition',
      name: language === 'zh' ? '基础认知' : 'Cognition Cove',
      nameEn: 'Cognition Cove',
      nameZh: '基础认知',
      description: language === 'zh' 
        ? '基础认知：命名、颜色、数字' 
        : 'Foundations: Naming, Colors, Numbers',
      mastery: 85,
      newItems: 12,
      examples: language === 'zh' 
        ? ['水果篮子', '大与小', '颜色识别'] 
        : ['Fruit Basket', 'Big & Small', 'Color Recognition'],
      // Actual center: Pixel(1035, 1252) | CSS(37.6%, 81.5%)
      // Approximate ellipse: rx=10.5%, ry=13%
      clickArea: { 
        width: '21%', 
        height: '26%',
        cx: '37.6%',
        cy: '81.5%'
      }
    },
    {
      id: 'literacy',
      name: language === 'zh' ? '符号与工具' : 'Symbol City',
      nameEn: 'Symbol City',
      nameZh: '符号与工具',
      description: language === 'zh' 
        ? '工具：拼音、汉字、自然拼读' 
        : 'Tools: Pinyin, Hanzi, Phonics',
      mastery: 42,
      newItems: 5,
      examples: language === 'zh' 
        ? ['拼音侦探', '汉字识别', '自然拼读'] 
        : ['Pinyin Detective', 'Hanzi Recognition', 'Phonics'],
      // Actual center: Pixel(727, 623) | CSS(26.4%, 40.6%)
      // Approximate ellipse: rx=10%, ry=12%
      clickArea: { 
        width: '20%', 
        height: '24%',
        cx: '26.4%',
        cy: '40.6%'
      }
    },
    {
      id: 'logic',
      name: language === 'zh' ? '结构与逻辑' : 'Logic Lab',
      nameEn: 'Logic Lab',
      nameZh: '结构与逻辑',
      description: language === 'zh' 
        ? '结构：语法、数学、构建' 
        : 'Structure: Grammar, Math, Builder',
      mastery: 30,
      newItems: 8,
      examples: language === 'zh' 
        ? ['句子构建', '数学运算', '逻辑模式'] 
        : ['Sentence Builder', 'Math Operations', 'Logic Patterns'],
      // Actual center: Pixel(1439, 387) | CSS(52.3%, 25.2%)
      // Approximate ellipse: rx=11%, ry=13%
      clickArea: { 
        width: '22%', 
        height: '26%',
        cx: '52.3%',
        cy: '25.2%'
      }
    },
    {
      id: 'story',
      name: language === 'zh' ? '场景与故事' : 'Story Valley',
      nameEn: 'Story Valley',
      nameZh: '场景与故事',
      description: language === 'zh' 
        ? '应用：场景、社交、故事' 
        : 'Application: Scenarios, Social, Stories',
      mastery: 20,
      newItems: 3,
      examples: language === 'zh' 
        ? ['购物场景', '社交故事', '阅读理解'] 
        : ['Shopping Scenario', 'Social Stories', 'Reading Comprehension'],
      // Actual center: Pixel(1986, 872) | CSS(72.2%, 56.8%)
      // Approximate ellipse: rx=11%, ry=14%
      clickArea: { 
        width: '22%', 
        height: '28%',
        cx: '72.2%',
        cy: '56.8%'
      }
    }
  ];

  const IslandDetail = () => {
    if (!activeIsland) return null;

    return (
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '20px'
      }} onClick={() => setActiveIsland(null)}>
        <div style={{
          backgroundColor: 'white',
          borderRadius: '24px',
          maxWidth: '800px',
          width: '100%',
          maxHeight: '85vh',
          overflow: 'auto',
          boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
          position: 'relative'
        }} onClick={(e) => e.stopPropagation()}>
          {/* Header */}
          <div style={{
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            padding: '32px',
            borderRadius: '24px 24px 0 0',
            position: 'relative',
            overflow: 'hidden'
          }}>
            <div style={{
              position: 'absolute',
              top: '-50px',
              right: '-50px',
              width: '200px',
              height: '200px',
              backgroundColor: 'rgba(255,255,255,0.1)',
              borderRadius: '50%',
              filter: 'blur(40px)'
            }}></div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', position: 'relative', zIndex: 10 }}>
              <div>
                <div style={{ fontSize: '12px', fontWeight: 'bold', color: 'rgba(255,255,255,0.8)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
                  {language === 'zh' ? '区域' : 'Sector'} {activeIsland.id.toUpperCase()}
                </div>
                <h2 style={{ fontSize: '36px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
                  {activeIsland.name}
                </h2>
                <p style={{ fontSize: '16px', color: 'rgba(255,255,255,0.9)', fontWeight: '500' }}>
                  {activeIsland.description}
                </p>
              </div>
            </div>
            <button 
              onClick={() => {
                setActiveIsland(null);
                setCognitionLanguage(null);
                setCognitionContentType(null);
              }}
              style={{
                position: 'absolute',
                top: '16px',
                right: '16px',
                backgroundColor: 'rgba(255,255,255,0.3)',
                border: 'none',
                borderRadius: '50%',
                width: '40px',
                height: '40px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '24px',
                color: 'white',
                zIndex: 20
              }}
            >
              ×
            </button>
          </div>

          {/* Content */}
          <div style={{ padding: '32px', backgroundColor: '#f9fafb' }}>
            {/* Mastery Progress */}
            <div style={{
              backgroundColor: 'white',
              padding: '24px',
              borderRadius: '16px',
              marginBottom: '24px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
            }}>
              <h3 style={{ fontSize: '12px', fontWeight: 'bold', color: '#9ca3af', textTransform: 'uppercase', marginBottom: '16px' }}>
                {language === 'zh' ? '掌握进度' : 'Mastery Progress'}
              </h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '12px' }}>
                <span style={{ fontSize: '36px', fontWeight: 'bold', color: '#1f2937' }}>
                  {activeIsland.mastery}%
                </span>
              </div>
              <div style={{
                height: '12px',
                backgroundColor: '#e5e7eb',
                borderRadius: '6px',
                overflow: 'hidden'
              }}>
                <div style={{
                  width: `${activeIsland.mastery}%`,
                  height: '100%',
                  backgroundColor: theme.categories.language.primary,
                  borderRadius: '6px',
                  transition: 'width 1s ease'
                }}></div>
              </div>
            </div>

            {/* New Items */}
            <div style={{
              backgroundColor: 'white',
              padding: '24px',
              borderRadius: '16px',
              marginBottom: '24px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 'bold', color: '#1f2937' }}>
                  {language === 'zh' ? '新内容' : 'New Content'}
                </h3>
                <span style={{
                  backgroundColor: '#fef3c7',
                  color: '#92400e',
                  padding: '4px 12px',
                  borderRadius: '12px',
                  fontSize: '14px',
                  fontWeight: 'bold'
                }}>
                  {activeIsland.newItems} {language === 'zh' ? '项' : 'items'}
                </span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {activeIsland.examples.map((example, idx) => (
                  <span key={idx} style={{
                    padding: '8px 16px',
                    backgroundColor: '#f3f4f6',
                    color: '#374151',
                    borderRadius: '8px',
                    fontSize: '14px',
                    fontWeight: '500'
                  }}>
                    {example}
                  </span>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div style={{
              backgroundColor: 'white',
              padding: '24px',
              borderRadius: '16px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
            }}>
              <h3 style={{ fontSize: '16px', fontWeight: 'bold', color: '#1f2937', marginBottom: '16px' }}>
                {language === 'zh' ? '操作' : 'Actions'}
              </h3>
              {/* Special two-level navigation for Cognition Cove */}
              {activeIsland.id === 'cognition' && onNavigateToContent ? (
                <div>
                  {!cognitionLanguage ? (
                    /* Level 1: Language Selection */
                    <div>
                      <h4 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '16px', color: '#374151' }}>
                        {language === 'zh' ? '选择语言' : 'Select Language'}
                      </h4>
                      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                        <button style={{
                          flex: '1 1 45%',
                          minWidth: '150px',
                          padding: '16px 24px',
                          backgroundColor: '#f0fdf4',
                          color: '#10b981',
                          border: '2px solid #10b981',
                          borderRadius: '12px',
                          fontSize: '16px',
                          fontWeight: 'bold',
                          cursor: 'pointer',
                          transition: 'all 0.2s'
                        }} onMouseEnter={(e) => {
                          e.target.style.backgroundColor = '#dcfce7';
                          e.target.style.transform = 'scale(1.02)';
                        }} onMouseLeave={(e) => {
                          e.target.style.backgroundColor = '#f0fdf4';
                          e.target.style.transform = 'scale(1)';
                        }} onClick={() => setCognitionLanguage('zh')}>
                          {language === 'zh' ? '中文' : 'Chinese'}
                        </button>
                        <button style={{
                          flex: '1 1 45%',
                          minWidth: '150px',
                          padding: '16px 24px',
                          backgroundColor: '#f0fdf4',
                          color: '#10b981',
                          border: '2px solid #10b981',
                          borderRadius: '12px',
                          fontSize: '16px',
                          fontWeight: 'bold',
                          cursor: 'pointer',
                          transition: 'all 0.2s'
                        }} onMouseEnter={(e) => {
                          e.target.style.backgroundColor = '#dcfce7';
                          e.target.style.transform = 'scale(1.02)';
                        }} onMouseLeave={(e) => {
                          e.target.style.backgroundColor = '#f0fdf4';
                          e.target.style.transform = 'scale(1)';
                        }} onClick={() => setCognitionLanguage('en')}>
                          {language === 'zh' ? '英文' : 'English'}
                        </button>
                      </div>
                    </div>
                  ) : !cognitionContentType ? (
                    /* Level 2: Content Type Selection */
                    <div>
                      <button style={{
                        marginBottom: '16px',
                        padding: '8px 16px',
                        fontSize: '14px',
                        border: '1px solid #ddd',
                        borderRadius: '6px',
                        backgroundColor: 'white',
                        cursor: 'pointer',
                        color: '#666'
                      }} onClick={() => setCognitionLanguage(null)}>
                        ← {language === 'zh' ? '返回' : 'Back'}
                      </button>
                      <h4 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '16px', color: '#374151' }}>
                        {language === 'zh' ? '选择内容类型' : 'Select Content Type'}
                      </h4>
                      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                        {cognitionLanguage === 'zh' ? (
                          <>
                            <button style={{
                              flex: '1 1 45%',
                              minWidth: '150px',
                              padding: '16px 24px',
                              backgroundColor: '#fef3c7',
                              color: '#f59e0b',
                              border: '2px solid #f59e0b',
                              borderRadius: '12px',
                              fontSize: '16px',
                              fontWeight: 'bold',
                              cursor: 'pointer',
                              transition: 'all 0.2s'
                            }} onMouseEnter={(e) => {
                              e.target.style.backgroundColor = '#fde68a';
                              e.target.style.transform = 'scale(1.02)';
                            }} onMouseLeave={(e) => {
                              e.target.style.backgroundColor = '#fef3c7';
                              e.target.style.transform = 'scale(1)';
                            }} onClick={() => {
                              setActiveIsland(null);
                              setCognitionLanguage(null);
                              setCognitionContentType(null);
                              onNavigateToContent('word-recognition-zh');
                            }}>
                              基础命名
                            </button>
                            <button style={{
                              flex: '1 1 45%',
                              minWidth: '150px',
                              padding: '16px 24px',
                              backgroundColor: '#dcfce7',
                              color: '#10b981',
                              border: '2px solid #10b981',
                              borderRadius: '12px',
                              fontSize: '16px',
                              fontWeight: 'bold',
                              cursor: 'pointer',
                              transition: 'all 0.2s'
                            }} onMouseEnter={(e) => {
                              e.target.style.backgroundColor = '#bbf7d0';
                              e.target.style.transform = 'scale(1.02)';
                            }} onMouseLeave={(e) => {
                              e.target.style.backgroundColor = '#dcfce7';
                              e.target.style.transform = 'scale(1)';
                            }} onClick={() => {
                              setActiveIsland(null);
                              // Don't reset state here - let App.js handle it
                              onNavigateToContent('pinyin-learning');
                            }}>
                              基础拼音
                            </button>
                          </>
                        ) : (
                          <>
                            <button style={{
                              flex: '1 1 45%',
                              minWidth: '150px',
                              padding: '16px 24px',
                              backgroundColor: '#dbeafe',
                              color: '#3b82f6',
                              border: '2px solid #3b82f6',
                              borderRadius: '12px',
                              fontSize: '16px',
                              fontWeight: 'bold',
                              cursor: 'pointer',
                              transition: 'all 0.2s'
                            }} onMouseEnter={(e) => {
                              e.target.style.backgroundColor = '#bfdbfe';
                              e.target.style.transform = 'scale(1.02)';
                            }} onMouseLeave={(e) => {
                              e.target.style.backgroundColor = '#dbeafe';
                              e.target.style.transform = 'scale(1)';
                            }} onClick={() => {
                              setActiveIsland(null);
                              setCognitionLanguage(null);
                              setCognitionContentType(null);
                              onNavigateToContent('word-recognition-en');
                            }}>
                              Naming
                            </button>
                            <button style={{
                              flex: '1 1 45%',
                              minWidth: '150px',
                              padding: '16px 24px',
                              backgroundColor: '#f3e8ff',
                              color: '#8b5cf6',
                              border: '2px solid #8b5cf6',
                              borderRadius: '12px',
                              fontSize: '16px',
                              fontWeight: 'bold',
                              cursor: 'pointer',
                              transition: 'all 0.2s'
                            }} onMouseEnter={(e) => {
                              e.target.style.backgroundColor = '#e9d5ff';
                              e.target.style.transform = 'scale(1.02)';
                            }} onMouseLeave={(e) => {
                              e.target.style.backgroundColor = '#f3e8ff';
                              e.target.style.transform = 'scale(1)';
                            }} onClick={() => {
                              setActiveIsland(null);
                              setCognitionLanguage(null);
                              setCognitionContentType(null);
                              // TODO: Add phonics navigation when ready
                              alert(language === 'zh' ? 'Phonics功能即将推出' : 'Phonics feature coming soon');
                            }}>
                              Phonics
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : (
                /* Default actions for other islands */
                <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                  <button style={{
                    padding: '12px 24px',
                    backgroundColor: theme.categories.language.primary,
                    color: 'white',
                    border: 'none',
                    borderRadius: '12px',
                    fontSize: '14px',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
                    transition: 'all 0.2s'
                  }} onMouseEnter={(e) => {
                    e.target.style.transform = 'translateY(-2px)';
                    e.target.style.boxShadow = '0 6px 12px rgba(0,0,0,0.15)';
                  }} onMouseLeave={(e) => {
                    e.target.style.transform = 'translateY(0)';
                    e.target.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';
                  }}>
                    {language === 'zh' ? '📊 查看详情' : '📊 View Details'}
                  </button>
                  <button style={{
                    padding: '12px 24px',
                    backgroundColor: '#8b5cf6',
                    color: 'white',
                    border: 'none',
                    borderRadius: '12px',
                    fontSize: '14px',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
                    transition: 'all 0.2s'
                  }} onMouseEnter={(e) => {
                    e.target.style.transform = 'translateY(-2px)';
                    e.target.style.boxShadow = '0 6px 12px rgba(0,0,0,0.15)';
                  }} onMouseLeave={(e) => {
                    e.target.style.transform = 'translateY(0)';
                    e.target.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';
                  }}>
                    {language === 'zh' ? '✨ 生成新任务' : '✨ Generate New Quest'}
                  </button>
                </div>
              )}
              </div>
            </div>
          </div>
        </div>
    );
  };

  return (
    <div style={{ 
      position: 'relative', 
      width: '100%', 
      height: 'calc(100vh - 200px)',
      minHeight: '600px',
      overflow: 'hidden',
      backgroundColor: '#f5f5f5',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      padding: '0'
    }}>
      {/* Map Image Container */}
      <div style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        overflow: 'hidden'
      }}>
        {/* Map Image - Fit to viewport */}
        <img 
          src={mapImagePath}
          alt={language === 'zh' ? '马力世界地图' : "Mario's World Map"}
          style={{
            width: 'auto',
            height: '100%',
            maxWidth: '100%',
            maxHeight: '100%',
            objectFit: 'contain',
            display: 'block'
          }}
          onError={(e) => {
            console.error('Map image not found:', mapImagePath);
            e.target.style.display = 'none';
          }}
        />

        {/* Clickable Areas Overlay - positioned relative to image */}
        {islands.map((island) => (
          <div key={island.id}>
            {/* Clickable Area - Ellipse shape centered on cx, cy */}
            <div
              style={{
                position: 'absolute',
                left: island.clickArea.cx,
                top: island.clickArea.cy,
                width: island.clickArea.width,
                height: island.clickArea.height,
                transform: 'translate(-50%, -50%)',
                cursor: 'pointer',
                zIndex: 10,
                border: '2px solid transparent',
                borderRadius: '50%', // Ellipse shape
                transition: 'all 0.3s ease'
              }}
              onClick={() => setActiveIsland(island)}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.6)';
                e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.15)';
                e.currentTarget.style.transform = 'translate(-50%, -50%) scale(1.05)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'transparent';
                e.currentTarget.style.backgroundColor = 'transparent';
                e.currentTarget.style.transform = 'translate(-50%, -50%) scale(1)';
              }}
              title={island.name}
            />
            {/* Island Name Label - positioned above the island */}
            <div
              style={{
                position: 'absolute',
                left: island.clickArea.cx,
                top: `calc(${island.clickArea.cy} - ${island.clickArea.height} / 2 - 35px)`,
                transform: 'translateX(-50%)',
                zIndex: 11,
                pointerEvents: 'none',
                textAlign: 'center'
              }}
            >
              <span style={{
                backgroundColor: 'rgba(0, 0, 0, 0.7)',
                backdropFilter: 'blur(8px)',
                color: 'white',
                padding: '6px 14px',
                borderRadius: '16px',
                fontSize: '16px',
                fontWeight: 'bold',
                textShadow: '0 2px 4px rgba(0,0,0,0.5)',
                display: 'inline-block',
                whiteSpace: 'nowrap',
                boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
                border: '1px solid rgba(255,255,255,0.2)'
              }}>
                {island.name}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Island Detail Modal */}
      <IslandDetail />
    </div>
  );
};

export default MariosWorld;
