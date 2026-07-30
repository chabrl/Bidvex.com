import API_BASE from '../../config';
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import {
  MessageSquare, Search, Trash2, AlertTriangle, ChevronDown,
  ChevronUp, ThumbsUp, Eye, User
} from 'lucide-react';
import { extractErrorMessage } from '../../utils/errorHandler';

const API = API_BASE;

const CommunityModerationManager = () => {
  const { token } = useAuth();
  const headers = { Authorization: `Bearer ${token}` };
  const [questions, setQuestions] = useState([]);
  const [total, setTotal] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);
  const [replies, setReplies] = useState({});
  const [deleteModal, setDeleteModal] = useState({ open: false, type: null, id: null, title: '' });
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    fetchQuestions();
  }, []);

  const fetchQuestions = async (search = '') => {
    setLoading(true);
    try {
      const params = search ? `?search=${encodeURIComponent(search)}&limit=100` : '?limit=100';
      const res = await axios.get(`${API}/admin/community/questions${params}`, { headers });
      setQuestions(res.data.questions || []);
      setTotal(res.data.total || 0);
    } catch (error) {
      toast.error('Failed to load community questions');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e) => {
    e.preventDefault();
    fetchQuestions(searchQuery);
  };

  const toggleExpand = async (questionId) => {
    if (expandedId === questionId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(questionId);
    if (!replies[questionId]) {
      try {
        const res = await axios.get(`${API}/admin/community/questions/${questionId}/replies`, { headers });
        setReplies(prev => ({ ...prev, [questionId]: res.data.replies || [] }));
      } catch {
        toast.error('Failed to load replies');
      }
    }
  };

  const confirmDelete = async () => {
    const { type, id } = deleteModal;
    setDeleting(true);
    try {
      if (type === 'question') {
        await axios.delete(`${API}/admin/comments/question/${id}`, { headers });
        toast.success('Question and all replies deleted');
      } else {
        await axios.delete(`${API}/admin/comments/reply/${id}`, { headers });
        toast.success('Reply deleted');
      }
      setDeleteModal({ open: false, type: null, id: null, title: '' });
      fetchQuestions(searchQuery);
      // Clear cached replies
      setReplies({});
      setExpandedId(null);
    } catch (error) {
      toast.error(extractErrorMessage(error) || 'Failed to delete');
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <div className="animate-spin rounded-full h-10 w-10 border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="community-moderation">
      <div>
        <h2 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
          <MessageSquare className="h-5 w-5 sm:h-6 sm:w-6" />
          Community Moderation
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Review, search, and delete community questions and replies
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="w-10 h-10 bg-indigo-100 dark:bg-indigo-900 rounded-full flex items-center justify-center">
              <MessageSquare className="h-5 w-5 text-indigo-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{total}</p>
              <p className="text-xs text-muted-foreground">Total Questions</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="w-10 h-10 bg-amber-100 dark:bg-amber-900 rounded-full flex items-center justify-center">
              <AlertTriangle className="h-5 w-5 text-amber-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{questions.filter(q => q.reply_count === 0).length}</p>
              <p className="text-xs text-muted-foreground">Unanswered</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search questions by title, body, or author..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 text-slate-900 dark:text-slate-100"
            data-testid="community-search"
          />
        </div>
        <Button type="submit" variant="outline">
          <Search className="h-4 w-4" />
        </Button>
      </form>

      {/* Questions List */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Questions ({questions.length})</CardTitle>
        </CardHeader>
        <CardContent className="p-3 sm:p-6 pt-0">
          {questions.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              No community questions found
            </p>
          ) : (
            <div className="space-y-3">
              {questions.map((q) => (
                <div key={q.id} className="border rounded-lg overflow-hidden">
                  {/* Question Row */}
                  <div className="flex flex-col sm:flex-row sm:items-center gap-3 p-4 hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <div className="flex-1 min-w-0">
                      <h4 className="font-semibold text-sm truncate text-slate-900 dark:text-slate-100">{q.title}</h4>
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{q.body}</p>
                      <div className="flex flex-wrap gap-2 mt-2 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1"><User className="h-3 w-3" />{q.author_name}</span>
                        <span className="flex items-center gap-1"><ThumbsUp className="h-3 w-3" />{q.upvote_count || 0}</span>
                        <span className="flex items-center gap-1"><MessageSquare className="h-3 w-3" />{q.reply_count || 0} replies</span>
                        <span className="flex items-center gap-1"><Eye className="h-3 w-3" />{q.views || 0} views</span>
                      </div>
                    </div>
                    <div className="flex gap-2 flex-shrink-0">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => toggleExpand(q.id)}
                        data-testid={`expand-question-${q.id}`}
                      >
                        {expandedId === q.id ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => setDeleteModal({ open: true, type: 'question', id: q.id, title: q.title })}
                        data-testid={`delete-question-${q.id}`}
                      >
                        <Trash2 className="h-3.5 w-3.5 mr-1" />
                        Delete
                      </Button>
                    </div>
                  </div>

                  {/* Replies (Expanded) */}
                  {expandedId === q.id && (
                    <div className="border-t bg-slate-50 dark:bg-slate-900/50 p-3 space-y-2">
                      {(replies[q.id] || []).length === 0 ? (
                        <p className="text-xs text-muted-foreground text-center py-3">No replies yet</p>
                      ) : (
                        (replies[q.id] || []).map((r) => (
                          <div key={r.id} className="flex items-start gap-3 p-3 bg-white dark:bg-slate-800 rounded-lg border">
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-medium text-slate-900 dark:text-slate-100">{r.author_name}</p>
                              <p className="text-xs text-muted-foreground mt-1">{r.body}</p>
                              <div className="flex gap-2 mt-1 text-xs text-muted-foreground">
                                <span className="flex items-center gap-1"><ThumbsUp className="h-3 w-3" />{r.upvote_count || 0}</span>
                                {r.is_best && <Badge className="bg-green-600 text-white text-[10px]">Best Answer</Badge>}
                              </div>
                            </div>
                            <Button
                              size="sm"
                              variant="destructive"
                              className="flex-shrink-0 h-7 text-xs"
                              onClick={() => setDeleteModal({ open: true, type: 'reply', id: r.id, title: r.body?.slice(0, 50) })}
                              data-testid={`delete-reply-${r.id}`}
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Modal */}
      {deleteModal.open && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-md border-2 border-red-600" data-testid="delete-comment-modal">
            <CardHeader className="bg-red-50 dark:bg-red-900/20">
              <CardTitle className="text-red-600 flex items-center gap-2 text-base">
                <AlertTriangle className="h-5 w-5" />
                Delete {deleteModal.type === 'question' ? 'Question' : 'Reply'}
              </CardTitle>
              <CardDescription className="text-red-500/80 text-sm">
                {deleteModal.type === 'question'
                  ? 'This will also delete all replies to this question.'
                  : 'This will permanently remove this reply.'}
              </CardDescription>
            </CardHeader>
            <CardContent className="p-5 space-y-4">
              <div className="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                <p className="text-sm text-slate-700 dark:text-slate-300 line-clamp-3">
                  "{deleteModal.title}"
                </p>
              </div>
              <div className="flex gap-2 justify-end">
                <Button variant="outline" onClick={() => setDeleteModal({ open: false, type: null, id: null, title: '' })} data-testid="cancel-delete-comment">
                  Cancel
                </Button>
                <Button variant="destructive" onClick={confirmDelete} disabled={deleting} data-testid="confirm-delete-comment">
                  {deleting ? 'Deleting...' : 'Delete'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default CommunityModerationManager;
