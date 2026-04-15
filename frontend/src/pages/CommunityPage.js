import API_BASE from '../config';
import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { toast } from 'sonner';
import {
  MessageCircle, ThumbsUp, Eye, Clock, Search,
  ChevronLeft, ArrowRight, Send, CheckCircle2, Award, Plus,
} from 'lucide-react';

const API = API_BASE;

const timeAgo = (dateStr) => {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
};

export default function CommunityPage() {
  const { t, i18n } = useTranslation();
  const { user, token } = useAuth();
  const fr = i18n.language?.startsWith('fr');

  const [questions, setQuestions] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('newest');
  const [selectedQuestion, setSelectedQuestion] = useState(null);
  const [showNewForm, setShowNewForm] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newBody, setNewBody] = useState('');
  const [replyBody, setReplyBody] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchQuestions = useCallback(async () => {
    setLoading(true);
    try {
      const params = { limit: 20, skip: 0, sort };
      if (search.trim()) params.search = search.trim();
      const res = await axios.get(`${API}/community/questions`, { params });
      setQuestions(res.data.questions);
      setTotal(res.data.total);
    } catch {
      toast.error(fr ? 'Erreur de chargement' : 'Failed to load questions');
    } finally {
      setLoading(false);
    }
  }, [sort, search, fr]);

  useEffect(() => { fetchQuestions(); }, [fetchQuestions]);

  const openQuestion = async (id) => {
    try {
      const res = await axios.get(`${API}/community/questions/${id}`);
      setSelectedQuestion(res.data);
    } catch {
      toast.error(fr ? 'Question introuvable' : 'Question not found');
    }
  };

  const handleNewQuestion = async (e) => {
    e.preventDefault();
    if (!user) { toast.error(fr ? 'Connectez-vous pour poster' : 'Login to post'); return; }
    setSubmitting(true);
    try {
      const res = await axios.post(`${API}/community/questions`, { title: newTitle, body: newBody }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setShowNewForm(false);
      setNewTitle(''); setNewBody('');
      toast.success(fr ? 'Question publiée !' : 'Question posted!');
      fetchQuestions();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error');
    } finally { setSubmitting(false); }
  };

  const handleReply = async (e) => {
    e.preventDefault();
    if (!user) { toast.error(fr ? 'Connectez-vous pour répondre' : 'Login to reply'); return; }
    setSubmitting(true);
    try {
      await axios.post(`${API}/community/questions/${selectedQuestion.id}/replies`, { body: replyBody }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setReplyBody('');
      toast.success(fr ? 'Réponse envoyée !' : 'Reply posted!');
      openQuestion(selectedQuestion.id);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error');
    } finally { setSubmitting(false); }
  };

  const handleUpvoteQuestion = async (qId) => {
    if (!user) { toast.error(fr ? 'Connectez-vous' : 'Login to upvote'); return; }
    try {
      const res = await axios.post(`${API}/community/questions/${qId}/upvote`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (selectedQuestion?.id === qId) {
        setSelectedQuestion(prev => ({ ...prev, upvote_count: res.data.upvote_count }));
      }
      setQuestions(prev => prev.map(q => q.id === qId ? { ...q, upvote_count: res.data.upvote_count } : q));
    } catch { /* silent */ }
  };

  const handleUpvoteReply = async (rId) => {
    if (!user) return;
    try {
      const res = await axios.post(`${API}/community/replies/${rId}/upvote`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (selectedQuestion) {
        setSelectedQuestion(prev => ({
          ...prev,
          replies: prev.replies.map(r => r.id === rId ? { ...r, upvote_count: res.data.upvote_count } : r),
        }));
      }
    } catch { /* silent */ }
  };

  const handleMarkBest = async (replyId) => {
    try {
      await axios.post(`${API}/community/questions/${selectedQuestion.id}/best-reply`, { reply_id: replyId }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success(fr ? 'Meilleure réponse marquée' : 'Best answer marked');
      openQuestion(selectedQuestion.id);
    } catch { /* silent */ }
  };

  // ── Question Detail View ──
  if (selectedQuestion) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950" data-testid="community-page">
        <div className="max-w-3xl mx-auto px-4 py-8">
          <button
            onClick={() => setSelectedQuestion(null)}
            className="flex items-center gap-1 text-sm text-slate-500 hover:text-primary mb-6 transition-colors"
            data-testid="back-to-questions"
          >
            <ChevronLeft className="h-4 w-4" /> {fr ? 'Retour aux questions' : 'Back to questions'}
          </button>

          <Card className="mb-6" data-testid="question-detail">
            <CardContent className="p-6">
              <h1 className="text-xl font-bold mb-2">{selectedQuestion.title}</h1>
              <div className="flex items-center gap-3 text-xs text-slate-500 mb-4">
                <span data-testid="question-author">{selectedQuestion.author_name}</span>
                <span>{timeAgo(selectedQuestion.created_at)}</span>
                <span className="flex items-center gap-1"><Eye className="h-3 w-3" />{selectedQuestion.views}</span>
              </div>
              <p className="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap leading-relaxed">{selectedQuestion.body}</p>
              <div className="flex items-center gap-3 mt-4 pt-4 border-t">
                <button
                  onClick={() => handleUpvoteQuestion(selectedQuestion.id)}
                  className="flex items-center gap-1 text-sm text-slate-500 hover:text-blue-600 transition-colors"
                  data-testid="upvote-question"
                >
                  <ThumbsUp className="h-4 w-4" /> {selectedQuestion.upvote_count || 0}
                </button>
                <span className="flex items-center gap-1 text-sm text-slate-500">
                  <MessageCircle className="h-4 w-4" /> {selectedQuestion.replies?.length || 0} {fr ? 'réponses' : 'replies'}
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Replies */}
          <h3 className="font-semibold text-sm mb-3">{fr ? 'Réponses' : 'Replies'} ({selectedQuestion.replies?.length || 0})</h3>
          <div className="space-y-3 mb-6">
            {(selectedQuestion.replies || []).map(reply => (
              <Card key={reply.id} className={reply.is_best ? 'border-2 border-green-500' : ''} data-testid={`reply-${reply.id}`}>
                <CardContent className="p-4">
                  {reply.is_best && (
                    <Badge className="bg-green-100 text-green-700 mb-2 text-xs" data-testid="best-answer-badge">
                      <Award className="h-3 w-3 mr-1" /> {fr ? 'Meilleure réponse' : 'Best Answer'}
                    </Badge>
                  )}
                  <p className="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap leading-relaxed">{reply.body}</p>
                  <div className="flex items-center justify-between mt-3 pt-3 border-t">
                    <div className="flex items-center gap-3 text-xs text-slate-500">
                      <span>{reply.author_name}</span>
                      <span>{timeAgo(reply.created_at)}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleUpvoteReply(reply.id)}
                        className="flex items-center gap-1 text-xs text-slate-400 hover:text-blue-600 transition-colors"
                        data-testid={`upvote-reply-${reply.id}`}
                      >
                        <ThumbsUp className="h-3.5 w-3.5" /> {reply.upvote_count || 0}
                      </button>
                      {user?.id === selectedQuestion.author_id && !reply.is_best && (
                        <button
                          onClick={() => handleMarkBest(reply.id)}
                          className="text-xs text-green-600 hover:underline flex items-center gap-1"
                          data-testid={`mark-best-${reply.id}`}
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" /> {fr ? 'Meilleure' : 'Best'}
                        </button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Reply Form */}
          {user ? (
            <form onSubmit={handleReply} className="space-y-3" data-testid="reply-form">
              <Textarea
                value={replyBody}
                onChange={(e) => setReplyBody(e.target.value)}
                placeholder={fr ? 'Écrivez votre réponse...' : 'Write your reply...'}
                rows={3}
                required
                data-testid="reply-input"
              />
              <Button type="submit" disabled={submitting} className="gap-2" data-testid="submit-reply">
                <Send className="h-4 w-4" /> {submitting ? '...' : fr ? 'Répondre' : 'Reply'}
              </Button>
            </form>
          ) : (
            <p className="text-sm text-slate-500 text-center py-4">
              {fr ? 'Connectez-vous pour répondre' : 'Login to reply'}
            </p>
          )}
        </div>
      </div>
    );
  }

  // ── Questions List View ──
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950" data-testid="community-page">
      {/* Hero */}
      <section className="py-12 px-4 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
        <div className="max-w-3xl mx-auto text-center">
          <h1 className="text-3xl sm:text-4xl font-bold mb-2">
            {fr ? 'Communauté BidVex' : 'BidVex Community'}
          </h1>
          <p className="text-slate-300 text-sm">
            {fr ? 'Posez des questions, partagez vos connaissances et aidez les autres.' : 'Ask questions, share knowledge, and help others.'}
          </p>
        </div>
      </section>

      <div className="max-w-3xl mx-auto px-4 py-8">
        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={fr ? 'Rechercher...' : 'Search questions...'}
              className="pl-9"
              data-testid="community-search"
            />
          </div>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="px-3 py-2 border rounded-md bg-background text-sm"
            data-testid="community-sort"
          >
            <option value="newest">{fr ? 'Plus récent' : 'Newest'}</option>
            <option value="most_replies">{fr ? 'Plus de réponses' : 'Most Replies'}</option>
            <option value="most_upvoted">{fr ? 'Plus votées' : 'Most Upvoted'}</option>
          </select>
          {user && (
            <Button onClick={() => setShowNewForm(true)} className="gap-2 shrink-0" data-testid="new-question-btn">
              <Plus className="h-4 w-4" /> {fr ? 'Poser une question' : 'Ask Question'}
            </Button>
          )}
        </div>

        {/* New Question Form */}
        {showNewForm && (
          <Card className="mb-6 border-2 border-primary/30" data-testid="new-question-form">
            <CardContent className="p-5">
              <form onSubmit={handleNewQuestion} className="space-y-3">
                <h3 className="font-semibold text-sm">{fr ? 'Nouvelle question' : 'New Question'}</h3>
                <Input
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder={fr ? 'Titre de votre question' : 'Question title'}
                  required
                  data-testid="question-title-input"
                />
                <Textarea
                  value={newBody}
                  onChange={(e) => setNewBody(e.target.value)}
                  placeholder={fr ? 'Décrivez votre question en détail...' : 'Describe your question in detail...'}
                  rows={4}
                  required
                  data-testid="question-body-input"
                />
                <div className="flex gap-2">
                  <Button type="submit" disabled={submitting} data-testid="submit-question">
                    {submitting ? '...' : fr ? 'Publier' : 'Post Question'}
                  </Button>
                  <Button type="button" variant="outline" onClick={() => setShowNewForm(false)}>
                    {fr ? 'Annuler' : 'Cancel'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {/* Questions */}
        {loading ? (
          <div className="text-center py-12 text-slate-400">{fr ? 'Chargement...' : 'Loading...'}</div>
        ) : questions.length === 0 ? (
          <div className="text-center py-12" data-testid="no-questions">
            <MessageCircle className="h-12 w-12 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500">{fr ? 'Aucune question pour le moment.' : 'No questions yet.'}</p>
            {user && (
              <Button onClick={() => setShowNewForm(true)} className="mt-4 gap-2" data-testid="first-question-btn">
                <Plus className="h-4 w-4" /> {fr ? 'Soyez le premier !' : 'Be the first to ask!'}
              </Button>
            )}
          </div>
        ) : (
          <div className="space-y-3" data-testid="questions-list">
            {questions.map(q => (
              <Card
                key={q.id}
                className="cursor-pointer hover:border-primary/40 transition-colors"
                onClick={() => openQuestion(q.id)}
                data-testid={`question-card-${q.id}`}
              >
                <CardContent className="p-4">
                  <div className="flex gap-4">
                    {/* Upvote column */}
                    <div className="flex flex-col items-center gap-1 shrink-0 pt-1">
                      <button
                        onClick={(e) => { e.stopPropagation(); handleUpvoteQuestion(q.id); }}
                        className="text-slate-400 hover:text-blue-600 transition-colors"
                      >
                        <ThumbsUp className="h-4 w-4" />
                      </button>
                      <span className="text-xs font-semibold">{q.upvote_count || 0}</span>
                    </div>
                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-sm mb-1 truncate">{q.title}</h3>
                      <p className="text-xs text-slate-500 line-clamp-2">{q.body}</p>
                      <div className="flex items-center gap-3 mt-2 text-xs text-slate-400">
                        <span>{q.author_name}</span>
                        <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{timeAgo(q.created_at)}</span>
                        <span className="flex items-center gap-1"><MessageCircle className="h-3 w-3" />{q.reply_count || 0}</span>
                        <span className="flex items-center gap-1"><Eye className="h-3 w-3" />{q.views || 0}</span>
                        {q.best_reply_id && (
                          <Badge className="bg-green-100 text-green-700 text-[10px]">
                            <CheckCircle2 className="h-2.5 w-2.5 mr-0.5" /> {fr ? 'Résolu' : 'Answered'}
                          </Badge>
                        )}
                      </div>
                    </div>
                    <ArrowRight className="h-4 w-4 text-slate-300 self-center shrink-0" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Total count */}
        {total > 0 && (
          <p className="text-center text-xs text-slate-400 mt-6">
            {total} {fr ? 'questions au total' : 'total questions'}
          </p>
        )}
      </div>
    </div>
  );
}
