import React from 'react';
import './SimpleHands.css';

/**
 * SimpleHands - Static hand visual component showing which finger to use
 * 
 * Renders left and right hands using provided SVG paths.
 * Highlights the active finger in blue.
 */
const SimpleHands = ({ activeFinger }) => {
  const isActive = (fingerId) => {
    return activeFinger === fingerId;
  };

  const HAND_PATHS = {
    left: {
      pinky: "M10,80 Q10,40 20,20 Q30,40 30,80",
      ring: "M35,80 Q35,20 45,10 Q55,20 55,80",
      middle: "M60,80 Q60,10 70,0 Q80,10 80,80",
      index: "M85,80 Q85,20 95,20 Q105,40 105,80",
      thumb: "M110,90 Q130,70 140,90 Q120,110 110,100"
    },
    right: {
      pinky: "M290,80 Q290,40 280,20 Q270,40 270,80",
      ring: "M265,80 Q265,20 255,10 Q245,20 245,80",
      middle: "M240,80 Q240,10 230,0 Q220,10 220,80",
      index: "M215,80 Q215,20 205,20 Q195,40 195,80",
      thumb: "M190,90 Q170,70 160,90 Q180,110 190,100"
    }
  };

  const getFingerFill = (hand, finger) => {
    const fingerId = `${hand === 'left' ? 'l' : 'r'}-${finger}`;
    return isActive(fingerId) ? '#3b82f6' : '#e5e7eb';
  };

  return (
    <div className="simple-hands-container">
      {/* Left Hand */}
      <div className="hand-wrapper">
        <div className="hand-label">Left Hand</div>
        <svg
          viewBox="0 0 300 150"
          width="250"
          height="125"
          className="hand-svg"
        >
          {/* Palm - Left */}
          <ellipse
            cx="75"
            cy="100"
            rx="50"
            ry="40"
            fill="#f9fafb"
            stroke="#d1d5db"
            strokeWidth="1"
          />
          
          {/* Left Hand Fingers */}
          <path
            d={HAND_PATHS.left.pinky}
            fill={getFingerFill('left', 'pinky')}
            stroke="#9ca3af"
            strokeWidth="2"
            className={`finger-path ${isActive('l-pinky') ? 'active' : ''}`}
          />
          <path
            d={HAND_PATHS.left.ring}
            fill={getFingerFill('left', 'ring')}
            stroke="#9ca3af"
            strokeWidth="2"
            className={`finger-path ${isActive('l-ring') ? 'active' : ''}`}
          />
          <path
            d={HAND_PATHS.left.middle}
            fill={getFingerFill('left', 'middle')}
            stroke="#9ca3af"
            strokeWidth="2"
            className={`finger-path ${isActive('l-middle') ? 'active' : ''}`}
          />
          <path
            d={HAND_PATHS.left.index}
            fill={getFingerFill('left', 'index')}
            stroke="#9ca3af"
            strokeWidth="2"
            className={`finger-path ${isActive('l-index') ? 'active' : ''}`}
          />
          <path
            d={HAND_PATHS.left.thumb}
            fill={getFingerFill('left', 'thumb')}
            stroke="#9ca3af"
            strokeWidth="2"
            className={`finger-path ${isActive('l-thumb') ? 'active' : ''}`}
          />
        </svg>
      </div>

      {/* Right Hand */}
      <div className="hand-wrapper">
        <div className="hand-label">Right Hand</div>
        <svg
          viewBox="0 0 300 150"
          width="250"
          height="125"
          className="hand-svg"
        >
          {/* Palm - Right */}
          <ellipse
            cx="225"
            cy="100"
            rx="50"
            ry="40"
            fill="#f9fafb"
            stroke="#d1d5db"
            strokeWidth="1"
          />
          
          {/* Right Hand Fingers */}
          <path
            d={HAND_PATHS.right.pinky}
            fill={getFingerFill('right', 'pinky')}
            stroke="#9ca3af"
            strokeWidth="2"
            className={`finger-path ${isActive('r-pinky') ? 'active' : ''}`}
          />
          <path
            d={HAND_PATHS.right.ring}
            fill={getFingerFill('right', 'ring')}
            stroke="#9ca3af"
            strokeWidth="2"
            className={`finger-path ${isActive('r-ring') ? 'active' : ''}`}
          />
          <path
            d={HAND_PATHS.right.middle}
            fill={getFingerFill('right', 'middle')}
            stroke="#9ca3af"
            strokeWidth="2"
            className={`finger-path ${isActive('r-middle') ? 'active' : ''}`}
          />
          <path
            d={HAND_PATHS.right.index}
            fill={getFingerFill('right', 'index')}
            stroke="#9ca3af"
            strokeWidth="2"
            className={`finger-path ${isActive('r-index') ? 'active' : ''}`}
          />
          <path
            d={HAND_PATHS.right.thumb}
            fill={getFingerFill('right', 'thumb')}
            stroke="#9ca3af"
            strokeWidth="2"
            className={`finger-path ${isActive('r-thumb') ? 'active' : ''}`}
          />
        </svg>
      </div>
    </div>
  );
};

export default SimpleHands;


