import React, { useState, useRef, useEffect } from 'react';
import { FiSend, FiX, FiMessageSquare, FiExternalLink } from 'react-icons/fi';
import api from '../services/api';
import './EnergyBot.css';
import { useAuth } from '../context/AuthContext';

/**
 * Parses bot message text and converts:
 *  1. Markdown links  [text](url)  → clickable <a> tags
 *  2. Bare URLs  https://... or http://...  → clickable <a> tags
 *  3. **bold** → <strong>
 * Returns an array of React elements.
 */
const renderMessageContent = (text) => {
  if (!text) return text;

  // Combined regex:  markdown links  |  bare URLs  |  **bold**
  const combinedRegex = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|(https?:\/\/[^\s<>)\]]+)|(\*\*(.+?)\*\*)/g;

  const parts = [];
  let lastIndex = 0;
  let match;

  while ((match = combinedRegex.exec(text)) !== null) {
    // Push plain text before the match
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    if (match[1] && match[2]) {
      // Markdown link: [text](url)
      parts.push(
        <a
          key={`link-${match.index}`}
          href={match[2]}
          target="_blank"
          rel="noopener noreferrer"
          className="bot-link"
        >
          {match[1]} <FiExternalLink size={12} style={{ marginLeft: 2, verticalAlign: 'middle' }} />
        </a>
      );
    } else if (match[3] && !match[4]) {
      // Bare URL
      const url = match[3].replace(/[.,;:!?]+$/, ''); // strip trailing punctuation
      parts.push(
        <a
          key={`url-${match.index}`}
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="bot-link"
        >
          {url} <FiExternalLink size={12} style={{ marginLeft: 2, verticalAlign: 'middle' }} />
        </a>
      );
      // If we stripped punctuation, add it back as plain text
      const stripped = match[3].slice(url.length);
      if (stripped) parts.push(stripped);
    } else if (match[4]) {
      // **bold**
      parts.push(<strong key={`b-${match.index}`}>{match[5]}</strong>);
    }

    lastIndex = match.index + match[0].length;
  }

  // Push remaining text
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
};

const EnergyBot = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    { role: 'bot', content: 'Hi there! How can I be of help to you?' }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);
  const { user } = useAuth();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const handleSend = async (e) => {
    e?.preventDefault();
    if (!input.trim()) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsTyping(true);

    try {
      const res = await api.post('/chat', {
        message: userMessage,
        history: messages.slice(1) // exclude initial greeting for history
      });

      setMessages(prev => [...prev, { role: 'bot', content: res.data.reply }]);
    } catch (err) {
      console.error('Chat error:', err);
      setMessages(prev => [...prev, { role: 'bot', content: "Sorry, I'm having trouble connecting right now." }]);
    } finally {
      setIsTyping(true);
      setTimeout(() => setIsTyping(false), 500); // Small delay for visual effect
    }
  };

  const handleChipClick = (text) => {
    setInput(text);
  };

  if (!user) return null; // Only show when logged in

  return (
    <div className="energybot-container">
      {!isOpen && (
        <div className="energybot-trigger" onClick={() => setIsOpen(true)}>
          <div className="trigger-bubble">
            Hi there! How can I be of help to you?
          </div>
          <div className="trigger-icon">
            <FiMessageSquare size={24} color="#fff" />
          </div>
        </div>
      )}

      {isOpen && (
        <div className="energybot-panel">
          <button className="close-btn standalone" onClick={() => setIsOpen(false)}>
            <FiX size={20} />
          </button>

          <div className="energybot-body">
            {messages.map((msg, idx) => (
              <div key={idx} className={`chat-bubble ${msg.role}`}>
                {msg.role === 'bot' && (
                  <div className="bot-avatar">⚡</div>
                )}
                <div className="bubble-content">
                  {msg.role === 'bot' ? renderMessageContent(msg.content) : msg.content}
                </div>
              </div>
            ))}

            {messages.length === 1 && (
              <div className="suggestion-chips">
                <button onClick={() => handleChipClick("Why is my bill high?")}>Why is my bill high?</button>
                <button onClick={() => handleChipClick("How to save ₹500 this month?")}>How to save ₹500?</button>
                <button onClick={() => handleChipClick("Which appliance uses most power?")}>Which app uses most power?</button>
              </div>
            )}

            {isTyping && (
              <div className="chat-bubble bot typing">
                <div className="bot-avatar">⚡</div>
                <div className="bubble-content typing-dots">
                  <span></span><span></span><span></span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <form className="energybot-footer" onSubmit={handleSend}>
            <input
              type="text"
              placeholder="Ask..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isTyping}
            />
            <button type="submit" disabled={isTyping || !input.trim()}>
              <FiSend size={18} />
            </button>
          </form>
        </div>
      )}
    </div>
  );
};

export default EnergyBot;
