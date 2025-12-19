import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent } from '../components/ui/card';
import { ScrollArea } from '../components/ui/scroll-area';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { 
  Send, User, Search, Wifi, WifiOff, Check, CheckCheck, Loader2, 
  Package, ExternalLink, Paperclip, Image, FileText, X, Download,
  Phone, Mail, Award, Clock, DollarSign, Share2, MessageSquare,
  Volume2, VolumeX, ChevronLeft, MoreVertical, Info, Maximize2
} from 'lucide-react';
import { useRealtimeMessaging } from '../hooks/useRealtimeMessaging';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// ========== NOTIFICATION SOUND ==========
const playMessageSound = () => {
  try {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    // BidVex brand-aligned ping sound (C major chord)
    oscillator.frequency.setValueAtTime(523.25, audioContext.currentTime); // C5
    oscillator.type = 'sine';
    
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
    
    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + 0.3);
  } catch (e) {
    console.log('Could not play notification sound');
  }
};

// ========== CONNECTION STATUS ==========
const ConnectionStatus = ({ connectionHealth }) => (
  <div className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ${
    connectionHealth === 'healthy' 
      ? 'bg-green-500/10 text-green-500' 
      : connectionHealth === 'connecting' 
      ? 'bg-yellow-500/10 text-yellow-500' 
      : 'bg-red-500/10 text-red-500'
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

// ========== PRODUCT MINI-CARD (CONTEXTUAL HEADER) ==========
const ProductMiniCard = ({ info, navigate }) => {
  if (!info) return null;
  
  const isLive = info.status === 'active' || new Date(info.auction_end_date) > new Date();
  
  return (
    <div 
      className="flex items-center gap-4 p-4 bg-gradient-to-r from-[#1E3A8A]/10 via-transparent to-[#06B6D4]/10 dark:from-[#1E3A8A]/20 dark:to-[#06B6D4]/20 border-b border-[#1E3A8A]/20 cursor-pointer hover:bg-[#1E3A8A]/5 transition-all"
      onClick={() => navigate(`/auction/${info.id}`)}
    >
      {info.image ? (
        <img src={info.image} alt="" className="w-16 h-16 rounded-xl object-cover ring-2 ring-[#06B6D4]/30 shadow-lg" />
      ) : (
        <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-[#1E3A8A] to-[#06B6D4] flex items-center justify-center">
          <Package className="h-8 w-8 text-white" />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <p className="font-bold text-slate-900 dark:text-white truncate text-lg">{info.title}</p>
        <div className="flex items-center gap-3 mt-1">
          <span className="text-xl font-bold text-[#06B6D4]">${info.price?.toFixed(2)}</span>
          <Badge className={`${isLive ? 'bg-green-500' : 'bg-slate-500'} text-white border-0 text-xs`}>
            {isLive ? '🔴 LIVE' : 'ENDED'}
          </Badge>
        </div>
      </div>
      <ExternalLink className="h-5 w-5 text-[#06B6D4]" />
    </div>
  );
};

// ========== SYSTEM MESSAGE CARD (WINNING HANDSHAKE) ==========
const SystemMessageCard = ({ message }) => {
  const data = message.system_data || {};
  
  if (message.message_type === 'auction_won') {
    return (
      <div className="mx-auto max-w-md my-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <Card className="overflow-hidden border-2 border-[#06B6D4]/30 bg-gradient-to-br from-[#1E3A8A]/5 to-[#06B6D4]/5 dark:from-[#1E3A8A]/20 dark:to-[#06B6D4]/20">
          <div className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] p-4 text-center">
            <Award className="h-10 w-10 text-white mx-auto mb-2" />
            <h3 className="text-white font-bold text-lg">🎉 Congratulations!</h3>
            <p className="text-white/80 text-sm">Auction Won</p>
          </div>
          <CardContent className="p-5 space-y-4">
            <p className="text-slate-700 dark:text-slate-200 text-center">
              You won the auction for <span className="font-bold text-[#1E3A8A] dark:text-[#06B6D4]">{data.item_title}</span>
            </p>
            
            {data.final_price && (
              <div className="text-center py-3 bg-slate-100 dark:bg-slate-800 rounded-lg">
                <p className="text-sm text-slate-500 dark:text-slate-400">Final Price</p>
                <p className="text-3xl font-bold text-[#06B6D4]">${data.final_price?.toFixed(2)}</p>
              </div>
            )}
            
            <div className="border-t border-slate-200 dark:border-slate-700 pt-4">
              <p className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">Contact Details:</p>
              <div className="space-y-2">
                {data.seller_name && (
                  <div className="flex items-center gap-3 text-sm">
                    <User className="h-4 w-4 text-[#06B6D4]" />
                    <span className="text-slate-700 dark:text-slate-200">{data.seller_name}</span>
                  </div>
                )}
                {data.seller_email && (
                  <div className="flex items-center gap-3 text-sm">
                    <Mail className="h-4 w-4 text-[#06B6D4]" />
                    <a href={`mailto:${data.seller_email}`} className="text-[#1E3A8A] dark:text-[#06B6D4] hover:underline">
                      {data.seller_email}
                    </a>
                  </div>
                )}
                {data.seller_phone && (
                  <div className="flex items-center gap-3 text-sm">
                    <Phone className="h-4 w-4 text-[#06B6D4]" />
                    <a href={`tel:${data.seller_phone}`} className="text-[#1E3A8A] dark:text-[#06B6D4] hover:underline">
                      {data.seller_phone}
                    </a>
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }
  
  // Generic system message
  return (
    <div className="text-center my-4">
      <span className="inline-block px-4 py-2 bg-slate-100 dark:bg-slate-800 rounded-full text-sm text-slate-600 dark:text-slate-300">
        {message.content}
      </span>
    </div>
  );
};

// ========== ITEM DETAILS SHARE CARD ==========
const ItemDetailsCard = ({ data }) => (
  <div className="bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-800 dark:to-slate-900 rounded-xl p-4 border border-slate-200 dark:border-slate-700 max-w-sm">
    <div className="flex items-center gap-2 mb-3">
      <Share2 className="h-4 w-4 text-[#06B6D4]" />
      <span className="text-sm font-semibold text-slate-600 dark:text-slate-300">Item Details</span>
    </div>
    {data.image && (
      <img src={data.image} alt="" className="w-full h-32 object-cover rounded-lg mb-3" />
    )}
    <h4 className="font-bold text-slate-900 dark:text-white mb-2">{data.title}</h4>
    <p className="text-sm text-slate-600 dark:text-slate-400 mb-3 line-clamp-2">{data.description}</p>
    <div className="flex justify-between items-center pt-3 border-t border-slate-200 dark:border-slate-700">
      <div>
        <p className="text-xs text-slate-500">Final Price</p>
        <p className="text-lg font-bold text-[#06B6D4]">${data.final_price?.toFixed(2)}</p>
      </div>
      <Badge className={`${data.payment_status === 'paid' ? 'bg-green-500' : 'bg-yellow-500'} text-white border-0`}>
        {data.payment_status === 'paid' ? '✓ Paid' : 'Pending'}
      </Badge>
    </div>
  </div>
);

// ========== ATTACHMENT PREVIEW ==========
const AttachmentPreview = ({ attachment, onView }) => {
  const isImage = attachment.type?.startsWith('image/') || /\.(jpg|jpeg|png|gif|webp)$/i.test(attachment.url);
  const isPDF = attachment.type === 'application/pdf' || /\.pdf$/i.test(attachment.url);
  
  return (
    <div 
      className="relative group cursor-pointer rounded-lg overflow-hidden bg-slate-100 dark:bg-slate-800"
      onClick={() => onView(attachment)}
    >
      {isImage ? (
        <img src={attachment.url} alt={attachment.name} className="w-40 h-32 object-cover" />
      ) : isPDF ? (
        <div className="w-40 h-32 flex flex-col items-center justify-center bg-red-50 dark:bg-red-900/20">
          <FileText className="h-10 w-10 text-red-500" />
          <span className="text-xs mt-2 text-slate-600 dark:text-slate-300 truncate max-w-[90%]">{attachment.name}</span>
        </div>
      ) : (
        <div className="w-40 h-32 flex flex-col items-center justify-center">
          <FileText className="h-10 w-10 text-slate-400" />
          <span className="text-xs mt-2 text-slate-600 dark:text-slate-300 truncate max-w-[90%]">{attachment.name}</span>
        </div>
      )}
      <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
        <Maximize2 className="h-6 w-6 text-white" />
      </div>
    </div>
  );
};

// ========== LIGHTBOX PREVIEW ==========
const Lightbox = ({ attachment, onClose }) => {
  if (!attachment) return null;
  
  const isImage = attachment.type?.startsWith('image/') || /\.(jpg|jpeg|png|gif|webp)$/i.test(attachment.url);
  
  return (
    <div 
      className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <button 
        className="absolute top-4 right-4 p-2 bg-white/10 rounded-full hover:bg-white/20 transition-colors"
        onClick={onClose}
      >
        <X className="h-6 w-6 text-white" />
      </button>
      
      <a 
        href={attachment.url}
        download={attachment.name}
        className="absolute top-4 right-16 p-2 bg-white/10 rounded-full hover:bg-white/20 transition-colors"
        onClick={(e) => e.stopPropagation()}
      >
        <Download className="h-6 w-6 text-white" />
      </a>
      
      <div className="max-w-4xl max-h-[90vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
        {isImage ? (
          <img src={attachment.url} alt={attachment.name} className="max-w-full max-h-[85vh] object-contain rounded-lg" />
        ) : (
          <iframe 
            src={attachment.url} 
            title={attachment.name}
            className="w-[90vw] h-[85vh] bg-white rounded-lg"
          />
        )}
      </div>
    </div>
  );
};

// ========== FILE UPLOAD PROGRESS ==========
const UploadProgress = ({ progress, fileName }) => (
  <div className="flex items-center gap-3 p-3 bg-slate-100 dark:bg-slate-800 rounded-lg">
    <Loader2 className="h-5 w-5 text-[#06B6D4] animate-spin" />
    <div className="flex-1">
      <p className="text-sm text-slate-700 dark:text-slate-200 truncate">{fileName}</p>
      <div className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-full mt-1 overflow-hidden">
        <div 
          className="h-full bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] rounded-full transition-all duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
    <span className="text-xs text-slate-500">{progress}%</span>
  </div>
);

// ========== MESSAGE BUBBLE ==========
const MessageBubble = ({ message, isOwn, onViewAttachment }) => {
  const hasAttachment = message.attachments?.length > 0;
  const hasItemDetails = message.message_type === 'item_details';
  
  return (
    <div className={`flex ${isOwn ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-200`}>
      <div className={`max-w-[75%] ${isOwn ? '' : ''}`}>
        {/* Item Details Card */}
        {hasItemDetails && message.item_data && (
          <ItemDetailsCard data={message.item_data} />
        )}
        
        {/* Attachments */}
        {hasAttachment && (
          <div className="flex flex-wrap gap-2 mb-2">
            {message.attachments.map((att, idx) => (
              <AttachmentPreview key={idx} attachment={att} onView={onViewAttachment} />
            ))}
          </div>
        )}
        
        {/* Text Message */}
        {message.content && (
          <div className={`rounded-2xl p-4 ${
            isOwn
              ? 'bg-gradient-to-br from-[#06B6D4] to-[#1E3A8A] text-white rounded-br-sm'
              : 'bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white rounded-bl-sm'
          } ${message._pending ? 'opacity-70' : ''}`}>
            <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</p>
          </div>
        )}
        
        {/* Timestamp & Read Receipt */}
        <div className={`flex items-center gap-1.5 mt-1 ${isOwn ? 'justify-end' : 'justify-start'}`}>
          <span className="text-xs text-slate-400">
            {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
          {isOwn && (
            message._pending ? (
              <Loader2 className="h-3 w-3 animate-spin text-slate-400" />
            ) : message.is_read ? (
              <CheckCheck className="h-3.5 w-3.5 text-[#06B6D4]" />
            ) : (
              <Check className="h-3.5 w-3.5 text-slate-400" />
            )
          )}
        </div>
      </div>
    </div>
  );
};

// ========== CONVERSATION LIST ITEM ==========
const ConversationItem = ({ convo, isSelected, onClick, otherUserOnline }) => (
  <div
    onClick={onClick}
    className={`p-4 cursor-pointer transition-all border-l-4 ${
      isSelected 
        ? 'bg-gradient-to-r from-[#1E3A8A]/10 to-transparent border-[#06B6D4] dark:from-[#1E3A8A]/30' 
        : 'border-transparent hover:bg-slate-50 dark:hover:bg-slate-800/50'
    }`}
    data-testid={`conversation-${convo.id}`}
  >
    <div className="flex items-start gap-3">
      <div className="relative flex-shrink-0">
        {convo.other_user?.picture ? (
          <img src={convo.other_user.picture} alt="" className="w-12 h-12 rounded-full ring-2 ring-white dark:ring-slate-800 shadow-md" />
        ) : (
          <div className="w-12 h-12 rounded-full bg-gradient-to-br from-[#1E3A8A] to-[#06B6D4] flex items-center justify-center shadow-md">
            <User className="h-6 w-6 text-white" />
          </div>
        )}
        {otherUserOnline && (
          <span className="absolute bottom-0 right-0 w-3.5 h-3.5 bg-green-500 border-2 border-white dark:border-slate-900 rounded-full" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex justify-between items-start mb-1">
          <p className="font-semibold text-slate-900 dark:text-white truncate">{convo.other_user?.name}</p>
          <span className="text-xs text-slate-400 whitespace-nowrap ml-2">
            {convo.last_message_time && new Date(convo.last_message_time).toLocaleDateString()}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <p className="text-sm text-slate-500 dark:text-slate-400 truncate flex-1">{convo.last_message}</p>
          {convo.unread_count > 0 && (
            <Badge className="bg-[#06B6D4] text-white border-0 text-xs px-2 min-w-[20px] flex items-center justify-center">
              {convo.unread_count}
            </Badge>
          )}
        </div>
        {convo.listing_title && (
          <div className="flex items-center gap-1 mt-1.5">
            <Package className="h-3 w-3 text-[#06B6D4]" />
            <span className="text-xs text-[#1E3A8A] dark:text-[#06B6D4] truncate">{convo.listing_title}</span>
          </div>
        )}
      </div>
    </div>
  </div>
);

// ========== MAIN MESSAGES PAGE ==========
const MessagesPage = () => {
  const { t } = useTranslation();
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [conversations, setConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [newMessage, setNewMessage] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [lightboxAttachment, setLightboxAttachment] = useState(null);
  const [showMobileConversations, setShowMobileConversations] = useState(true);
  
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const typingTimeoutRef = useRef(null);
  const fileInputRef = useRef(null);

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

  // Play sound on new message
  useEffect(() => {
    if (messages.length > 0 && soundEnabled) {
      const lastMsg = messages[messages.length - 1];
      if (lastMsg.sender_id !== user?.id && !lastMsg._local) {
        playMessageSound();
      }
    }
  }, [messages.length, soundEnabled, user?.id]);

  // Fetch conversations on mount
  useEffect(() => {
    if (user && token) {
      fetchConversations();
    }
  }, [user, token]);

  // Auto-select conversation when redirected
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
        setShowMobileConversations(false);
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
      setShowMobileConversations(false);
    }
  }, [selectedConversation]);

  // Auto-scroll to bottom
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Mark messages as read
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
      toast.success('Conversation started!');
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

    if (isConnected) {
      const sent = wsSendMessage(messageContent);
      if (sent) {
        setSending(false);
        sendTypingStop();
        return;
      }
    }

    try {
      const receiverId = selectedConversation.participants.find(p => p !== user.id);
      await axios.post(`${API}/messages`, {
        receiver_id: receiverId,
        content: messageContent,
        listing_id: selectedConversation.listing_id || null
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      await fetchMessages(selectedConversation.id);
    } catch (error) {
      toast.error('Failed to send message');
      setInitialMessages(messages.filter(m => m.id !== optimisticMessage.id));
    } finally {
      setSending(false);
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file || !selectedConversation) return;
    
    // Validate file size (10MB max)
    if (file.size > 10 * 1024 * 1024) {
      toast.error('File size must be less than 10MB');
      return;
    }
    
    // Validate file type
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'application/pdf'];
    if (!allowedTypes.includes(file.type)) {
      toast.error('Only JPG, PNG, GIF, WebP and PDF files are allowed');
      return;
    }
    
    setUploadProgress({ progress: 0, fileName: file.name });
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('receiver_id', selectedConversation.participants.find(p => p !== user.id));
      formData.append('conversation_id', selectedConversation.id);
      
      await axios.post(`${API}/messages/attachment`, formData, {
        headers: { 
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        },
        onUploadProgress: (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress({ progress, fileName: file.name });
        }
      });
      
      toast.success('File uploaded successfully');
      await fetchMessages(selectedConversation.id);
    } catch (error) {
      toast.error('Failed to upload file');
    } finally {
      setUploadProgress(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const sendItemDetails = async () => {
    if (!selectedConversation || !listingInfo) return;
    
    try {
      await axios.post(`${API}/messages/share-item-details`, {
        conversation_id: selectedConversation.id,
        listing_id: listingInfo.id
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      toast.success('Item details shared');
      await fetchMessages(selectedConversation.id);
    } catch (error) {
      toast.error('Failed to share item details');
    }
  };

  const handleInputChange = (e) => {
    setNewMessage(e.target.value);
    
    if (e.target.value.length > 0) {
      sendTypingStart();
      
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
      
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
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900">
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin text-[#06B6D4] mx-auto mb-4" />
          <p className="text-slate-600 dark:text-slate-300">Loading messages...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-64px)] flex bg-white dark:bg-slate-900" data-testid="messages-page">
      {/* Hidden file input */}
      <input
        type="file"
        ref={fileInputRef}
        className="hidden"
        accept="image/jpeg,image/png,image/gif,image/webp,application/pdf"
        onChange={handleFileUpload}
      />
      
      {/* Lightbox */}
      {lightboxAttachment && (
        <Lightbox attachment={lightboxAttachment} onClose={() => setLightboxAttachment(null)} />
      )}
      
      {/* ========== CONVERSATIONS LIST (Left Pane) ========== */}
      <div className={`${showMobileConversations ? 'flex' : 'hidden'} md:flex flex-col w-full md:w-96 border-r border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900`}>
        {/* Header */}
        <div className="p-5 border-b border-slate-200 dark:border-slate-700 bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4]">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <MessageSquare className="h-6 w-6 text-white" />
              <h2 className="text-xl font-bold text-white">Messages</h2>
            </div>
            <div className="flex items-center gap-2">
              <button 
                onClick={() => setSoundEnabled(!soundEnabled)}
                className="p-2 rounded-full bg-white/10 hover:bg-white/20 transition-colors"
                title={soundEnabled ? 'Mute sounds' : 'Enable sounds'}
              >
                {soundEnabled ? (
                  <Volume2 className="h-4 w-4 text-white" />
                ) : (
                  <VolumeX className="h-4 w-4 text-white" />
                )}
              </button>
              <ConnectionStatus connectionHealth={connectionHealth} />
            </div>
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              placeholder="Search conversations..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10 bg-white/10 border-white/20 text-white placeholder:text-white/60 focus:bg-white/20"
            />
          </div>
        </div>
        
        {/* Conversations List */}
        <ScrollArea className="flex-1">
          {filteredConversations.length > 0 ? (
            filteredConversations.map((convo) => (
              <ConversationItem
                key={convo.id}
                convo={convo}
                isSelected={selectedConversation?.id === convo.id}
                onClick={() => setSelectedConversation(convo)}
                otherUserOnline={selectedConversation?.id === convo.id && otherUserOnline}
              />
            ))
          ) : (
            <div className="p-8 text-center">
              <MessageSquare className="h-16 w-16 mx-auto mb-4 text-slate-300 dark:text-slate-600" />
              <p className="text-slate-500 dark:text-slate-400">No conversations yet</p>
              <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">Start by messaging a seller</p>
            </div>
          )}
        </ScrollArea>
      </div>

      {/* ========== CHAT AREA (Right Pane) ========== */}
      <div className={`${!showMobileConversations || !selectedConversation ? 'flex' : 'hidden'} md:flex flex-col flex-1`}>
        {selectedConversation ? (
          <>
            {/* Chat Header */}
            <div className="border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
              {/* User Info Bar */}
              <div className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {/* Mobile back button */}
                  <button 
                    onClick={() => setShowMobileConversations(true)}
                    className="md:hidden p-2 -ml-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
                  >
                    <ChevronLeft className="h-5 w-5" />
                  </button>
                  
                  <div className="relative">
                    {otherUser?.picture || selectedConversation.other_user?.picture ? (
                      <img 
                        src={otherUser?.picture || selectedConversation.other_user?.picture} 
                        alt="" 
                        className="w-11 h-11 rounded-full ring-2 ring-[#06B6D4]/30" 
                      />
                    ) : (
                      <div className="w-11 h-11 rounded-full bg-gradient-to-br from-[#1E3A8A] to-[#06B6D4] flex items-center justify-center">
                        <User className="h-5 w-5 text-white" />
                      </div>
                    )}
                    {otherUserOnline && (
                      <span className="absolute bottom-0 right-0 w-3 h-3 bg-green-500 border-2 border-white dark:border-slate-900 rounded-full" />
                    )}
                  </div>
                  <div>
                    <p className="font-semibold text-slate-900 dark:text-white">
                      {otherUser?.name || selectedConversation.other_user?.name}
                    </p>
                    <p className={`text-xs ${otherUserOnline ? 'text-green-500' : 'text-slate-400'}`}>
                      {otherUserTyping ? (
                        <span className="flex items-center gap-1">
                          <span className="flex gap-0.5">
                            <span className="w-1.5 h-1.5 bg-[#06B6D4] rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                            <span className="w-1.5 h-1.5 bg-[#06B6D4] rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                            <span className="w-1.5 h-1.5 bg-[#06B6D4] rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                          </span>
                          typing...
                        </span>
                      ) : otherUserOnline ? 'Online' : 'Offline'}
                    </p>
                  </div>
                </div>
                
                <div className="flex items-center gap-2">
                  {/* Share Item Details (for sellers) */}
                  {listingInfo && user?.id === listingInfo.seller_id && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={sendItemDetails}
                      className="border-[#06B6D4] text-[#06B6D4] hover:bg-[#06B6D4]/10"
                    >
                      <Share2 className="h-4 w-4 mr-1" />
                      Share Details
                    </Button>
                  )}
                  
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <MoreVertical className="h-5 w-5" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => navigate(`/profile/${otherUser?.id || selectedConversation.other_user?.id}`)}>
                        <User className="h-4 w-4 mr-2" /> View Profile
                      </DropdownMenuItem>
                      {listingInfo && (
                        <DropdownMenuItem onClick={() => navigate(`/auction/${listingInfo.id}`)}>
                          <Package className="h-4 w-4 mr-2" /> View Listing
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
              
              {/* Product Mini-Card */}
              <ProductMiniCard info={listingInfo} navigate={navigate} />
            </div>

            {/* Messages Area */}
            <ScrollArea className="flex-1 p-4 bg-slate-50 dark:bg-slate-950">
              <div className="space-y-4 max-w-3xl mx-auto">
                {messages.map((msg) => (
                  msg.message_type === 'system' || msg.message_type === 'auction_won' ? (
                    <SystemMessageCard key={msg.id} message={msg} />
                  ) : (
                    <MessageBubble 
                      key={msg.id} 
                      message={msg} 
                      isOwn={msg.sender_id === user.id}
                      onViewAttachment={setLightboxAttachment}
                    />
                  )
                ))}
                
                {/* Typing indicator */}
                {otherUserTyping && (
                  <div className="flex justify-start animate-in fade-in">
                    <div className="bg-slate-200 dark:bg-slate-800 rounded-2xl rounded-bl-sm p-4">
                      <div className="flex gap-1">
                        <span className="w-2 h-2 bg-[#06B6D4] rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <span className="w-2 h-2 bg-[#06B6D4] rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <span className="w-2 h-2 bg-[#06B6D4] rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                    </div>
                  </div>
                )}
                
                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>

            {/* Upload Progress */}
            {uploadProgress && (
              <div className="px-4 pb-2">
                <UploadProgress progress={uploadProgress.progress} fileName={uploadProgress.fileName} />
              </div>
            )}

            {/* Message Input */}
            <div className="p-4 border-t border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
              <div className="flex gap-2 max-w-3xl mx-auto">
                <Button 
                  variant="ghost" 
                  size="icon"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={!!uploadProgress}
                  className="text-slate-500 hover:text-[#06B6D4] hover:bg-[#06B6D4]/10"
                >
                  <Paperclip className="h-5 w-5" />
                </Button>
                <Input
                  ref={inputRef}
                  placeholder="Type a message..."
                  value={newMessage}
                  onChange={handleInputChange}
                  onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                  data-testid="message-input"
                  disabled={sending}
                  className="flex-1 border-slate-200 dark:border-slate-700 focus:border-[#06B6D4] focus:ring-[#06B6D4]/20"
                />
                <Button 
                  onClick={sendMessage} 
                  className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white hover:opacity-90 shadow-lg shadow-[#06B6D4]/30" 
                  data-testid="send-message-btn"
                  disabled={!newMessage.trim() || sending}
                >
                  {sending ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <Send className="h-5 w-5" />
                  )}
                </Button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-950">
            <div className="text-center max-w-md p-8">
              <div className="w-24 h-24 mx-auto mb-6 rounded-full bg-gradient-to-br from-[#1E3A8A]/20 to-[#06B6D4]/20 flex items-center justify-center">
                <MessageSquare className="h-12 w-12 text-[#06B6D4]" />
              </div>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">BidVex Pro-Connect</h3>
              <p className="text-slate-500 dark:text-slate-400">
                Select a conversation to start messaging. Connect with sellers and buyers instantly!
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MessagesPage;
