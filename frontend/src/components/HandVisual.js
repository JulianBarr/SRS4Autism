import React from 'react';
import './HandVisual.css';

/**
 * HandVisual - Visual hand component showing which finger to use
 * 
 * Displays a hand image with a blue dot overlay indicating the active finger.
 * Uses placeholder coordinates that can be calibrated later.
 * 
 * CALIBRATION TOOL: Click anywhere on the image to get coordinates in the console.
 */

// Placeholder finger positions (to be calibrated)
const FINGER_POSITIONS = {
  'l-pinky':  { top: '50.3%', left: '18.4%' },
  'l-ring':   { top: '43.7%', left: '24.2%' },
  'l-middle': { top: '41.3%', left: '29.7%' },
  'l-index':  { top: '45.8%', left: '34.7%' },
  'r-index':  { top: '47.9%', left: '65.1%' },
  'r-middle': { top: '44.6%', left: '70.6%' },
  'r-ring':   { top: '46.0%%', lef: '74.3%' },
  'r-pinky':  { top: '51.7%', left: '79.2%' },
  'r-thumb':  { top: '60.6%', left: '59.9%' } // Spacebar
};

const HandVisual = ({ activeFinger }) => {
  const position = activeFinger ? FINGER_POSITIONS[activeFinger] : null;

  // Calibration tool: Click on image to get coordinates
  // Use the IMAGE element itself for accurate measurements
  const handleCalibrate = (e) => {
    // Get the rectangle of the IMAGE ITSELF (e.target is the img element)
    const rect = e.target.getBoundingClientRect();
    
    // Calculate % relative to that rectangle
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    
    console.log(`FINGER_POSITIONS entry: { top: '${y.toFixed(1)}%', left: '${x.toFixed(1)}%' },`);
    console.log(`Click position: left: '${x.toFixed(1)}%', top: '${y.toFixed(1)}%'`);
  };

  return (
    <div className="hand-visual-container">
      <div 
        className="hand-visual-wrapper" 
        style={{ 
          position: 'relative',
          display: 'inline-block',
          lineHeight: 0, // Removes text spacing
          zIndex: 10
        }}
        title="Click on the image to calibrate finger positions (check console for coordinates)"
      >
        {/* Hand Image - Natural aspect ratio (no cropping) */}
        <img 
          src="/typing-hands.png" 
          alt="Hands (Click to calibrate finger positions)" 
          onClick={handleCalibrate}
          style={{ 
            maxHeight: '30vh',
            width: 'auto',
            maxWidth: '100%',
            display: 'block',
            cursor: 'crosshair',
            borderRadius: '8px'
          }} 
        />
        
        {/* Active Finger Overlay Dot */}
        {position && (
          <div
            className="finger-dot"
            style={{
              position: 'absolute',
              top: position.top,
              left: position.left,
              width: '20px',
              height: '20px',
              backgroundColor: '#3b82f6',
              borderRadius: '50%',
              transform: 'translate(-50%, -50%)',
              transition: 'all 0.2s ease',
              boxShadow: '0 0 10px rgba(59, 130, 246, 0.6)',
              zIndex: 11,
              border: '2px solid white',
              pointerEvents: 'none' // Don't interfere with clicks
            }}
          />
        )}
      </div>
    </div>
  );
};

export default HandVisual;
