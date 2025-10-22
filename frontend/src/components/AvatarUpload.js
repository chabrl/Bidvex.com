import React, { useState, useRef } from 'react';
import AvatarEditor from 'react-avatar-editor';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Slider } from './ui/slider';
import { Upload, User } from 'lucide-react';
import { toast } from 'sonner';

const AvatarUpload = ({ currentAvatar, onAvatarUpdate }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [image, setImage] = useState(null);
  const [scale, setScale] = useState(1);
  const [rotation, setRotation] = useState(0);
  const editorRef = useRef(null);
  const fileInputRef = useRef(null);

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (file.size > 5000000) {
        toast.error('Image size should be less than 5MB');
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        setImage(reader.result);
        setIsOpen(true);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSave = async () => {
    if (editorRef.current) {
      const canvas = editorRef.current.getImageScaledToCanvas();
      const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
      
      try {
        await onAvatarUpdate(dataUrl);
        toast.success('Profile photo updated!');
        setIsOpen(false);
        setImage(null);
      } catch (error) {
        toast.error('Failed to update photo');
      }
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <div className="relative">
          {currentAvatar ? (
            <img
              src={currentAvatar}
              alt="Profile"
              className="w-24 h-24 rounded-full object-cover border-4 border-primary"
            />
          ) : (
            <div className="w-24 h-24 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center text-white text-3xl font-bold">
              <User className="w-12 h-12" />
            </div>
          )}
        </div>
        <div className="space-y-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            data-testid="upload-avatar-btn"
          >
            <Upload className="mr-2 h-4 w-4" />
            Upload Photo
          </Button>
          <p className="text-xs text-muted-foreground">JPG, PNG or GIF (max 5MB)</p>
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handleFileSelect}
        className="hidden"
      />

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Profile Photo</DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4">
            <div className="flex justify-center bg-gray-100 dark:bg-gray-800 p-4 rounded-lg">
              {image && (
                <AvatarEditor
                  ref={editorRef}
                  image={image}
                  width={250}
                  height={250}
                  border={20}
                  borderRadius={125}
                  color={[0, 0, 0, 0.6]}
                  scale={scale}
                  rotate={rotation}
                />
              )}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Zoom</label>
              <Slider
                value={[scale]}
                onValueChange={(value) => setScale(value[0])}
                min={1}
                max={3}
                step={0.1}
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Rotation</label>
              <Slider
                value={[rotation]}
                onValueChange={(value) => setRotation(value[0])}
                min={0}
                max={360}
                step={1}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} className="gradient-button text-white border-0">
              Save Photo
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AvatarUpload;
