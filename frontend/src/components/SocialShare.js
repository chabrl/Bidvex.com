import React, { useState } from 'react';
import { Button } from './ui/button';
import { Share2, Facebook, Instagram, Linkedin, MessageCircle, X } from 'lucide-react';
import { toast } from 'sonner';

const SocialShare = ({ title, url, description, className = '' }) => {
  const [showMenu, setShowMenu] = useState(false);

  const shareUrl = url || window.location.href;
  const shareTitle = title || 'Check out this auction on BidVex';
  const shareText = description || `${shareTitle} - ${shareUrl}`;

  const shareLinks = {
    facebook: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}`,
    twitter: `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(shareUrl)}`,
    linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`,
    whatsapp: `https://wa.me/?text=${encodeURIComponent(shareText)}`,
  };

  const handleShare = (platform) => {
    if (platform === 'instagram') {
      // Instagram doesn't support web sharing, so copy link
      copyToClipboard();
      toast.info('Link copied! Paste it in your Instagram post or story');
      return;
    }

    window.open(shareLinks[platform], '_blank', 'width=600,height=400');
    setShowMenu(false);
    toast.success(`Shared on ${platform.charAt(0).toUpperCase() + platform.slice(1)}!`);
  };

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      toast.success('Link copied to clipboard!');
      setShowMenu(false);
    } catch (err) {
      toast.error('Failed to copy link');
    }
  };

  const shareOptions = [
    { id: 'facebook', name: 'Facebook', icon: Facebook, color: 'hover:bg-blue-600 hover:text-white' },
    { id: 'twitter', name: 'Twitter', icon: X, color: 'hover:bg-black hover:text-white' },
    { id: 'linkedin', name: 'LinkedIn', icon: Linkedin, color: 'hover:bg-blue-700 hover:text-white' },
    { id: 'whatsapp', name: 'WhatsApp', icon: MessageCircle, color: 'hover:bg-green-600 hover:text-white' },
    { id: 'instagram', name: 'Instagram', icon: Instagram, color: 'hover:bg-pink-600 hover:text-white' },
  ];

  return (
    <div className={`relative ${className}`}>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setShowMenu(!showMenu)}
        className="gap-2"
        title="Share"
      >
        <Share2 className="h-4 w-4" />
        <span className="hidden sm:inline">Share</span>
      </Button>

      {showMenu && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setShowMenu(false)}
          />

          {/* Share Menu */}
          <div className="absolute right-0 top-full mt-2 z-50 w-56 bg-white dark:bg-gray-900 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 py-2">
            <div className="px-3 py-2 border-b border-gray-200 dark:border-gray-700">
              <p className="text-sm font-semibold">Share this auction</p>
            </div>
            
            {shareOptions.map((option) => {
              const Icon = option.icon;
              return (
                <button
                  key={option.id}
                  onClick={() => handleShare(option.id)}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${option.color}`}
                >
                  <Icon className="h-5 w-5" />
                  <span>{option.name}</span>
                </button>
              );
            })}

            <div className="border-t border-gray-200 dark:border-gray-700 mt-1 pt-1">
              <button
                onClick={copyToClipboard}
                className="w-full flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
              >
                <Share2 className="h-5 w-5" />
                <span>Copy Link</span>
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default SocialShare;
