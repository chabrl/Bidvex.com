import API_BASE from '../config';
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { X, MessageCircle, Send, ShieldCheck, CreditCard, Package, HelpCircle, Mail, GripVertical } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

// Mobile bottom-nav height + safe gap. MobileBottomNav.js renders 64px nav
// content + iPhone safe-area-inset-bottom (≈34px on iPhones with home indicator,
// 0px on Android & iPads). We keep a 16px breathing-room gap above the nav.
const MOBILE_NAV_HEIGHT = 64;       // matches --bidvex-mobile-nav-height
const FAB_GAP = 16;                 // breathing room above the nav
const FAB_RIGHT_OFFSET = 16;
const FAB_SIZE = 56;                // 14 in tailwind ≈ 56px (3.5rem)
const STORAGE_KEY = 'bidvex.fabPosition.v1';

// Bottom inset (in px) including iPhone home-indicator safe area.
// Read at runtime by querying a hidden element with `padding-bottom: env(...)`.
const getSafeAreaBottom = () => {
  if (typeof window === 'undefined' || typeof document === 'undefined') return 0;
  const probe = document.createElement('div');
  probe.style.cssText = 'position:fixed;bottom:0;height:0;padding-bottom:env(safe-area-inset-bottom,0px);visibility:hidden;pointer-events:none;';
  document.body.appendChild(probe);
  const v = parseFloat(getComputedStyle(probe).paddingBottom) || 0;
  document.body.removeChild(probe);
  return v;
};

// Total floor offset from bottom of viewport that the FAB must respect:
// nav-height + safe-area-inset-bottom + breathing gap.
const getFabBottomFloor = () => MOBILE_NAV_HEIGHT + getSafeAreaBottom() + FAB_GAP;

const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

const AIAssistant = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Welcome to BidVex! I am your Master Concierge, here to provide exceptional service. How may I assist you today?',
      rich_content: null,
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [serviceDegraded, setServiceDegraded] = useState(false);
  const messagesEndRef = useRef(null);
  const { token } = useAuth();
  const navigate = useNavigate();
  const backendUrl = API_BASE;

  // ── Draggable FAB state ──
  // Position is stored as {x, y} in viewport pixels (from top-left).
  // Default sits the FAB above the mobile bottom-nav at the right edge.
  const computeDefaultPos = () => ({
    x: typeof window !== 'undefined' ? window.innerWidth - FAB_SIZE - FAB_RIGHT_OFFSET : 16,
    y: typeof window !== 'undefined' ? window.innerHeight - FAB_SIZE - getFabBottomFloor() : 88,
  });

  const [fabPos, setFabPos] = useState(() => {
    if (typeof window === 'undefined') return { x: 16, y: 88 };
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (saved && typeof saved.x === 'number' && typeof saved.y === 'number') {
        return {
          x: clamp(saved.x, 8, window.innerWidth - FAB_SIZE - 8),
          y: clamp(saved.y, 8, window.innerHeight - FAB_SIZE - getFabBottomFloor()),
        };
      }
    } catch { /* ignore */ }
    return computeDefaultPos();
  });

  const dragRef = useRef({ dragging: false, startX: 0, startY: 0, origX: 0, origY: 0, moved: false });

  // Re-clamp on viewport resize / rotation so FAB never falls off-screen.
  useEffect(() => {
    const onResize = () => {
      setFabPos((p) => ({
        x: clamp(p.x, 8, window.innerWidth - FAB_SIZE - 8),
        y: clamp(p.y, 8, window.innerHeight - FAB_SIZE - getFabBottomFloor()),
      }));
    };
    window.addEventListener('resize', onResize);
    window.addEventListener('orientationchange', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      window.removeEventListener('orientationchange', onResize);
    };
  }, []);

  const persistPos = useCallback((p) => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(p)); } catch { /* ignore */ }
  }, []);

  // Drag handlers — work for both touch and mouse.
  const onPointerDown = (e) => {
    const point = e.touches ? e.touches[0] : e;
    dragRef.current = {
      dragging: true,
      startX: point.clientX,
      startY: point.clientY,
      origX: fabPos.x,
      origY: fabPos.y,
      moved: false,
    };
  };
  const onPointerMove = (e) => {
    if (!dragRef.current.dragging) return;
    const point = e.touches ? e.touches[0] : e;
    const dx = point.clientX - dragRef.current.startX;
    const dy = point.clientY - dragRef.current.startY;
    if (Math.abs(dx) > 4 || Math.abs(dy) > 4) {
      dragRef.current.moved = true;
      e.preventDefault?.();
    }
    if (!dragRef.current.moved) return;
    const nx = clamp(dragRef.current.origX + dx, 8, window.innerWidth - FAB_SIZE - 8);
    const ny = clamp(dragRef.current.origY + dy, 8, window.innerHeight - FAB_SIZE - getFabBottomFloor());
    setFabPos({ x: nx, y: ny });
  };
  const onPointerUp = () => {
    if (!dragRef.current.dragging) return;
    if (dragRef.current.moved) persistPos(fabPos);
    dragRef.current.dragging = false;
  };

  // Click vs drag: only open chat if pointer never moved during the press.
  const handleFabClick = () => {
    if (dragRef.current.moved) return;     // dragged → ignore click
    setIsOpen(true);
  };

  // Reset position to default (long-press or right-click handler optional, exposed in console)
  useEffect(() => {
    window.__bidvexResetFabPos = () => {
      const def = computeDefaultPos();
      setFabPos(def);
      persistPos(def);
    };
    return () => { try { delete window.__bidvexResetFabPos; } catch { /* ignore */ } };
  }, [persistPos]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => { scrollToBottom(); }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input;
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userMessage, rich_content: null }]);
    setIsLoading(true);

    try {
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const lang = (navigator.language || 'en').startsWith('fr') ? 'fr' : 'en';
      const ctrl = new AbortController();
      const timeoutId = setTimeout(() => ctrl.abort(), 30000); // 30s hard timeout
      const res = await fetch(`${backendUrl}/ai-chat/message`, {
        method: 'POST',
        headers,
        signal: ctrl.signal,
        body: JSON.stringify({
          message: userMessage,
          chat_history: messages.slice(-10).map((m) => ({ role: m.role, content: m.content })),
          language: lang,
        }),
      });
      clearTimeout(timeoutId);
      if (!res.ok) {
        // Service responded but errored (5xx, 429, etc.) → graceful degraded state
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();
      if (data && data.success === false) {
        // Backend returned 200 but with success:false (LLM unreachable) → degrade
        throw new Error(data.error || 'LLM unavailable');
      }
      setServiceDegraded(false);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: data.message, rich_content: data.rich_content },
      ]);
    } catch (e) {
      setServiceDegraded(true);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Service temporarily unavailable. Please retry in a moment, or email support@bidvex.com for immediate help.\n\nService temporairement indisponible. Veuillez réessayer dans un instant ou écrire à support@bidvex.com pour de l\'aide immédiate.',
          rich_content: {
            has_rich_content: true,
            action_buttons: [
              { text: 'Email Support / Contacter le support', action: 'email', url: 'support@bidvex.com', icon: 'mail', style: 'primary' },
            ],
          },
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleActionButton = (action, url) => {
    if (action === 'navigate' && url) {
      navigate(url);
      setIsOpen(false);
    } else if (action === 'open_url' && url) {
      window.open(url, '_blank', 'noopener,noreferrer');
    } else if (action === 'email' && url) {
      window.location.href = `mailto:${url}`;
    }
  };

  const getActionIcon = (icon) => {
    const iconProps = { className: 'h-4 w-4 mr-2' };
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
          onClick={handleFabClick}
          onMouseDown={onPointerDown}
          onMouseMove={onPointerMove}
          onMouseUp={onPointerUp}
          onMouseLeave={onPointerUp}
          onTouchStart={onPointerDown}
          onTouchMove={onPointerMove}
          onTouchEnd={onPointerUp}
          className="rounded-full w-14 h-14 sm:w-16 sm:h-16 text-white border border-white/20 shadow-2xl transition-shadow hover:scale-110 hover:shadow-cyan-500/50 hover:border-white/40 select-none touch-none cursor-grab active:cursor-grabbing"
          style={{
            position: 'fixed',
            left: fabPos.x,
            top: fabPos.y,
            zIndex: 1000,
            backdropFilter: 'blur(8px)',
            background: 'rgba(37, 99, 235, 0.9)',
            touchAction: 'none',
          }}
          data-testid="ai-assistant-btn"
          aria-label="Open BidVex Master Concierge — drag to reposition"
          title="Tap to chat. Drag to reposition."
        >
          <MessageCircle className="h-7 w-7 pointer-events-none" />
          <GripVertical className="absolute -top-1 -right-1 h-3 w-3 text-white/60 pointer-events-none" aria-hidden="true" />
        </Button>
      )}

      {isOpen && (
        <>
          {/* Mobile Bottom Sheet Backdrop */}
          <div
            className="md:hidden fixed inset-0 bg-black/50 z-[999] backdrop-blur-sm"
            onClick={() => setIsOpen(false)}
            data-testid="ai-assistant-backdrop"
          />

          {/* Chatbot Card — also sits above the mobile bottom nav */}
          <div
            className="fixed z-[1000] flex flex-col rounded-2xl overflow-hidden shadow-2xl border border-white/10 bg-white dark:bg-slate-900"
            style={{
              left: '12px',
              right: '12px',
              bottom: `calc(${MOBILE_NAV_HEIGHT}px + env(safe-area-inset-bottom, 0px) + ${FAB_GAP}px)`,
              maxHeight: `calc(100vh - ${MOBILE_NAV_HEIGHT}px - env(safe-area-inset-bottom, 0px) - 64px)`,
            }}
          >
            {/* Header */}
            <div className="p-4 flex justify-between items-center bg-gradient-to-br from-[#1E3A8A] to-[#06B6D4] text-white flex-shrink-0">
              <div>
                <h3 className="font-bold text-lg text-white">BidVex Master Concierge</h3>
                <p className="text-xs text-white/90">Your Luxury Auction Specialist</p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsOpen(false)}
                className="text-white hover:bg-white/20 rounded-full"
                aria-label="Close"
                data-testid="ai-assistant-close-btn"
              >
                <X className="h-5 w-5" />
              </Button>
            </div>

            {/* Degraded service banner */}
            {serviceDegraded && (
              <div
                className="px-4 py-2 bg-amber-50 dark:bg-amber-900/30 border-b border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-200 text-xs flex-shrink-0"
                data-testid="ai-degraded-banner"
              >
                <span className="font-semibold">⚠ Service degraded.</span> Some replies may fail. Email <a href="mailto:support@bidvex.com" className="underline">support@bidvex.com</a> for urgent help.
              </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-slate-800 min-h-0">
              {messages.map((msg, idx) => (
                <div key={idx}>
                  <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-[85%] rounded-2xl p-3 shadow-md ${
                        msg.role === 'user'
                          ? 'bg-gradient-to-br from-[#1E3A8A] to-[#06B6D4] text-white'
                          : 'bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 border border-gray-200 dark:border-gray-700'
                      }`}
                    >
                      <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{msg.content}</p>
                    </div>
                  </div>
                  {msg.rich_content?.has_rich_content && msg.rich_content.action_buttons?.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2 justify-start ml-2">
                      {msg.rich_content.action_buttons.map((btn, btnIdx) => (
                        <Button
                          key={btnIdx}
                          onClick={() => handleActionButton(btn.action, btn.url)}
                          variant={btn.style === 'primary' ? 'default' : 'outline'}
                          size="sm"
                          className={
                            btn.style === 'primary'
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

              {/* Animated typing indicator (instant feedback while waiting on the LLM) */}
              {isLoading && (
                <div className="flex justify-start" data-testid="ai-typing-indicator">
                  <div className="bg-white dark:bg-gray-800 rounded-2xl px-4 py-3 shadow-sm border border-gray-200 dark:border-gray-700 flex items-center gap-1">
                    <span className="w-2 h-2 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t bg-white dark:bg-gray-800 flex-shrink-0">
              <div className="flex gap-2">
                <Input
                  placeholder="Ask me anything about BidVex..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                  disabled={isLoading}
                  className="flex-1 border-gray-300 focus:border-[#06B6D4] focus:ring-[#06B6D4] text-slate-900 dark:text-slate-100"
                  data-testid="ai-assistant-input"
                />
                <Button
                  onClick={handleSend}
                  disabled={isLoading || !input.trim()}
                  className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] hover:from-[#1E3A8A]/90 hover:to-[#06B6D4]/90 text-white border-0 px-4 flex-shrink-0"
                  data-testid="ai-assistant-send-btn"
                >
                  <Send className="h-4 w-4" />
                </Button>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 text-center">
                Powered by Gemini 2.5 Flash &bull; Available 24/7
              </p>
            </div>
          </div>
        </>
      )}
    </>
  );
};

export default AIAssistant;
