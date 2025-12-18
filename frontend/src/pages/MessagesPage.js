import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useSearchParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card } from '../components/ui/card';
import { ScrollArea } from '../components/ui/scroll-area';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { Send, User, Search, Wifi, WifiOff, Check, CheckCheck, Loader2, Package, ExternalLink } from 'lucide-react';
import { useRealtimeMessaging } from '../hooks/useRealtimeMessaging';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Connection status indicator component
const ConnectionStatus = ({ connectionHealth }) => (
  <div className={`flex items-center gap-1 text-xs ${
    connectionHealth === 'healthy' ? 'text-green-500' :
    connectionHealth === 'connecting' ? 'text-yellow-500' :
    'text-red-500'
  }`}>
    {connectionHealth === 'healthy' ? (
      <><Wifi className="h-3 w-3" /> Live</>
    ) : connectionHealth === 'connecting' ? (
      <><Loader2 className="h-3 w-3 animate-spin" /> Connecting</>
    ) : (
      <><WifiOff className="h-3 w-3" /> Offline</>
    )}
  </div>
);

// Reference Card for listing context
const ListingReferenceCard = ({ info, navigate }) => {
  if (!info) return null;
  
  return (
    <div 
      className="mx-4 mt-2 p-3 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30 rounded-lg border border-blue-200 dark:border-blue-800 cursor-pointer hover:shadow-md transition-shadow"
      onClick={() => navigate(`/auction/${info.id}`)}
    >
      <div className="flex items-center gap-3">
        {info.image ? (
          <img src={info.image} alt="" className="w-12 h-12 rounded-lg object-cover" />
        ) : (
          <div className="w-12 h-12 rounded-lg bg-gray-200 flex items-center justify-center">
            <Package className="h-6 w-6 text-gray-400" />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
            {info.title}
          </p>
          {info.price && (
            <p className="text-xs text-blue-600 dark:text-blue-400 font-semibold">
              Current: ${info.price.toFixed(2)}
            </p>
          )}
        </div>
        <ExternalLink className="h-4 w-4 text-gray-400" />
      </div>
    </div>
  );
};

const MessagesPage = () => {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [conversations, setConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [newMessage, setNewMessage] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const typingTimeoutRef = useRef(null);

  // Real-time messaging hook
  const {
    messages,
    isConnected,
    connectionHealth,
    otherUser,
    otherUserOnline,
    otherUserTyping,
    listingInfo,
    sendMessage: wsSendMessage,
    sendTypingStart,
    sendTypingStop,
    markAsRead,
    addLocalMessage,
    setInitialMessages
  } = useRealtimeMessaging(selectedConversation?.id);

  // Fetch conversations on mount
  useEffect(() => {
    if (user && token) {
      fetchConversations();
    }
  }, [user, token]);

  // Auto-select conversation when redirected from "Message Seller" button
  useEffect(() => {
    const handleAutoSelection = async () => {
      const sellerId = searchParams.get('seller');
      const listingId = searchParams.get('listing');
      
      if (!sellerId || !user || loading) return;
      
      const existingConvo = conversations.find(convo => 
        convo.participants && convo.participants.includes(sellerId)
      );
      
      if (existingConvo) {
        setSelectedConversation(existingConvo);
      } else if (!loading) {
        await startNewConversation(sellerId, listingId);
      }
    };
    
    handleAutoSelection();
  }, [conversations, loading, searchParams, user]);

  // Fetch messages when conversation is selected
  useEffect(() => {
    if (selectedConversation) {
      fetchMessages(selectedConversation.id);
    }
  }, [selectedConversation]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Mark messages as read when viewing
  useEffect(() => {
    if (messages.length > 0 && isConnected) {
      const unreadIds = messages
        .filter(m => m.receiver_id === user?.id && !m.is_read)
        .map(m => m.id);
      if (unreadIds.length > 0) {
        markAsRead(unreadIds);
      }
    }
  }, [messages, isConnected, user?.id, markAsRead]);

  const fetchConversations = async () => {
    try {
      const response = await axios.get(`${API}/conversations`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setConversations(response.data);
    } catch (error) {
      console.error('Failed to fetch conversations:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchMessages = async (conversationId) => {
    try {
      const response = await axios.get(`${API}/messages/${conversationId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setInitialMessages(response.data);
    } catch (error) {
      console.error('Failed to fetch messages:', error);
      toast.error('Failed to load messages');
    }
  };

  const startNewConversation = async (sellerId, listingId) => {
    try {
      await axios.post(`${API}/messages`, {
        receiver_id: sellerId,
        content: `Hi, I'm interested in your listing.`,
        listing_id: listingId
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      await fetchConversations();
      
      const newConvo = conversations.find(convo => 
        convo.participants && convo.participants.includes(sellerId)
      );
      
      if (newConvo) {
        setSelectedConversation(newConvo);
        toast.success('Conversation started!');
      }
    } catch (error) {
      console.error('Failed to start conversation:', error);
      toast.error(error.response?.data?.detail || 'Failed to start conversation');
    }
  };

  const sendMessage = async () => {
    if (!newMessage.trim() || !selectedConversation || sending) return;

    const messageContent = newMessage.trim();
    setNewMessage('');
    setSending(true);

    // Optimistic update - add message locally immediately
    const optimisticMessage = {
      id: `temp-${Date.now()}`,
      conversation_id: selectedConversation.id,
      sender_id: user.id,
      receiver_id: selectedConversation.participants.find(p => p !== user.id),
      content: messageContent,
      created_at: new Date().toISOString(),
      is_read: false,
      _pending: true
    };
    addLocalMessage(optimisticMessage);

    // Try WebSocket first for instant delivery
    if (isConnected) {
      const sent = wsSendMessage(messageContent);
      if (sent) {
        setSending(false);
        sendTypingStop();
        return;
      }
    }

    // Fallback to REST API
    try {
      const receiverId = selectedConversation.participants.find(p => p !== user.id);
      await axios.post(`${API}/messages`, {
        receiver_id: receiverId,
        content: messageContent,
        listing_id: selectedConversation.listing_id || null
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      // Refresh to get the real message
      await fetchMessages(selectedConversation.id);
    } catch (error) {
      toast.error('Failed to send message');
      // Remove optimistic message on failure
      setInitialMessages(messages.filter(m => m.id !== optimisticMessage.id));
    } finally {
      setSending(false);
    }
  };

  const handleInputChange = (e) => {
    setNewMessage(e.target.value);
    
    // Send typing indicator
    if (e.target.value.length > 0) {
      sendTypingStart();
      
      // Clear previous timeout
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
      
      // Stop typing after 2 seconds of inactivity
      typingTimeoutRef.current = setTimeout(() => {
        sendTypingStop();
      }, 2000);
    } else {
      sendTypingStop();
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const filteredConversations = conversations.filter(convo =>
    convo.other_user?.name?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-64px)] flex" data-testid="messages-page">
      {/* Conversations List */}
      <div className="w-full md:w-1/3 border-r bg-white dark:bg-gray-900">
        <div className="p-4 border-b">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold">Messages</h2>
            <ConnectionStatus connectionHealth={connectionHealth} />
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search conversations..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
        </div>
        
        <ScrollArea className="h-[calc(100vh-200px)]">
          {filteredConversations.length > 0 ? (
            filteredConversations.map((convo) => (
              <div
                key={convo.id}
                onClick={() => setSelectedConversation(convo)}
                className={`p-4 border-b cursor-pointer hover:bg-accent/50 transition-colors ${
                  selectedConversation?.id === convo.id ? 'bg-accent' : ''
                }`}
                data-testid={`conversation-${convo.id}`}
              >
                <div className="flex items-start gap-3">
                  <div className="relative">
                    {convo.other_user?.picture ? (
                      <img src={convo.other_user.picture} alt="" className="w-12 h-12 rounded-full" />
                    ) : (
                      <div className="w-12 h-12 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center">
                        <User className="h-6 w-6 text-white" />
                      </div>
                    )}
                    {/* Online status dot */}
                    {selectedConversation?.id === convo.id && otherUserOnline && (
                      <span className="absolute bottom-0 right-0 w-3 h-3 bg-green-500 border-2 border-white rounded-full" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-start">
                      <p className="font-semibold truncate">{convo.other_user?.name}</p>
                      {convo.unread_count > 0 && (
                        <Badge className="bg-primary text-white text-xs">
                          {convo.unread_count}
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground truncate">{convo.last_message}</p>
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="p-8 text-center text-muted-foreground">
              No conversations yet
            </div>
          )}
        </ScrollArea>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {selectedConversation ? (
          <>
            {/* Chat Header */}
            <div className="p-4 border-b bg-white dark:bg-gray-900">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="relative">
                    {otherUser?.picture || selectedConversation.other_user?.picture ? (
                      <img 
                        src={otherUser?.picture || selectedConversation.other_user?.picture} 
                        alt="" 
                        className="w-10 h-10 rounded-full" 
                      />
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center">
                        <User className="h-5 w-5 text-white" />
                      </div>
                    )}
                    {/* Online status dot */}
                    {otherUserOnline && (
                      <span className="absolute bottom-0 right-0 w-3 h-3 bg-green-500 border-2 border-white rounded-full" />
                    )}
                  </div>
                  <div>
                    <p className="font-semibold">
                      {otherUser?.name || selectedConversation.other_user?.name}
                    </p>
                    <p className={`text-xs ${otherUserOnline ? 'text-green-500' : 'text-muted-foreground'}`}>
                      {otherUserTyping ? (
                        <span className="flex items-center gap-1">
                          <span className="flex gap-1">
                            <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                            <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                            <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                          </span>
                          typing...
                        </span>
                      ) : otherUserOnline ? (
                        'Online'
                      ) : (
                        'Offline'
                      )}
                    </p>
                  </div>
                </div>
                <ConnectionStatus />
              </div>
            </div>

            {/* Listing Reference Card */}
            <ListingReferenceCard info={listingInfo} />

            {/* Messages Area */}
            <ScrollArea className="flex-1 p-4">
              <div className="space-y-4">
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${msg.sender_id === user.id ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-200`}
                  >
                    <div
                      className={`max-w-[70%] rounded-lg p-3 ${
                        msg.sender_id === user.id
                          ? 'bg-gradient-to-br from-primary to-accent text-white'
                          : 'bg-gray-100 dark:bg-gray-800'
                      } ${msg._pending ? 'opacity-70' : ''}`}
                    >
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                      <div className="flex items-center justify-end gap-1 mt-1">
                        <p className="text-xs opacity-70">
                          {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </p>
                        {/* Read receipt indicator for sent messages */}
                        {msg.sender_id === user.id && (
                          msg._pending ? (
                            <Loader2 className="h-3 w-3 animate-spin opacity-70" />
                          ) : msg.is_read ? (
                            <CheckCheck className="h-3 w-3 text-blue-300" />
                          ) : (
                            <Check className="h-3 w-3 opacity-70" />
                          )
                        )}
                      </div>
                    </div>
                  </div>
                ))}
                
                {/* Typing indicator */}
                {otherUserTyping && (
                  <div className="flex justify-start animate-in fade-in">
                    <div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-3">
                      <div className="flex gap-1">
                        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                    </div>
                  </div>
                )}
                
                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>

            {/* Message Input */}
            <div className="p-4 border-t bg-white dark:bg-gray-900">
              <div className="flex gap-2">
                <Input
                  ref={inputRef}
                  placeholder="Type a message..."
                  value={newMessage}
                  onChange={handleInputChange}
                  onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                  data-testid="message-input"
                  disabled={sending}
                />
                <Button 
                  onClick={sendMessage} 
                  className="gradient-button text-white border-0" 
                  data-testid="send-message-btn"
                  disabled={!newMessage.trim() || sending}
                >
                  {sending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <div className="text-center">
              <User className="h-16 w-16 mx-auto mb-4 opacity-50" />
              <p>Select a conversation to start messaging</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MessagesPage;
