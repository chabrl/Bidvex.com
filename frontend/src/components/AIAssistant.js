import React, { useState } from 'react';
import { Button } from './ui/button';
import { Card, CardContent } from './ui/card';
import { Input } from './ui/input';
import { X, MessageCircle, Send } from 'lucide-react';

const AIAssistant = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hi! I am your BidVex AI assistant. How can I help you today?' }
  ]);
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (!input.trim()) return;
    
    setMessages([...messages, { role: 'user', content: input }]);
    
    setTimeout(() => {
      const response = getAIResponse(input);
      setMessages(prev => [...prev, { role: 'assistant', content: response }]);
    }, 500);
    
    setInput('');
  };

  const getAIResponse = (query) => {
    const lowerQuery = query.toLowerCase();
    if (lowerQuery.includes('listing') || lowerQuery.includes('create')) {
      return 'To create a listing, click "Sell" in the navigation menu. Fill in the item details, add images, set your starting price, and choose an auction end date.';
    } else if (lowerQuery.includes('bid')) {
      return 'To bid on an item, go to the listing page and enter your bid amount. Make sure your bid is higher than the current price. You need to be logged in to place bids.';
    } else if (lowerQuery.includes('payment')) {
      return 'Payments are processed securely through Stripe. You can add payment methods in your account settings. A buyer premium fee applies: 5% for personal accounts, 4.5% for business accounts.';
    } else if (lowerQuery.includes('account') || lowerQuery.includes('profile')) {
      return 'You can manage your account by clicking your profile icon and selecting "Settings". There you can update your profile, add payment methods, and manage notifications.';
    } else {
      return 'I am here to help! You can ask me about creating listings, placing bids, payments, or managing your account. For more detailed support, please contact our team.';
    }
  };

  return (
    <>
      {!isOpen && (
        <Button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 rounded-full w-14 h-14 gradient-button text-white border-0 shadow-lg z-50"
          data-testid="ai-assistant-btn"
        >
          <MessageCircle className="h-6 w-6" />
        </Button>
      )}

      {isOpen && (
        <Card className="fixed bottom-6 right-6 w-96 h-[500px] shadow-2xl z-50 flex flex-col">
          <div className="p-4 border-b flex justify-between items-center gradient-bg text-white">
            <h3 className="font-semibold">BidVex AI Assistant</h3>
            <Button variant="ghost" size="icon" onClick={() => setIsOpen(false)} className="text-white hover:bg-white/20">
              <X className="h-4 w-4" />
            </Button>
          </div>
          
          <CardContent className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[80%] rounded-lg p-3 ${
                  msg.role === 'user' 
                    ? 'bg-gradient-to-br from-primary to-accent text-white' 
                    : 'bg-gray-100 dark:bg-gray-800'
                }`}>
                  <p className="text-sm">{msg.content}</p>
                </div>
              </div>
            ))}
          </CardContent>
          
          <div className="p-4 border-t">
            <div className="flex gap-2">
              <Input
                placeholder="Ask me anything..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSend()}
              />
              <Button onClick={handleSend} className="gradient-button text-white border-0">
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </Card>
      )}
    </>
  );
};

export default AIAssistant;
