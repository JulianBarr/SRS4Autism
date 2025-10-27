import React, { useRef, useEffect } from 'react';
import '../styles/RichTextEditor.css';

const RichTextEditor = ({ value, onChange, placeholder = "Type or paste content (images supported)..." }) => {
  const editorRef = useRef(null);
  const isUpdating = useRef(false);

  useEffect(() => {
    if (editorRef.current && !isUpdating.current) {
      // Set initial content
      if (value && editorRef.current.innerHTML !== value) {
        editorRef.current.innerHTML = value || '';
      }
    }
  }, [value]);

  const handleInput = () => {
    if (editorRef.current && onChange) {
      isUpdating.current = true;
      onChange(editorRef.current.innerHTML);
      setTimeout(() => {
        isUpdating.current = false;
      }, 0);
    }
  };

  const handlePaste = async (e) => {
    e.preventDefault();
    
    const clipboardData = e.clipboardData || window.clipboardData;
    const items = clipboardData.items;

    // Check for images first
    let hasImage = false;
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      
      if (item.type.indexOf('image') !== -1) {
        hasImage = true;
        const blob = item.getAsFile();
        
        // Convert blob to base64 data URL
        const reader = new FileReader();
        reader.onload = function(event) {
          const base64 = event.target.result;
          
          // Insert image at cursor position
          const img = document.createElement('img');
          img.src = base64;
          img.style.maxWidth = '100%';
          img.style.height = 'auto';
          img.className = 'pasted-image';
          
          // Insert at cursor or at end
          const selection = window.getSelection();
          if (selection.rangeCount > 0) {
            const range = selection.getRangeAt(0);
            range.deleteContents();
            range.insertNode(img);
            
            // Move cursor after image
            range.setStartAfter(img);
            range.setEndAfter(img);
            selection.removeAllRanges();
            selection.addRange(range);
          } else {
            editorRef.current.appendChild(img);
          }
          
          handleInput();
        };
        reader.readAsDataURL(blob);
      }
    }

    // If no images, handle text paste
    if (!hasImage) {
      const text = clipboardData.getData('text/plain');
      
      // Insert text at cursor
      const selection = window.getSelection();
      if (selection.rangeCount > 0) {
        const range = selection.getRangeAt(0);
        range.deleteContents();
        const textNode = document.createTextNode(text);
        range.insertNode(textNode);
        
        // Move cursor after text
        range.setStartAfter(textNode);
        range.setEndAfter(textNode);
        selection.removeAllRanges();
        selection.addRange(range);
      }
      
      handleInput();
    }
  };

  const handleKeyDown = (e) => {
    // Allow basic keyboard shortcuts
    if (e.key === 'Enter' && !e.shiftKey) {
      // Don't prevent - allow line breaks
    }
  };

  return (
    <div className="rich-text-editor-container">
      <div
        ref={editorRef}
        className="rich-text-editor"
        contentEditable={true}
        onInput={handleInput}
        onPaste={handlePaste}
        onKeyDown={handleKeyDown}
        data-placeholder={placeholder}
        suppressContentEditableWarning={true}
      />
    </div>
  );
};

export default RichTextEditor;

