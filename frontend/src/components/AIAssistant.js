import React, { useState, useRef, useEffect, useContext } from 'react';
import { Button } from './ui/button';
import { Card, CardContent } from './ui/card';
import { Input } from './ui/input';
import { X, MessageCircle, Send, Loader2, ShieldCheck, CreditCard, Package, HelpCircle, Mail } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

const AIAssistant = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    { 
      role: 'assistant', 
      content: 'Welcome to BidVex! I am your Master Concierge, here to provide exceptional service. How may I assist you today?',
      rich_content: null
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const { token } = useContext(AuthContext);
  const navigate = useNavigate();
  const backendUrl = import.meta.env.REACT_APP_BACKEND_URL || process.env.REACT_APP_BACKEND_URL;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    
    const userMessage = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage, rich_content: null }]);
    setIsLoading(true);

    try {
      const headers = {
        'Content-Type': 'application/json'
      };
      
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${backendUrl}/api/ai-chat/message`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          message: userMessage,
          language: 'en',
          chat_history: messages.slice(-10).map(m => ({
            role: m.role,
            content: m.content
          }))
        })
      });

      const data = await response.json();

      if (data.success) {
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: data.message,
          rich_content: data.rich_content
        }]);
      } else {
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: data.message || 'I apologize, but I encountered an error. Please try again.',
          rich_content: null
        }]);
      }
    } catch (error) {
      console.error('AI chat error:', error);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: 'I apologize, but I\'m experiencing technical difficulties. Please try again or contact support@bidvex.com.',
        rich_content: null
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleActionButton = (action, url) => {
    if (url && url.startsWith('http')) {
      window.location.href = url;
    } else if (url) {
      setIsOpen(false);
      navigate(url);
    }
  };

  const getActionIcon = (icon) => {
    const iconProps = { className: "h-4 w-4 mr-2" };
    switch (icon) {
      case 'shield-check': return <ShieldCheck {...iconProps} />;
      case 'credit-card': return <CreditCard {...iconProps} />;
      case 'package': return <Package {...iconProps} />;
      case 'help-circle': return <HelpCircle {...iconProps} />;
      case 'mail': return <Mail {...iconProps} />;
      default: return null;
    }
  };

  return (
    <>
      {!isOpen && (
        <Button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 rounded-full w-14 h-14 bg-gradient-to-br from-[#1E3A8A] to-[#06B6D4] hover:from-[#1E3A8A]/90 hover:to-[#06B6D4]/90 text-white border-0 shadow-lg z-50 transition-all hover:scale-110"
          data-testid="ai-assistant-btn"
        >
          <MessageCircle className="h-6 w-6" />
        </Button>
      )}

      {isOpen && (
        <>
          {/* Mobile Bottom Sheet */}
          <div className="md:hidden fixed inset-0 bg-black/50 z-50 backdrop-blur-sm" onClick={() => setIsOpen(false)} />
          
          <Card className="fixed bottom-0 md:bottom-6 md:right-6 left-0 right-0 md:left-auto md:w-96 h-[70vh] md:h-[600px] shadow-2xl z-50 flex flex-col rounded-t-3xl md:rounded-3xl border-0">
            {/* Header with BidVex branding */}
            <div className="p-4 border-b flex justify-between items-center bg-gradient-to-br from-[#1E3A8A] to-[#06B6D4] text-white rounded-t-3xl md:rounded-t-3xl">
              <div>
                <h3 className="font-bold text-lg">BidVex Master Concierge</h3>
                <p className="text-xs text-white/80">Your Luxury Auction Specialist</p>
              </div>
              <Button variant="ghost" size="icon" onClick={() => setIsOpen(false)} className="text-white hover:bg-white/20 rounded-full">
                <X className="h-5 w-5" />
              </Button>
            </div>
            
            {/* Messages */}
            <CardContent className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50 dark:bg-gray-900">
              {messages.map((msg, idx) => (
                <div key={idx}>
                  <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] rounded-2xl p-3 ${
                      msg.role === 'user' 
                        ? 'bg-gradient-to-br from-[#1E3A8A] to-[#06B6D4] text-white shadow-md' 
                        : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 shadow-sm border border-gray-200 dark:border-gray-700'
                    }`}>
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                  
                  {/* Rich Content - Action Buttons */}
                  {msg.rich_content && msg.rich_content.has_rich_content && msg.rich_content.action_buttons && msg.rich_content.action_buttons.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2 justify-start ml-2">
                      {msg.rich_content.action_buttons.map((btn, btnIdx) => (
                        <Button
                          key={btnIdx}
                          onClick={() => handleActionButton(btn.action, btn.url)}
                          variant={btn.style === 'primary' ? 'default' : 'outline'}
                          size="sm"
                          className={btn.style === 'primary' 
                            ? 'bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] hover:from-[#1E3A8A]/90 hover:to-[#06B6D4]/90 text-white border-0 shadow-md'
                            : 'border-[#06B6D4] text-[#1E3A8A] hover:bg-[#06B6D4]/10'
                          }
                        >
                          {getActionIcon(btn.icon)}
                          {btn.text}
                        </Button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              
              {/* Loading indicator */}
              {isLoading && (
                <div className="flex justify-start">
                  <div className="bg-white dark:bg-gray-800 rounded-2xl p-3 shadow-sm border border-gray-200 dark:border-gray-700">
                    <Loader2 className="h-5 w-5 animate-spin text-[#06B6D4]" />
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </CardContent>
            
            {/* Input */}
            <div className="p-4 border-t bg-white dark:bg-gray-800">
              <div className="flex gap-2">
                <Input
                  placeholder="Ask me anything about BidVex..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                  disabled={isLoading}
                  className="flex-1 border-gray-300 focus:border-[#06B6D4] focus:ring-[#06B6D4]"
                />
                <Button 
                  onClick={handleSend} 
                  disabled={isLoading || !input.trim()}
                  className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] hover:from-[#1E3A8A]/90 hover:to-[#06B6D4]/90 text-white border-0 px-4"
                >
                  {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                </Button>
              </div>
              <p className="text-xs text-gray-500 mt-2 text-center">
                Powered by GPT-4 • Available 24/7
              </p>
            </div>
          </Card>
        </>
      )}
    </>
  );
};

export default AIAssistant;
