/**
 * iter319 — Country / province / state catalog for global onboarding.
 *
 * Top of the list = the priority recruitment markets (Canada, US).
 * The full ISO list is added below for global applicants. Province /
 * state catalogs are exhaustive — admins will see exactly what the
 * applicant selected without normalisation noise.
 */

export const PRIORITY_COUNTRIES = ['Canada', 'United States'];

export const COUNTRIES = [
  'Canada', 'United States',
  'Australia', 'Belgium', 'Brazil', 'Chile', 'China', 'Colombia',
  'Czech Republic', 'Denmark', 'Egypt', 'Finland', 'France', 'Germany',
  'Greece', 'Hungary', 'India', 'Ireland', 'Israel', 'Italy', 'Japan',
  'Lebanon', 'Luxembourg', 'Mexico', 'Morocco', 'Netherlands',
  'New Zealand', 'Norway', 'Pakistan', 'Peru', 'Philippines', 'Poland',
  'Portugal', 'Romania', 'Saudi Arabia', 'Singapore', 'South Africa',
  'South Korea', 'Spain', 'Sweden', 'Switzerland', 'Thailand', 'Tunisia',
  'Turkey', 'Ukraine', 'United Arab Emirates', 'United Kingdom',
  'Vietnam', 'Other',
];

export const CA_PROVINCES = [
  { code: 'AB', label: 'Alberta' },
  { code: 'BC', label: 'British Columbia' },
  { code: 'MB', label: 'Manitoba' },
  { code: 'NB', label: 'New Brunswick' },
  { code: 'NL', label: 'Newfoundland and Labrador' },
  { code: 'NS', label: 'Nova Scotia' },
  { code: 'NT', label: 'Northwest Territories' },
  { code: 'NU', label: 'Nunavut' },
  { code: 'ON', label: 'Ontario' },
  { code: 'PE', label: 'Prince Edward Island' },
  { code: 'QC', label: 'Quebec / Québec' },
  { code: 'SK', label: 'Saskatchewan' },
  { code: 'YT', label: 'Yukon' },
];

export const US_STATES = [
  { code: 'AL', label: 'Alabama' }, { code: 'AK', label: 'Alaska' },
  { code: 'AZ', label: 'Arizona' }, { code: 'AR', label: 'Arkansas' },
  { code: 'CA', label: 'California' }, { code: 'CO', label: 'Colorado' },
  { code: 'CT', label: 'Connecticut' }, { code: 'DE', label: 'Delaware' },
  { code: 'FL', label: 'Florida' }, { code: 'GA', label: 'Georgia' },
  { code: 'HI', label: 'Hawaii' }, { code: 'ID', label: 'Idaho' },
  { code: 'IL', label: 'Illinois' }, { code: 'IN', label: 'Indiana' },
  { code: 'IA', label: 'Iowa' }, { code: 'KS', label: 'Kansas' },
  { code: 'KY', label: 'Kentucky' }, { code: 'LA', label: 'Louisiana' },
  { code: 'ME', label: 'Maine' }, { code: 'MD', label: 'Maryland' },
  { code: 'MA', label: 'Massachusetts' }, { code: 'MI', label: 'Michigan' },
  { code: 'MN', label: 'Minnesota' }, { code: 'MS', label: 'Mississippi' },
  { code: 'MO', label: 'Missouri' }, { code: 'MT', label: 'Montana' },
  { code: 'NE', label: 'Nebraska' }, { code: 'NV', label: 'Nevada' },
  { code: 'NH', label: 'New Hampshire' }, { code: 'NJ', label: 'New Jersey' },
  { code: 'NM', label: 'New Mexico' }, { code: 'NY', label: 'New York' },
  { code: 'NC', label: 'North Carolina' }, { code: 'ND', label: 'North Dakota' },
  { code: 'OH', label: 'Ohio' }, { code: 'OK', label: 'Oklahoma' },
  { code: 'OR', label: 'Oregon' }, { code: 'PA', label: 'Pennsylvania' },
  { code: 'RI', label: 'Rhode Island' }, { code: 'SC', label: 'South Carolina' },
  { code: 'SD', label: 'South Dakota' }, { code: 'TN', label: 'Tennessee' },
  { code: 'TX', label: 'Texas' }, { code: 'UT', label: 'Utah' },
  { code: 'VT', label: 'Vermont' }, { code: 'VA', label: 'Virginia' },
  { code: 'WA', label: 'Washington' }, { code: 'WV', label: 'West Virginia' },
  { code: 'WI', label: 'Wisconsin' }, { code: 'WY', label: 'Wyoming' },
  { code: 'DC', label: 'District of Columbia' },
];
