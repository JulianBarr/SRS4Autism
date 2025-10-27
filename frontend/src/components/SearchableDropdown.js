import React, { useState, useRef, useEffect } from 'react';
import '../styles/SearchableDropdown.css';

const SearchableDropdown = ({ 
  options = [], 
  value, 
  onChange, 
  placeholder = "Select or type...",
  label = "",
  disabled = false,
  onRefresh = null
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchText, setSearchText] = useState(value || '');
  const [filteredOptions, setFilteredOptions] = useState(options);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const containerRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    setSearchText(value || '');
  }, [value]);

  useEffect(() => {
    setFilteredOptions(options);
  }, [options]);

  useEffect(() => {
    // Close dropdown when clicking outside
    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleInputChange = (e) => {
    const text = e.target.value;
    setSearchText(text);
    
    // Filter options based on search text
    const filtered = options.filter(option =>
      option.toLowerCase().includes(text.toLowerCase())
    );
    
    setFilteredOptions(filtered);
    setHighlightedIndex(0);
    setIsOpen(true);
    
    // If user types a custom deck name, still update parent
    onChange(text);
  };

  const handleOptionClick = (option) => {
    setSearchText(option);
    onChange(option);
    setIsOpen(false);
  };

  const handleInputFocus = () => {
    setIsOpen(true);
    setFilteredOptions(options);
  };

  const handleKeyDown = (e) => {
    if (!isOpen) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') {
        setIsOpen(true);
        e.preventDefault();
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setHighlightedIndex(prev =>
          prev < filteredOptions.length - 1 ? prev + 1 : 0
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightedIndex(prev =>
          prev > 0 ? prev - 1 : filteredOptions.length - 1
        );
        break;
      case 'Enter':
        e.preventDefault();
        if (filteredOptions[highlightedIndex]) {
          handleOptionClick(filteredOptions[highlightedIndex]);
        }
        break;
      case 'Escape':
        setIsOpen(false);
        break;
      default:
        break;
    }
  };

  return (
    <div className="searchable-dropdown" ref={containerRef}>
      {label && <label className="searchable-dropdown-label">{label}</label>}
      <div className="searchable-dropdown-input-container">
        <input
          ref={inputRef}
          type="text"
          className="searchable-dropdown-input"
          value={searchText}
          onChange={handleInputChange}
          onFocus={handleInputFocus}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
        />
        <div className="searchable-dropdown-icons">
          {onRefresh && (
            <button
              type="button"
              className="dropdown-refresh-btn"
              onClick={(e) => {
                e.stopPropagation();
                onRefresh();
              }}
              title="Refresh deck list"
            >
              ↻
            </button>
          )}
          <button
            type="button"
            className="dropdown-toggle-btn"
            onClick={() => setIsOpen(!isOpen)}
            disabled={disabled}
          >
            ▼
          </button>
        </div>
      </div>
      
      {isOpen && filteredOptions.length > 0 && (
        <div className="searchable-dropdown-menu">
          {filteredOptions.map((option, index) => (
            <div
              key={option}
              className={`searchable-dropdown-item ${index === highlightedIndex ? 'highlighted' : ''}`}
              onClick={() => handleOptionClick(option)}
              onMouseEnter={() => setHighlightedIndex(index)}
            >
              {option}
            </div>
          ))}
        </div>
      )}
      
      {isOpen && filteredOptions.length === 0 && searchText && (
        <div className="searchable-dropdown-menu">
          <div className="searchable-dropdown-item no-results">
            No matching decks. Press Enter to create "{searchText}"
          </div>
        </div>
      )}
    </div>
  );
};

export default SearchableDropdown;

