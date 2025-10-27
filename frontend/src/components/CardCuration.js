import React, { useState } from 'react';
import axios from 'axios';
import { useLanguage } from '../i18n/LanguageContext';
import SearchableDropdown from './SearchableDropdown';
import RichTextEditor from './RichTextEditor';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const CardCuration = ({ cards, onApproveCard, onRefresh }) => {
  const { t } = useLanguage();
  const [selectedCards, setSelectedCards] = useState([]);
  const [ankiProfiles, setAnkiProfiles] = useState([]);
  const [selectedDeck, setSelectedDeck] = useState(() => {
    // Load last selected deck from localStorage
    return localStorage.getItem('lastSelectedDeck') || '';
  });
  const [availableDecks, setAvailableDecks] = useState([]);
  const [editingCard, setEditingCard] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [currentPage, setCurrentPage] = useState(1);
  const [cardsPerPage] = useState(10);

  React.useEffect(() => {
    loadAnkiProfiles();
    loadAvailableDecks();
  }, []);

  const loadAnkiProfiles = async () => {
    try {
      const response = await axios.get(`${API_BASE}/anki-profiles`);
      console.log('Loaded Anki profiles:', response.data);
      setAnkiProfiles(response.data);
      
      // If no profiles exist, create a default one
      if (response.data.length === 0) {
        console.log('No Anki profiles found, creating default...');
        await createDefaultProfile();
      }
    } catch (error) {
      console.error('Error loading Anki profiles:', error);
    }
  };

  const loadAvailableDecks = async () => {
    try {
      const response = await axios.get(`${API_BASE}/anki/decks`);
      console.log('Loaded Anki decks:', response.data.decks);
      setAvailableDecks(response.data.decks || []);
    } catch (error) {
      console.error('Error loading Anki decks:', error);
      // If AnkiConnect is not available, just use empty array
      setAvailableDecks([]);
    }
  };

  const createDefaultProfile = async () => {
    try {
      const defaultProfile = {
        name: 'Default',
        deck_name: 'SRS4Autism',
        is_active: true
      };
      await axios.post(`${API_BASE}/anki-profiles`, defaultProfile);
      const response = await axios.get(`${API_BASE}/anki-profiles`);
      setAnkiProfiles(response.data);
      setSelectedDeck('SRS4Autism');
    } catch (error) {
      console.error('Error creating default profile:', error);
    }
  };

  const handleCardSelect = (cardId) => {
    setSelectedCards(prev => 
      prev.includes(cardId) 
        ? prev.filter(id => id !== cardId)
        : [...prev, cardId]
    );
  };

  const handleSelectAll = () => {
    const pendingCards = cards.filter(card => card.status === 'pending');
    setSelectedCards(pendingCards.map(card => card.id));
  };

  const handleDeselectAll = () => {
    setSelectedCards([]);
  };

  const handleApproveSelected = async () => {
    for (const cardId of selectedCards) {
      await onApproveCard(cardId);
    }
    setSelectedCards([]);
  };

  const handleDeleteCard = async (cardId) => {
    if (!window.confirm('Are you sure you want to delete this card?')) {
      return;
    }
    
    try {
      await axios.delete(`${API_BASE}/cards/${cardId}`);
      onRefresh();
    } catch (error) {
      console.error('Error deleting card:', error);
      alert('Failed to delete card');
    }
  };

  const handleDeleteSelected = async () => {
    if (!window.confirm(`Are you sure you want to delete ${selectedCards.length} card(s)?`)) {
      return;
    }
    
    try {
      for (const cardId of selectedCards) {
        await axios.delete(`${API_BASE}/cards/${cardId}`);
      }
      setSelectedCards([]);
      onRefresh();
    } catch (error) {
      console.error('Error deleting cards:', error);
      alert('Failed to delete some cards');
    }
  };

  const handleEditCard = (card) => {
    setEditingCard(card.id);
    setEditForm({ ...card });
  };

  const handleEditFieldChange = (field, value) => {
    setEditForm(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSaveEdit = async () => {
    try {
      // Update card in backend
      await axios.put(`${API_BASE}/cards/${editingCard}`, editForm);
      setEditingCard(null);
      setEditForm({});
      onRefresh();
    } catch (error) {
      console.error('Error saving card:', error);
      alert('Failed to save card changes');
    }
  };

  const handleCancelEdit = () => {
    setEditingCard(null);
    setEditForm({});
  };

  const handleSyncToAnki = async (forceResync = false) => {
    console.log('🔵 Sync to Anki clicked! Force resync:', forceResync);
    console.log('Selected deck:', selectedDeck, 'Type:', typeof selectedDeck, 'Truthy?:', !!selectedDeck);
    console.log('Selected cards:', selectedCards);
    console.log('All cards:', cards);
    console.log('Button should be disabled?', selectedCards.length === 0 || !selectedDeck);
    
    if (!selectedDeck) {
      console.log('❌ No deck selected');
      alert(t('pleaseSelectAnkiProfile'));
      return;
    }

    // If forceResync, allow synced cards, otherwise only approved
    const cardsToSync = cards.filter(card => {
      if (!selectedCards.includes(card.id)) return false;
      if (forceResync) return true; // Allow any selected card
      return card.status === 'approved'; // Only approved cards
    });

    console.log('Cards to sync:', cardsToSync);

    if (cardsToSync.length === 0) {
      console.log('❌ No cards selected for sync');
      alert(forceResync ? 'Please select cards to re-sync' : t('pleaseSelectApprovedCards'));
      return;
    }

    const deckName = selectedDeck;
    console.log('Deck name:', deckName);

    try {
      const response = await axios.post(`${API_BASE}/anki/sync`, {
        deck_name: deckName,
        card_ids: cardsToSync.map(c => c.id)
      });

      alert(`✅ Success!\n${response.data.message}\n\nCards have been added to Anki deck: ${deckName}`);
      
      // Refresh the cards to show updated status
      onRefresh();
      setSelectedCards([]);
    } catch (error) {
      console.error('Error syncing to Anki:', error);
      
      let errorMessage = 'Failed to sync cards to Anki';
      
      if (error.response?.status === 503) {
        errorMessage = '❌ Cannot connect to Anki!\n\nMake sure:\n1. Anki is running\n2. AnkiConnect add-on is installed\n3. AnkiConnect is enabled';
      } else if (error.response?.data?.detail) {
        errorMessage = `Error: ${error.response.data.detail}`;
      }
      
      alert(errorMessage);
    }
  };

  const renderCardPreview = (card) => {
    const isEditing = editingCard === card.id;
    const cardData = isEditing ? editForm : card;

    if (isEditing) {
      return renderEditForm(card);
    }

    switch (card.card_type) {
      case 'basic':
        return (
          <div className="card-preview">
            <h4>{t('basicCard')}</h4>
            <div className="front">
              <strong>{t('front')}:</strong> 
              <div dangerouslySetInnerHTML={{__html: card.front}} />
            </div>
            <div className="back">
              <strong>{t('back')}:</strong> 
              <div dangerouslySetInnerHTML={{__html: card.back}} />
            </div>
          </div>
        );
      case 'basic_reverse':
        return (
          <div className="card-preview">
            <h4>{t('basicReverseCard')}</h4>
            <div className="front">
              <strong>{t('front')}:</strong> 
              <div dangerouslySetInnerHTML={{__html: card.front}} />
            </div>
            <div className="back">
              <strong>{t('back')}:</strong> 
              <div dangerouslySetInnerHTML={{__html: card.back}} />
            </div>
            <div className="note">{t('worksBoothWays')}</div>
          </div>
        );
      case 'interactive_cloze':
        return (
          <div className="card-preview">
            <h4>Interactive Cloze Card</h4>
            <div 
              className="cloze-text" 
              dangerouslySetInnerHTML={{__html: card.text_field || card.cloze_text}}
            />
            {card.extra_field && (
              <div className="extra-info">
                <strong>Extra:</strong> 
                <div dangerouslySetInnerHTML={{__html: card.extra_field}} />
              </div>
            )}
            <div className="note">Click blanks to reveal (uses [[c1::answer]] syntax)</div>
          </div>
        );
      case 'cloze':
        return (
          <div className="card-preview">
            <h4>{t('clozeCard')}</h4>
            <div className="cloze-text">{card.cloze_text}</div>
            <div className="note">{t('missingWordHidden')}</div>
          </div>
        );
      default:
        return <div>Unknown card type: {card.card_type}</div>;
    }
  };

  const renderEditForm = (card) => {
    return (
      <div className="card-edit-form">
        <h4>Editing {card.card_type} card</h4>
        
        {card.card_type === 'interactive_cloze' ? (
          <>
            <div className="form-group">
              <label>Text (with [[c1::answer]] syntax - paste images supported):</label>
              <RichTextEditor
                value={editForm.text_field || ''}
                onChange={(value) => handleEditFieldChange('text_field', value)}
                placeholder="Type or paste content with [[c1::cloze]] syntax. You can paste images!"
              />
            </div>
            <div className="form-group">
              <label>Extra Info (optional - paste images supported):</label>
              <RichTextEditor
                value={editForm.extra_field || ''}
                onChange={(value) => handleEditFieldChange('extra_field', value)}
                placeholder="Additional context or hints. You can paste images!"
              />
            </div>
          </>
        ) : (
          <>
            <div className="form-group">
              <label>Front (paste images supported):</label>
              <RichTextEditor
                value={editForm.front || ''}
                onChange={(value) => handleEditFieldChange('front', value)}
                placeholder="Question or prompt. You can paste images!"
              />
            </div>
            <div className="form-group">
              <label>Back (paste images supported):</label>
              <RichTextEditor
                value={editForm.back || ''}
                onChange={(value) => handleEditFieldChange('back', value)}
                placeholder="Answer. You can paste images!"
              />
            </div>
          </>
        )}
        
        <div className="form-group">
          <label>Tags (comma-separated):</label>
          <input
            type="text"
            value={(editForm.tags || []).join(', ')}
            onChange={(e) => {
              const tags = e.target.value.split(',').map(t => t.trim()).filter(t => t);
              handleEditFieldChange('tags', tags);
            }}
          />
        </div>
        
        <div className="edit-actions">
          <button onClick={handleSaveEdit} className="btn btn-success">
            Save Changes
          </button>
          <button onClick={handleCancelEdit} className="btn btn-secondary">
            Cancel
          </button>
        </div>
      </div>
    );
  };

  const getStatusBadge = (status) => {
    const statusClasses = {
      pending: 'status-pending',
      approved: 'status-approved',
      synced: 'status-synced'
    };
    const statusText = {
      pending: t('pending'),
      approved: t('approved'),
      synced: t('synced')
    };
    return (
      <span className={`status-badge ${statusClasses[status]}`}>
        {statusText[status] || status.toUpperCase()}
      </span>
    );
  };

  // Sort cards by created_at descending (latest first)
  const sortedCards = [...cards].sort((a, b) => {
    const dateA = new Date(a.created_at);
    const dateB = new Date(b.created_at);
    return dateB - dateA;
  });
  
  const pendingCards = sortedCards.filter(card => card.status === 'pending');
  const approvedCards = sortedCards.filter(card => card.status === 'approved');
  const syncedCards = sortedCards.filter(card => card.status === 'synced');
  
  // Pagination for pending cards
  const indexOfLastCard = currentPage * cardsPerPage;
  const indexOfFirstCard = indexOfLastCard - cardsPerPage;
  const currentPendingCards = pendingCards.slice(indexOfFirstCard, indexOfLastCard);
  const totalPages = Math.ceil(pendingCards.length / cardsPerPage);
  
  // Check if sync button should be enabled
  const canSync = selectedCards.length > 0 && selectedDeck;
  const hasApprovedSelected = cards.filter(card => 
    selectedCards.includes(card.id) && card.status === 'approved'
  ).length > 0;

  return (
    <div className="card">
      <h2>{t('curationTitle')}</h2>
      <p>{t('curationDescription')}</p>

      {/* Global Settings */}
      <div className="card">
        <h3>{t('globalSettings')}</h3>
        <div className="form-group">
          <SearchableDropdown
            label={`${t('ankiProfile')}:`}
            options={availableDecks}
            value={selectedDeck}
            onChange={(value) => {
              console.log('✅ Deck selected:', value);
              setSelectedDeck(value);
              // Save to localStorage for next time
              localStorage.setItem('lastSelectedDeck', value);
            }}
            placeholder={!selectedDeck ? "⚠️ " + t('selectAnkiProfile') : t('selectAnkiProfile')}
            onRefresh={loadAvailableDecks}
          />
          <small style={{color: '#666', fontSize: '12px', marginTop: '5px', display: 'block'}}>
            {availableDecks.length > 0 
              ? `${availableDecks.length} decks available from Anki`
              : 'Type to create new deck or click ↻ to refresh'}
            {selectedDeck && (
              <span style={{marginLeft: '10px', color: '#28a745', fontWeight: 'bold'}}>
                ✓ Last used: {selectedDeck}
              </span>
            )}
          </small>
        </div>
      </div>

      {/* Selection Controls */}
      <div className="card">
        <h3>{t('selectionControls')}</h3>
        <div className="selection-controls">
          <button onClick={handleSelectAll} className="btn btn-secondary">
            {t('selectAllPending')}
          </button>
          <button onClick={handleDeselectAll} className="btn btn-secondary">
            {t('deselectAll')}
          </button>
          <button 
            onClick={handleApproveSelected} 
            className="btn btn-success"
            disabled={selectedCards.length === 0}
          >
            {t('approveSelected')} ({selectedCards.length})
          </button>
          <button 
            onClick={handleDeleteSelected} 
            className="btn btn-danger"
            disabled={selectedCards.length === 0}
          >
            {t('deleteSelected')} ({selectedCards.length})
          </button>
          <button 
            onClick={() => handleSyncToAnki(false)} 
            className="btn"
            disabled={selectedCards.length === 0 || !selectedDeck}
            title={
              !selectedDeck 
                ? t('pleaseSelectAnkiProfile')
                : selectedCards.length === 0 
                  ? t('pleaseSelectApprovedCards')
                  : !hasApprovedSelected
                    ? "Only approved cards can be synced"
                    : t('syncToAnki')
            }
          >
            {t('syncToAnki')}
          </button>
          
          <button 
            onClick={() => handleSyncToAnki(true)} 
            className="btn btn-secondary"
            disabled={selectedCards.length === 0 || !selectedDeck}
            title={
              !selectedDeck 
                ? 'Select a deck first'
                : selectedCards.length === 0 
                  ? 'Select cards to re-sync'
                  : 'Re-sync selected cards (approved or synced)'
            }
            style={{
              backgroundColor: '#6c757d',
              marginLeft: '10px'
            }}
          >
            🔄 Re-sync Selected
          </button>
        </div>
        
        {/* Status message */}
        {selectedCards.length > 0 && !hasApprovedSelected && (
          <div style={{marginTop: '10px', padding: '10px', background: '#fff3cd', borderRadius: '4px', color: '#856404'}}>
            {t('warningSelectApproved').replace('{count}', selectedCards.length)}
          </div>
        )}
        
        {!selectedDeck && (
          <div style={{marginTop: '10px', padding: '10px', background: '#d1ecf1', borderRadius: '4px', color: '#0c5460'}}>
            {t('infoSelectProfile')}
          </div>
        )}
      </div>

      {/* Pending Cards */}
      <div className="card">
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
          <h3>{t('pendingCards')} ({pendingCards.length})</h3>
          {totalPages > 1 && (
            <div className="pagination">
              <button 
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                disabled={currentPage === 1}
                className="btn btn-secondary"
              >
                ← Prev
              </button>
              <span style={{margin: '0 15px'}}>
                Page {currentPage} of {totalPages}
              </span>
              <button 
                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                disabled={currentPage === totalPages}
                className="btn btn-secondary"
              >
                Next →
              </button>
            </div>
          )}
        </div>
        {pendingCards.length === 0 ? (
          <p>{t('noPendingCards')}</p>
        ) : (
          <div className="cards-list">
            {currentPendingCards.map(card => (
              <div key={card.id} className="card-item">
                <div className="card-header">
                  <input
                    type="checkbox"
                    checked={selectedCards.includes(card.id)}
                    onChange={() => handleCardSelect(card.id)}
                  />
                  <span className="card-id">#{card.id.slice(-6)}</span>
                  {getStatusBadge(card.status)}
                  <span className="card-tags">
                    {card.tags.map(tag => (
                      <span key={tag} className="tag">#{tag}</span>
                    ))}
                  </span>
                </div>
                {renderCardPreview(card)}
                {editingCard !== card.id && (
                  <div className="card-actions">
                    <button 
                      onClick={() => handleEditCard(card)}
                      className="btn btn-secondary"
                    >
                      {t('edit')}
                    </button>
                    <button 
                      onClick={() => onApproveCard(card.id)}
                      className="btn btn-success"
                    >
                      {t('approve')}
                    </button>
                    <button 
                      onClick={() => handleDeleteCard(card.id)}
                      className="btn btn-danger"
                    >
                      {t('delete')}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Approved Cards */}
      <div className="card">
        <h3>{t('approvedCards')} ({approvedCards.length})</h3>
        {approvedCards.length === 0 ? (
          <p>{t('noApprovedCards')}</p>
        ) : (
          <div className="cards-list">
            {approvedCards.map(card => (
              <div key={card.id} className="card-item">
                <div className="card-header">
                  <input
                    type="checkbox"
                    checked={selectedCards.includes(card.id)}
                    onChange={() => handleCardSelect(card.id)}
                  />
                  <span className="card-id">#{card.id.slice(-6)}</span>
                  {getStatusBadge(card.status)}
                  <span className="card-tags">
                    {card.tags.map(tag => (
                      <span key={tag} className="tag">#{tag}</span>
                    ))}
                  </span>
                </div>
                {renderCardPreview(card)}
                <div className="card-actions">
                  <button 
                    onClick={() => handleDeleteCard(card.id)}
                    className="btn btn-danger"
                  >
                    {t('delete')}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Synced Cards */}
      {syncedCards.length > 0 && (
        <div className="card">
          <h3>✅ {t('syncedCards')} ({syncedCards.length})</h3>
          <p>{t('syncedSuccessfully')}</p>
          
          {/* Selection controls for synced cards */}
          <div style={{marginBottom: '15px', display: 'flex', gap: '10px', alignItems: 'center'}}>
            <button 
              onClick={() => {
                const allSyncedIds = syncedCards.map(c => c.id);
                const allSelected = allSyncedIds.every(id => selectedCards.includes(id));
                if (allSelected) {
                  // Deselect all synced cards
                  setSelectedCards(selectedCards.filter(id => !allSyncedIds.includes(id)));
                } else {
                  // Select all synced cards
                  setSelectedCards([...new Set([...selectedCards, ...allSyncedIds])]);
                }
              }}
              className="btn btn-secondary"
              style={{fontSize: '14px', padding: '5px 10px'}}
            >
              {syncedCards.every(c => selectedCards.includes(c.id)) ? '☑️ Deselect All' : '☐ Select All'}
            </button>
            <span style={{fontSize: '14px', color: '#666'}}>
              {selectedCards.filter(id => syncedCards.find(c => c.id === id)).length} of {syncedCards.length} selected
            </span>
          </div>
          
          <div className="cards-list">
            {syncedCards.map(card => (
              <div key={card.id} className="card-item">
                <div className="card-header">
                  <input
                    type="checkbox"
                    checked={selectedCards.includes(card.id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedCards([...selectedCards, card.id]);
                      } else {
                        setSelectedCards(selectedCards.filter(id => id !== card.id));
                      }
                    }}
                    style={{marginRight: '10px', transform: 'scale(1.2)'}}
                  />
                  <span className="card-id">#{card.id.slice(-6)}</span>
                  {getStatusBadge(card.status)}
                  <span className="card-tags">
                    {card.tags.map(tag => (
                      <span key={tag} className="tag">#{tag}</span>
                    ))}
                  </span>
                </div>
                {renderCardPreview(card)}
                <div className="card-actions">
                  <button 
                    onClick={() => handleDeleteCard(card.id)}
                    className="btn btn-danger"
                  >
                    {t('delete')}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default CardCuration;

