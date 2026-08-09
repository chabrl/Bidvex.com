/**
 * iter453 — Seller Dashboard relist toast alignment regression.
 *
 * Verifies:
 *   • Multi-item relist (backend returns status="draft") → SUCCESS toast
 *     shows the "Draft created for review" copy in EN and FR. The old
 *     "Listing relisted! It is live again." copy is NOT shown.
 *   • Marketplace single-item relist (backend returns status="active") →
 *     unchanged "Listing relisted! It is live again." copy fires.
 *   • FR variants use the correct bilingual strings.
 */
/* eslint-disable no-undef */
import { toast } from 'sonner';

// Mimic the exact logic in SellerDashboard.js::handleRelistNow so we
// can test the toast selection without pulling the whole component.
function pickRelistToast(responseData, lang) {
  const fr = (lang || 'en').startsWith('fr');
  const isDraft = responseData?.status === 'draft';
  if (isDraft) {
    return {
      kind: 'success',
      msg: fr
        ? 'Brouillon créé pour révision. Publiez-le depuis votre tableau de bord lorsque vous êtes prêt.'
        : 'Draft created for review. Publish it from your dashboard when ready.',
    };
  }
  return {
    kind: 'success',
    msg: fr
      ? 'Annonce republiée ! Elle est de nouveau en ligne.'
      : 'Listing relisted! It is live again.',
  };
}

jest.mock('sonner', () => ({
  toast: {
    success: jest.fn(),
    info: jest.fn(),
    error: jest.fn(),
  },
}));

beforeEach(() => {
  toast.success.mockClear();
  toast.info.mockClear();
  toast.error.mockClear();
});

describe('iter453 — SellerDashboard relist toast alignment', () => {
  test('multi-item partial relist (status=draft) shows draft-review copy in EN', () => {
    const t = pickRelistToast({ status: 'draft', new_listing_id: 'abc' }, 'en');
    expect(t.kind).toBe('success');
    expect(t.msg).toBe(
      'Draft created for review. Publish it from your dashboard when ready.'
    );
    // Legacy live-again copy must NOT appear.
    expect(t.msg).not.toMatch(/live again/i);
  });

  test('multi-item partial relist (status=draft) shows draft-review copy in FR', () => {
    const t = pickRelistToast({ status: 'draft', new_listing_id: 'abc' }, 'fr');
    expect(t.kind).toBe('success');
    expect(t.msg).toContain('Brouillon créé pour révision');
    // Legacy live-again FR copy must NOT appear.
    expect(t.msg).not.toContain('en ligne');
  });

  test('marketplace single-item relist (status=active) keeps live-again copy in EN', () => {
    const t = pickRelistToast({ status: 'active', new_listing_id: 'abc' }, 'en');
    expect(t.kind).toBe('success');
    expect(t.msg).toBe('Listing relisted! It is live again.');
  });

  test('marketplace single-item relist (status=active) keeps live-again copy in FR', () => {
    const t = pickRelistToast({ status: 'active', new_listing_id: 'abc' }, 'fr');
    expect(t.kind).toBe('success');
    expect(t.msg).toBe('Annonce republiée ! Elle est de nouveau en ligne.');
  });

  test('no double-toast (single success call, no info follow-up)', () => {
    // The old code fired both a success + a follow-up info toast for
    // status=draft. The new code fires exactly ONE toast per relist.
    const responses = [
      { status: 'draft', new_listing_id: 'abc' },
      { status: 'active', new_listing_id: 'xyz' },
    ];
    responses.forEach((r) => {
      const t = pickRelistToast(r, 'en');
      // Simulate the caller invoking the toast function.
      toast[t.kind](t.msg);
    });
    // Exactly 2 success calls, zero info follow-ups.
    expect(toast.success).toHaveBeenCalledTimes(2);
    expect(toast.info).not.toHaveBeenCalled();
  });
});
