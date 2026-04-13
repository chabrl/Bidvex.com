# BidVex SendGrid Template Upload Guide

## How to Upload

For each `.html` file below:
1. Go to **SendGrid Dashboard → Email API → Dynamic Templates**
2. Click **Create a Dynamic Template**
3. Name it exactly as listed below
4. Click **Add Version → Code Editor**
5. Paste the HTML content from the corresponding `.html` file
6. Set the **Subject** line as listed
7. Click **Save** → note the `d-xxxxx` Template ID
8. Paste the Template ID back into this document

---

## Template Files & Subjects

| # | File | Template Name | Subject Line |
|---|------|--------------|-------------|
| 1 | `01_welcome_en.html` | Welcome EN | `Welcome to the BidVex Ecosystem, {{first_name}}!` |
| 2 | `01_welcome_fr.html` | Bienvenue FR | `Bienvenue dans l'écosystème BidVex, {{first_name}} !` |
| 3 | `02_onboarding_day3_en.html` | Onboarding Day 3 EN | `Have you placed your first bid? | BidVex` |
| 4 | `02_onboarding_day3_fr.html` | Onboarding Jour 3 FR | `Avez-vous placé votre première enchère ? | BidVex` |
| 5 | `03_onboarding_week1_en.html` | Onboarding Week 1 EN | `Your BidVex Quick-Start Guide` |
| 6 | `03_onboarding_week1_fr.html` | Onboarding Semaine 1 FR | `Votre guide de démarrage BidVex` |
| 7 | `04_subscription_pitch_en.html` | Subscription Pitch EN | `20% Off — Unlock the Full BidVex Experience` |
| 8 | `04_subscription_pitch_fr.html` | Offre d'abonnement FR | `20 % de rabais — Débloquez l'expérience BidVex complète` |
| 9 | `05_reengagement_en.html` | Re-engagement EN | `We miss you, {{first_name}}! | BidVex` |
| 10 | `05_reengagement_fr.html` | Réengagement FR | `Vous nous manquez, {{first_name}} ! | BidVex` |
| 11 | `06_reengagement_final_en.html` | Re-engagement Final EN | `Last Chance — Come Back & Save | BidVex` |
| 12 | `06_reengagement_final_fr.html` | Réengagement Final FR | `Dernière chance — Revenez et économisez | BidVex` |
| 13 | `07_subscription_final_reminder_en.html` | Subscription Final Reminder EN | `Your {{plan_name}} subscription expires tomorrow` |
| 14 | `07_subscription_final_reminder_fr.html` | Rappel final abonnement FR | `Votre abonnement {{plan_name}} expire demain` |
| 15 | `08_reactivation_offer_en.html` | Reactivation Offer EN | `Welcome Back — Here's a Gift | BidVex` |
| 16 | `08_reactivation_offer_fr.html` | Offre de réactivation FR | `Bon retour — Voici un cadeau | BidVex` |
| 17 | `09_new_auction_near_you_en.html` | New Auction Near You EN | `New Auction Near You — {{city}} | BidVex` |
| 18 | `09_new_auction_near_you_fr.html` | Nouvelle enchère près de vous FR | `Nouvelle enchère près de chez vous — {{city}} | BidVex` |
| 19 | `10_ending_soon_near_you_en.html` | Ending Soon Near You EN | `Ending in {{hours_remaining}}h — Auction Near You | BidVex` |
| 20 | `10_ending_soon_near_you_fr.html` | Se termine bientôt près de vous FR | `Se termine dans {{hours_remaining}}h — Enchère près de chez vous | BidVex` |

---

## Variables Used Per Template

| Template | Variables (must match `dynamic_data` keys exactly) |
|----------|----------------------------------------------------|
| Welcome | `first_name`, `current_year` |
| Onboarding Day 3 | `first_name`, `current_year` |
| Onboarding Week 1 | `first_name`, `current_year` |
| Subscription Pitch | `first_name`, `coupon_code`, `current_year` |
| Re-engagement | `first_name`, `current_year` |
| Re-engagement Final | `first_name`, `coupon_code`, `current_year` |
| Subscription Final Reminder | `first_name`, `plan_name`, `expiry_date`, `renewal_price`, `current_year` |
| Reactivation Offer | `first_name`, `coupon_code`, `current_year` |
| New Auction Near You | `first_name`, `auction_title`, `auction_id`, `city`, `distance_km`, `start_price`, `auction_end_time`, `current_year` |
| Ending Soon Near You | `first_name`, `auction_title`, `auction_id`, `current_highest_bid`, `hours_remaining`, `distance_km`, `current_year` |

---

## After Upload: Record Template IDs Here

```
# Lifecycle Templates
WELCOME_EN = d-_______________
WELCOME_FR = d-_______________
ONBOARDING_DAY3_EN = d-_______________
ONBOARDING_DAY3_FR = d-_______________
ONBOARDING_WEEK1_EN = d-_______________
ONBOARDING_WEEK1_FR = d-_______________
SUBSCRIPTION_PITCH_EN = d-_______________
SUBSCRIPTION_PITCH_FR = d-_______________
REENGAGEMENT_EN = d-_______________
REENGAGEMENT_FR = d-_______________
REENGAGEMENT_FINAL_EN = d-_______________
REENGAGEMENT_FINAL_FR = d-_______________
SUBSCRIPTION_FINAL_REMINDER_EN = d-_______________
SUBSCRIPTION_FINAL_REMINDER_FR = d-_______________
REACTIVATION_OFFER_EN = d-_______________
REACTIVATION_OFFER_FR = d-_______________

# Geo Templates
NEW_AUCTION_NEAR_YOU_EN = d-_______________
NEW_AUCTION_NEAR_YOU_FR = d-_______________
ENDING_SOON_NEAR_YOU_EN = d-_______________
ENDING_SOON_NEAR_YOU_FR = d-_______________
```
