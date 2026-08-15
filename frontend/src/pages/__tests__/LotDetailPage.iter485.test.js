/**
 * iter485 — Lot Detail bid panel "Place Bid" enable/disable regression.
 *
 * Bug: On a lot's bidding panel the user selected a quick-bid amount
 * ($7.00 pill) and checked the payment-methods acknowledgement, but the
 * main "Place Bid" button stayed disabled (gray).
 *
 * Root cause: the three quick-bid pills were wired as one-click bid
 * submitters (calling `handlePlaceBid(amt)` directly) rather than as
 * amount-picker shortcuts that populate the custom-bid input. When the
 * user clicked a pill before ticking the payment-methods checkbox the
 * pill was disabled and did nothing, so `bidAmount` stayed empty. After
 * checking the box the main submit button correctly reported "no
 * amount entered" via `!bidAmount` but the user's mental model was
 * "the pill selected the amount".
 *
 * Fix: quick-bid pills now call `setBidAmount(String(amt))`. The main
 * "Place Bid" button remains the single submission point and is the
 * only element gated on `paymentAck && bidAmount && amount ≥ nextValid`.
 *
 * This test suite verifies:
 *   1. The disabled boolean matches the documented contract for every
 *      combination of the three inputs (paymentAck × bidAmount × amount
 *      vs. nextValidBid).
 *   2. The source of LotDetailPage.jsx wires the pills to setBidAmount
 *      and no longer submits on pill click / gates pills on paymentAck.
 */
/* eslint-disable no-undef */
import fs from 'fs';
import path from 'path';

// Extracted disabled-expression from LotDetailPage.jsx line 658.
// Kept as an isolated pure function so we can lock down the truth
// table without mounting the whole component tree.
function placeBidDisabled({ paymentAck, bidAmount, nextValidBid }) {
  return !paymentAck || !bidAmount || Number(bidAmount) < nextValidBid;
}

describe('iter485 — Place Bid disabled contract', () => {
  const NEXT = 7; // matches the reproduction screenshot

  test('disabled when ack unchecked, even with a valid amount typed', () => {
    expect(placeBidDisabled({ paymentAck: false, bidAmount: '7', nextValidBid: NEXT })).toBe(true);
  });

  test('disabled when amount is empty, even with ack checked', () => {
    expect(placeBidDisabled({ paymentAck: true, bidAmount: '', nextValidBid: NEXT })).toBe(true);
  });

  test('disabled when amount is below next-valid, even with ack checked', () => {
    expect(placeBidDisabled({ paymentAck: true, bidAmount: '6', nextValidBid: NEXT })).toBe(true);
  });

  test('ENABLED when ack is checked, amount is set, and amount ≥ next-valid', () => {
    expect(placeBidDisabled({ paymentAck: true, bidAmount: '7', nextValidBid: NEXT })).toBe(false);
    expect(placeBidDisabled({ paymentAck: true, bidAmount: '12', nextValidBid: NEXT })).toBe(false);
  });

  test('unchecking ack after a valid amount is set re-disables the button', () => {
    // Simulate: user picked pill (bidAmount=7), checked ack (enabled), then unchecks.
    const before = placeBidDisabled({ paymentAck: true, bidAmount: '7', nextValidBid: NEXT });
    const after  = placeBidDisabled({ paymentAck: false, bidAmount: '7', nextValidBid: NEXT });
    expect(before).toBe(false);
    expect(after).toBe(true);
  });

  test('reproduction path: pill click sets amount, then ack tick enables the button', () => {
    // Initial state — nothing selected, ack unchecked.
    let paymentAck = false;
    let bidAmount = '';
    expect(placeBidDisabled({ paymentAck, bidAmount, nextValidBid: NEXT })).toBe(true);

    // User clicks the $7 quick-bid pill → pill's onClick now sets bidAmount.
    // (This is exactly what the fix wires — see the source-level test below.)
    bidAmount = String(7);
    // Ack still unchecked — button still disabled.
    expect(placeBidDisabled({ paymentAck, bidAmount, nextValidBid: NEXT })).toBe(true);

    // User checks the payment-methods acknowledgement.
    paymentAck = true;
    // Both conditions now satisfied — the button MUST become enabled.
    expect(placeBidDisabled({ paymentAck, bidAmount, nextValidBid: NEXT })).toBe(false);
  });
});

describe('iter485 — LotDetailPage.jsx source-level guard against regression', () => {
  const src = fs.readFileSync(
    path.join(__dirname, '..', 'LotDetailPage.jsx'),
    'utf8',
  );

  test('quick-bid pills call setBidAmount (amount picker), not handlePlaceBid', () => {
    // Locate the quick-bid block by its data-testid.
    const quickBidBlockStart = src.indexOf('data-testid="lot-detail-quick-bid"');
    expect(quickBidBlockStart).toBeGreaterThan(-1);
    // Extract a window covering the map(...) callback that renders each pill.
    const window = src.slice(quickBidBlockStart, quickBidBlockStart + 1000);
    expect(window).toMatch(/onClick=\{[^}]*setBidAmount\(String\(amt\)\)/);
    // And explicitly confirm the pills DO NOT submit on click any more.
    expect(window).not.toMatch(/onClick=\{[^}]*handlePlaceBid\(amt\)/);
  });

  test('quick-bid pills are NOT gated on paymentAck (they are pure pickers)', () => {
    const quickBidBlockStart = src.indexOf('data-testid="lot-detail-quick-bid"');
    const window = src.slice(quickBidBlockStart, quickBidBlockStart + 1000);
    expect(window).not.toMatch(/disabled=\{!paymentAck\}/);
  });

  test('main Place Bid button remains gated on ack + amount + next-valid', () => {
    // Guard the exact contract this whole fix relies on.
    expect(src).toMatch(
      /disabled=\{!paymentAck \|\| !bidAmount \|\| Number\(bidAmount\) < nextValidBid\}/,
    );
  });

  test('main Place Bid button is still the sole submitter', () => {
    // The button that actually calls handlePlaceBid must still exist.
    expect(src).toMatch(/onClick=\{\(\) => handlePlaceBid\(Number\(bidAmount\)\)\}/);
    // And there must be exactly ONE such handlePlaceBid submission call now
    // (the three quick-bid submissions were removed by this fix).
    const submits = src.match(/handlePlaceBid\(/g) || [];
    // Only one call-site remaining: the sole submit button below the input.
    // (The function definition is `handlePlaceBid = async (...)` — no direct
    // paren after the identifier, so it isn't counted by this regex.)
    expect(submits.length).toBe(1);
  });
});
