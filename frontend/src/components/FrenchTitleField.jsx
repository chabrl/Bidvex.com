/**
 * iter299 P0 — Bill 96 French Title input, shared by every listing
 * creation form (marketplace, lots, vehicles, multi-lot, storage).
 *
 * Renders required (red asterisk + Bill 96 helper) when the listing is
 * Quebec-bound, optional otherwise. Shows the inline validation error
 * passed by the parent form.
 */
import React from 'react';
import { Input } from './ui/input';
import { Label } from './ui/label';

export const FrenchTitleField = ({
  value,
  onChange,
  isQuebec = false,
  error = null,
  isFr = false,
  idPrefix = '',
  textarea = false,
}) => {
  const id = `${idPrefix}title-fr`;
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>
        {isQuebec ? (
          <>
            Title (French) / Titre (fran&ccedil;ais) <span className="text-red-600">*</span>
          </>
        ) : (
          <>French Title (optional) / Titre fran&ccedil;ais (optionnel)</>
        )}
      </Label>
      <Input
        id={id}
        name="title_fr"
        value={value || ''}
        onChange={onChange}
        data-testid={`${idPrefix}title-fr-input`}
        placeholder="ex: Table en bois massif, véhicule de travail..."
        aria-invalid={!!error}
        className={error ? 'border-red-500 focus-visible:ring-red-500' : ''}
      />
      {isQuebec && !error && (
        <p className="text-xs text-slate-500" data-testid={`${idPrefix}title-fr-helper`}>
          {isFr
            ? 'Obligatoire pour les annonces québécoises (Loi 96)'
            : 'Required for Quebec listings under Bill 96 / Obligatoire pour les annonces québécoises (Loi 96)'}
        </p>
      )}
      {error && (
        <p className="text-xs font-medium text-red-600" data-testid={`${idPrefix}title-fr-error`}>
          {error}
        </p>
      )}
    </div>
  );
};

export default FrenchTitleField;
