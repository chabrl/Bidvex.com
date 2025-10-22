import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card } from '../components/ui/card';
import { ScrollArea } from '../components/ui/scroll-area';
import { Avatar } from '../components/ui/avatar';
import { toast } from 'sonner';
import { Send, User, Search } from 'lucide-react';
import io from 'socket.io-client';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const WS_URL = process.env.REACT_APP_BACKEND_URL.replace('/api', '').replace('https://', 'wss://').replace('http://', 'ws://');

const MessagesPage = () => {
  const { user, token } = useAuth();
  const [searchParams] = useSearchParams();
  const [conversations, setConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);

  useEffect(() => {
    if (user && token) {
      fetchConversations();
      connectWebSocket();
    }
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [user, token]);

  // Auto-select conversation when redirected from "Message Seller" button
  useEffect(() => {
    const handleAutoSelection = async () => {
      const sellerId = searchParams.get('seller');
      const listingId = searchParams.get('listing');
      
      if (sellerId && user && !loading) {
        console.log('Auto-selecting conversation with seller:', sellerId);
        
        // Wait for conversations to load
        if (conversations.length === 0) {
          return; // Wait for conversations to load first
        }
        
        // Find existing conversation with this seller
        const existingConvo = conversations.find(convo => 
          convo.participants && convo.participants.includes(sellerId)
        );
        
        if (existingConvo) {
          console.log('Found existing conversation:', existingConvo.id);
          setSelectedConversation(existingConvo);
        } else {
          // Create new conversation if it doesn't exist
          console.log('Creating new conversation with seller:', sellerId);
          await startNewConversation(sellerId, listingId);
        }
      }
    };
    
    handleAutoSelection();
  }, [conversations, searchParams, user, loading]);

  const startNewConversation = async (sellerId, listingId) => {
    try {
      // Send an initial message to create the conversation
      await axios.post(`${API}/messages`, {
        receiver_id: sellerId,
        content: `Hi, I'm interested in your listing.`,
        listing_id: listingId
      });
      
      // Refresh conversations to get the new one
      const response = await axios.get(`${API}/conversations`);
      setConversations(response.data);
      
      // Find and select the newly created conversation
      const newConvo = response.data.find(convo => 
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

  useEffect(() => {
    if (selectedConversation) {
      fetchMessages(selectedConversation.id);
    }
  }, [selectedConversation]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const connectWebSocket = () => {
    if (user) {
      const ws = new WebSocket(`${WS_URL}/ws/messages/${user.id}`);
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'new_message') {
          if (selectedConversation && data.message.conversation_id === selectedConversation.id) {
            setMessages(prev => [...prev, data.message]);
          }
          fetchConversations();
        }
      };
      
      wsRef.current = ws;
    }
  };

  const fetchConversations = async () => {
    try {
      const response = await axios.get(`${API}/conversations`);
      setConversations(response.data);
    } catch (error) {
      console.error('Failed to fetch conversations:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchMessages = async (conversationId) => {
    try {
      const response = await axios.get(`${API}/messages/${conversationId}`);
      setMessages(response.data);
    } catch (error) {
      console.error('Failed to fetch messages:', error);
      toast.error('Failed to load messages');
    }
  };

  const sendMessage = async () => {
    if (!newMessage.trim() || !selectedConversation) return;

    const receiverId = selectedConversation.participants.find(p => p !== user.id);

    try {
      await axios.post(`${API}/messages`, {
        receiver_id: receiverId,
        content: newMessage,
        listing_id: selectedConversation.listing_id || null
      });
      
      setNewMessage('');
      fetchMessages(selectedConversation.id);
    } catch (error) {
      toast.error('Failed to send message');
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const filteredConversations = conversations.filter(convo =>
    convo.other_user?.name.toLowerCase().includes(searchTerm.toLowerCase())
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
      <div className="w-full md:w-1/3 border-r bg-white dark:bg-gray-900">
        <div className="p-4 border-b">
          <h2 className="text-xl font-bold mb-4">Messages</h2>
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
                  {convo.other_user?.picture ? (
                    <img src={convo.other_user.picture} alt="" className="w-12 h-12 rounded-full" />
                  ) : (
                    <div className="w-12 h-12 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center">
                      <User className="h-6 w-6 text-white" />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-start">
                      <p className="font-semibold truncate">{convo.other_user?.name}</p>
                      {convo.unread_count > 0 && (
                        <span className="bg-primary text-white text-xs rounded-full px-2 py-1">
                          {convo.unread_count}
                        </span>
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

      <div className="flex-1 flex flex-col">
        {selectedConversation ? (
          <>
            <div className="p-4 border-b bg-white dark:bg-gray-900">
              <div className="flex items-center gap-3">
                {selectedConversation.other_user?.picture ? (
                  <img src={selectedConversation.other_user.picture} alt="" className="w-10 h-10 rounded-full" />
                ) : (
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center">
                    <User className="h-5 w-5 text-white" />
                  </div>
                )}
                <div>
                  <p className="font-semibold">{selectedConversation.other_user?.name}</p>
                  <p className="text-xs text-muted-foreground">Active</p>
                </div>
              </div>
            </div>

            <ScrollArea className="flex-1 p-4 space-y-4">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.sender_id === user.id ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[70%] rounded-lg p-3 ${
                      msg.sender_id === user.id
                        ? 'bg-gradient-to-br from-primary to-accent text-white'
                        : 'bg-gray-100 dark:bg-gray-800'
                    }`}
                  >
                    <p className="text-sm">{msg.content}</p>
                    <p className="text-xs mt-1 opacity-70">
                      {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </ScrollArea>

            <div className="p-4 border-t bg-white dark:bg-gray-900">
              <div className="flex gap-2">
                <Input
                  placeholder="Type a message..."
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                  data-testid="message-input"
                />
                <Button onClick={sendMessage} className="gradient-button text-white border-0" data-testid="send-message-btn">
                  <Send className="h-4 w-4" />
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
