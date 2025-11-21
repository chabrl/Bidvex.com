# SendGrid Templates - Bilingual Support Implementation Guide

Complete guide for adding French (FR) translations to your SendGrid email templates.

---

## Current Status

✅ **Framework Ready**: Backend supports `language` parameter  
✅ **Variable Included**: All emails send `language` and `current_year`  
⚠️ **Content Pending**: Templates only have English content  

---

## Implementation Options

### Option 1: Single Template with Conditional Logic (Recommended)

**Pros:**
- Single template ID per category
- Easier to maintain
- Automatic language switching
- No code changes needed

**Cons:**
- More complex template design
- Longer template files

**Best For**: Most use cases

### Option 2: Separate Templates per Language

**Pros:**
- Simpler template design
- Complete control over translations
- Easier for translators

**Cons:**
- Duplicate template IDs
- More templates to manage
- Requires code changes

**Best For**: Complex templates with significant layout differences

---

## Option 1: Single Template with Conditional Logic

### Step 1: Understanding Handlebars Conditionals

SendGrid uses Handlebars syntax for dynamic content:

```handlebars
{{#if (eq language "fr")}}
  Contenu en français
{{else}}
  English content
{{/if}}
```

### Step 2: Example - Welcome Email

**Current English-Only Template:**

```html
<h1>Welcome to BidVex!</h1>
<p>Hi {{ first_name }},</p>
<p>Thank you for joining BidVex. We're excited to have you as part of our auction community!</p>
<a href="{{ login_url }}">Login to Your Account</a>
```

**Bilingual Template with Conditionals:**

```html
{{#if (eq language "fr")}}
  <h1>Bienvenue sur BidVex!</h1>
  <p>Bonjour {{ first_name }},</p>
  <p>Merci de vous être inscrit sur BidVex. Nous sommes ravis de vous compter parmi notre communauté d'enchères!</p>
  <a href="{{ login_url }}">Connexion à votre compte</a>
{{else}}
  <h1>Welcome to BidVex!</h1>
  <p>Hi {{ first_name }},</p>
  <p>Thank you for joining BidVex. We're excited to have you as part of our auction community!</p>
  <a href="{{ login_url }}">Login to Your Account</a>
{{/if}}
```

### Step 3: Complete Example with All Elements

```html
<!DOCTYPE html>
<html>
<head>
  <style>
    /* Your CSS styles here */
  </style>
</head>
<body>
  {{#if (eq language "fr")}}
    <!-- French Version -->
    <div class="header">
      <img src="https://bidvex.com/logo-fr.png" alt="BidVex">
    </div>
    
    <div class="content">
      <h1>Bienvenue sur BidVex!</h1>
      
      <p>Bonjour {{ first_name }},</p>
      
      <p>Merci de vous être inscrit sur BidVex en tant que compte <strong>{{ account_type }}</strong>. Nous sommes ravis de vous compter parmi notre communauté d'enchères!</p>
      
      <div class="cta">
        <a href="{{ login_url }}" class="button">Connexion à votre compte</a>
      </div>
      
      <p>Découvrez nos enchères actuelles:</p>
      <a href="{{ explore_url }}">Parcourir les enchères</a>
      
      <p>Si vous avez des questions, n'hésitez pas à nous contacter.</p>
    </div>
    
    <div class="footer">
      <p>&copy; {{ current_year }} BidVex. Tous droits réservés.</p>
    </div>
    
  {{else}}
    <!-- English Version -->
    <div class="header">
      <img src="https://bidvex.com/logo-en.png" alt="BidVex">
    </div>
    
    <div class="content">
      <h1>Welcome to BidVex!</h1>
      
      <p>Hi {{ first_name }},</p>
      
      <p>Thank you for joining BidVex as a <strong>{{ account_type }}</strong> account. We're excited to have you as part of our auction community!</p>
      
      <div class="cta">
        <a href="{{ login_url }}" class="button">Login to Your Account</a>
      </div>
      
      <p>Explore our current auctions:</p>
      <a href="{{ explore_url }}">Browse Auctions</a>
      
      <p>If you have any questions, feel free to contact us.</p>
    </div>
    
    <div class="footer">
      <p>&copy; {{ current_year }} BidVex. All rights reserved.</p>
    </div>
  {{/if}}
</body>
</html>
```

### Step 4: Translation Checklist

For each template, translate:

**Text Content:**
- ✅ Subject lines
- ✅ Headings (h1, h2, h3)
- ✅ Body paragraphs
- ✅ Button text
- ✅ Link text
- ✅ Footer text
- ✅ Legal disclaimers

**Email-Specific Text:**
- ✅ Call-to-action buttons
- ✅ Instructions
- ✅ Greeting/closing
- ✅ Error messages (if any)

**Don't Translate:**
- ❌ Variable names ({{ first_name }})
- ❌ URLs (unless you have FR-specific pages)
- ❌ Technical IDs
- ❌ Email addresses

---

## Translation Examples for All Templates

### 1. Authentication Templates

#### Welcome Email
```
EN: Welcome to BidVex!
FR: Bienvenue sur BidVex!

EN: Thank you for joining
FR: Merci de vous être inscrit

EN: Login to Your Account
FR: Connexion à votre compte
```

#### Password Reset
```
EN: Reset Your Password
FR: Réinitialisez votre mot de passe

EN: Click the button below to reset your password
FR: Cliquez sur le bouton ci-dessous pour réinitialiser votre mot de passe

EN: Reset Password
FR: Réinitialiser le mot de passe

EN: This link expires in {{ expires_in_hours }} hour(s)
FR: Ce lien expire dans {{ expires_in_hours }} heure(s)
```

### 2. Bidding Templates

#### Bid Placed
```
EN: Bid Confirmation
FR: Confirmation d'enchère

EN: Your bid of {{ currency }} {{ bid_amount }} has been placed
FR: Votre enchère de {{ bid_amount }} {{ currency }} a été placée

EN: Current High Bid
FR: Enchère la plus élevée

EN: Auction ends on {{ auction_end_date }}
FR: L'enchère se termine le {{ auction_end_date }}
```

#### Outbid
```
EN: You've Been Outbid!
FR: Vous avez été surenchéri!

EN: Someone placed a higher bid
FR: Quelqu'un a placé une enchère plus élevée

EN: Place New Bid
FR: Placer une nouvelle enchère
```

#### Bid Won
```
EN: Congratulations! You Won the Auction
FR: Félicitations! Vous avez remporté l'enchère

EN: Your winning bid
FR: Votre enchère gagnante

EN: Proceed to Payment
FR: Procéder au paiement
```

### 3. Auction Updates

#### Ending Soon
```
EN: Auction Ending Soon!
FR: L'enchère se termine bientôt!

EN: Only {{ time_remaining }} left
FR: Plus que {{ time_remaining }}

EN: Place Your Bid Now
FR: Enchérissez maintenant
```

#### Auction Started
```
EN: Auction Now Live!
FR: L'enchère est maintenant en cours!

EN: The auction you're watching has started
FR: L'enchère que vous suivez a commencé

EN: Bid Now
FR: Enchérir maintenant
```

### 4. Seller Notifications

#### New Bid Received
```
EN: New Bid Received!
FR: Nouvelle enchère reçue!

EN: {{ bidder_name }} placed a bid on your item
FR: {{ bidder_name }} a placé une enchère sur votre article

EN: Total bids: {{ total_bids }}
FR: Total des enchères: {{ total_bids }}
```

#### Item Sold
```
EN: Your Item Sold!
FR: Votre article a été vendu!

EN: Final price
FR: Prix final

EN: View Details
FR: Voir les détails
```

### 5. Financial Templates

#### Invoice
```
EN: Invoice for Your Purchase
FR: Facture pour votre achat

EN: Invoice Number
FR: Numéro de facture

EN: Total Amount
FR: Montant total

EN: Payment Method
FR: Mode de paiement

EN: Download Invoice
FR: Télécharger la facture
```

#### Payment Received
```
EN: Payment Received
FR: Paiement reçu

EN: Thank you for your payment
FR: Merci pour votre paiement

EN: Transaction ID
FR: ID de transaction
```

### 6. Communication

#### New Message
```
EN: You have a new message
FR: Vous avez un nouveau message

EN: {{ sender_name }} sent you a message
FR: {{ sender_name }} vous a envoyé un message

EN: View Message
FR: Voir le message

EN: Reply
FR: Répondre
```

### 7. Admin

#### Report Received
```
EN: New Report Received
FR: Nouveau signalement reçu

EN: Report Type
FR: Type de signalement

EN: Review Report
FR: Examiner le signalement
```

---

## Implementation Steps

### Step 1: Access SendGrid Templates

1. Go to: https://app.sendgrid.com/
2. Navigate to: **Email API → Dynamic Templates**
3. Select template to edit

### Step 2: Edit Template

1. Click **Edit** on the template
2. Select the version to edit
3. Click **Code Editor** (top right)

### Step 3: Add Bilingual Content

1. Wrap existing content in `{{else}}` block
2. Add French content in `{{#if (eq language "fr")}}` block
3. Ensure all variables are in both versions
4. Test with preview feature

### Step 4: Test Template

**Test with English:**
```json
{
  "first_name": "John",
  "language": "en",
  "current_year": "2025"
}
```

**Test with French:**
```json
{
  "first_name": "Jean",
  "language": "fr",
  "current_year": "2025"
}
```

### Step 5: Save and Activate

1. Click **Save Template**
2. Template is now bilingual!
3. No code changes needed

---

## Option 2: Separate Templates per Language

If you prefer separate templates:

### Step 1: Duplicate Templates

1. Create French versions of all 7 templates in SendGrid
2. Name them with `-FR` suffix (e.g., "Authentication - FR")

### Step 2: Update Code

Modify `email_templates.py`:

```python
class EmailTemplates:
    """SendGrid Dynamic Template IDs for BidVex emails."""
    
    # English Templates
    WELCOME_EN = 'd-e0ee403fbd8646db8011339cf2eeac30'
    BID_PLACED_EN = 'd-13806757fbd24818b24bc520074ea979'
    # ... other English templates
    
    # French Templates
    WELCOME_FR = 'd-NEW-FRENCH-TEMPLATE-ID-HERE'
    BID_PLACED_FR = 'd-NEW-FRENCH-TEMPLATE-ID-HERE'
    # ... other French templates
    
    @staticmethod
    def get_template(template_name: str, language: str = 'en'):
        """Get template ID based on language."""
        suffix = '_FR' if language == 'fr' else '_EN'
        template_attr = f"{template_name}{suffix}"
        return getattr(EmailTemplates, template_attr)
```

### Step 3: Update Helper Functions

```python
async def send_welcome_email(email_service, user: Dict, language: str = 'en'):
    """Send welcome email in specified language."""
    template_id = EmailTemplates.get_template('WELCOME', language)
    
    return await email_service.send_email(
        to=user['email'],
        template_id=template_id,
        dynamic_data=EmailDataBuilder.welcome_email(user),
        language=language
    )
```

---

## Testing Bilingual Templates

### Test Script

```python
import asyncio
from services.email_service import get_email_service
from config.email_templates import send_welcome_email

async def test_bilingual():
    email_service = get_email_service()
    
    user = {
        'name': 'Test User',
        'email': 'your-email@example.com',
        'account_type': 'personal'
    }
    
    # Test English
    print("Sending English email...")
    result_en = await send_welcome_email(email_service, user, 'en')
    print(f"EN: {result_en}")
    
    await asyncio.sleep(2)
    
    # Test French
    print("Sending French email...")
    result_fr = await send_welcome_email(email_service, user, 'fr')
    print(f"FR: {result_fr}")

asyncio.run(test_bilingual())
```

### Verification Checklist

When testing French emails, verify:

- ✅ Subject line in French
- ✅ All body text in French
- ✅ Button text in French
- ✅ Footer text in French
- ✅ Date/time formatting appropriate for locale
- ✅ Currency symbols correct ($ → $)
- ✅ No English text visible
- ✅ Special characters (é, è, à, ç) display correctly
- ✅ Links work correctly

---

## Best Practices

### 1. Maintain Consistency

- Use same French terminology across all templates
- Keep tone and voice consistent
- Match formality level (vous vs tu)

### 2. Professional Translation

- Don't rely solely on machine translation
- Have native French speaker review
- Consider Quebec French vs France French differences

### 3. Cultural Adaptation

- Adapt examples and references for French audience
- Use appropriate date formats (DD/MM/YYYY)
- Consider cultural nuances in messaging

### 4. Variable Handling

Always include variables in both language blocks:
```handlebars
{{#if (eq language "fr")}}
  Bonjour {{ first_name }},
{{else}}
  Hi {{ first_name }},
{{/if}}
```

### 5. Testing

- Test with real French users
- Check on multiple email clients
- Verify mobile display
- Test special characters

---

## Common Pitfalls

### ❌ Don't: Mix Languages

```handlebars
<!-- BAD -->
{{#if (eq language "fr")}}
  Bonjour {{ first_name }}, welcome to BidVex!
{{/if}}
```

### ✅ Do: Keep Languages Separate

```handlebars
<!-- GOOD -->
{{#if (eq language "fr")}}
  Bonjour {{ first_name }}, bienvenue sur BidVex!
{{else}}
  Hi {{ first_name }}, welcome to BidVex!
{{/if}}
```

### ❌ Don't: Forget Footer

```handlebars
<!-- BAD - Footer only in English -->
{{#if (eq language "fr")}}
  <!-- French content -->
{{else}}
  <!-- English content -->
{{/if}}
<footer>Copyright 2025</footer>
```

### ✅ Do: Translate Everything

```handlebars
<!-- GOOD -->
{{#if (eq language "fr")}}
  <!-- French content -->
  <footer>&copy; {{ current_year }} Tous droits réservés</footer>
{{else}}
  <!-- English content -->
  <footer>&copy; {{ current_year }} All rights reserved</footer>
{{/if}}
```

---

## French Translations Reference

### Common Email Phrases

| English | French |
|---------|--------|
| Welcome | Bienvenue |
| Thank you | Merci |
| Hello | Bonjour |
| Regards | Cordialement |
| Click here | Cliquez ici |
| View details | Voir les détails |
| Contact us | Contactez-nous |
| Unsubscribe | Se désabonner |
| Privacy Policy | Politique de confidentialité |
| Terms of Service | Conditions d'utilisation |

### BidVex-Specific Terms

| English | French |
|---------|--------|
| Auction | Enchère |
| Bid | Enchère / Offre |
| Listing | Annonce |
| Seller | Vendeur |
| Buyer | Acheteur |
| Current Bid | Enchère actuelle |
| Starting Price | Prix de départ |
| Reserve Price | Prix de réserve |
| Buy Now | Acheter maintenant |
| Place Bid | Enchérir |

---

## Next Steps

1. ✅ **Choose Implementation Option** (Option 1 recommended)
2. ✅ **Gather Translations** (hire translator or use reference above)
3. ✅ **Update Templates** (15-30 min per template)
4. ✅ **Test Each Template** (5 min per template)
5. ✅ **Deploy to Production** (immediate, no code changes)
6. ✅ **Monitor User Feedback** (ongoing)

---

**Estimated Time**: 4-6 hours for all 7 templates  
**Difficulty**: Medium  
**Impact**: High (better user experience for French speakers)

**Last Updated**: November 21, 2025  
**Status**: Ready for Implementation
