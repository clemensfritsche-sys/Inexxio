'use client';

import { useState, useEffect } from 'react';
import { Users, Shield, Mail, MapPin, Briefcase, Building2, ShoppingBag, Truck, FileText } from 'lucide-react';
import { api } from '@/lib/api';
import type { UniversalObject, UserProfile, UserPlatformRole } from '@/types';

const ROLE_LABELS: Record<UserPlatformRole, string> = {
  admin: 'Administrator',
  employee: 'Mitarbeiter',
  supplier: 'Lieferant',
  customer: 'Kunde',
};

const ROLE_COLORS: Record<UserPlatformRole, { bg: string; color: string }> = {
  admin: { bg: '#FEE2E2', color: '#B91C1C' },
  employee: { bg: '#DBEAFE', color: '#1D4ED8' },
  supplier: { bg: '#D1FAE5', color: '#065F46' },
  customer: { bg: '#F3F4F6', color: '#374151' },
};

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <dt style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>
        {label}
      </dt>
      <dd style={{ fontSize: 14, color: value ? '#0F172A' : '#cbd5e1', fontStyle: value ? 'normal' : 'italic' }}>
        {value || '—'}
      </dd>
    </div>
  );
}

function Section({ title, icon: Icon, children }: { title: string; icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <Icon style={{ width: 14, height: 14, color: '#64748b' }} />
        <h4 style={{ fontSize: 12, fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em', margin: 0 }}>
          {title}
        </h4>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 24px' }}>
        {children}
      </div>
    </div>
  );
}

interface UserDetailProps {
  object: UniversalObject;
  currentUserRole?: string;
  onRoleChanged?: () => void;
}

export function UserDetail({ object, currentUserRole, onRoleChanged }: UserDetailProps) {
  const [tab, setTab] = useState<'profil' | 'rolle'>('profil');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [saved, setSaved] = useState(false);

  const profile = object.data as UserProfile;
  const isAdmin = currentUserRole === 'admin';

  const [roleValue, setRoleValue] = useState<UserPlatformRole>(profile?.role ?? 'customer');

  useEffect(() => {
    setRoleValue(profile?.role ?? 'customer');
    setSaveError('');
    setSaved(false);
  }, [profile?.id, profile?.role]);

  const fullName = [profile?.first_name, profile?.last_name].filter(Boolean).join(' ') || profile?.display_name || profile?.email || '—';
  const roleColors = ROLE_COLORS[roleValue] ?? ROLE_COLORS.customer;

  const role = profile?.role ?? 'customer';
  const isBusiness = profile?.is_business || role === 'supplier';
  const isEmployee = role === 'employee' || role === 'admin';
  const isCustomerOrSupplier = role === 'customer' || role === 'supplier';

  const hasAddress = !!(profile?.address_line1 || profile?.city);
  const hasCompanyInfo = !!(profile?.company_name || profile?.uid_number || profile?.vat_number || profile?.trade_register_nr);
  const hasB2cShipping = !!(profile?.ship_b2c_address_line1 || profile?.ship_b2c_city);
  const hasB2bShipping = !!(profile?.ship_b2b_address_line1 || profile?.ship_b2b_city);
  const hasInvoice = !!(profile?.invoice_address_line1 || profile?.invoice_city || profile?.invoice_email || profile?.invoice_vat_id);
  const hasShopInfo = !!(profile?.customer_group || profile?.credit_limit != null || profile?.accepts_marketing != null);

  async function handleRoleSave() {
    if (!profile?.id) return;
    setSaving(true);
    setSaveError('');
    setSaved(false);
    try {
      await api.updateUserRole(profile.id, roleValue);
      setSaved(true);
      onRoleChanged?.();
      setTimeout(() => setSaved(false), 2000);
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '20px 24px 0', borderBottom: '1px solid #E2E8F0', background: '#fff' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, marginBottom: 16 }}>
          <div style={{
            width: 44, height: 44, borderRadius: '50%', flexShrink: 0,
            background: profile?.photo_url ? 'transparent' : '#E51A14',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16, fontWeight: 700, color: '#fff', overflow: 'hidden',
          }}>
            {profile?.photo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={profile.photo_url} alt={fullName} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            ) : (
              (profile?.first_name?.[0] || profile?.email?.[0] || 'U').toUpperCase()
            )}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#94a3b8' }}>
                {object.number}
              </span>
            </div>
            <h2 style={{ fontSize: 17, fontWeight: 700, color: '#0F172A', margin: 0, lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {fullName}
            </h2>
            <p style={{ fontSize: 13, color: '#64748b', margin: '2px 0 0' }}>{profile?.email}</p>
          </div>
          <div style={{
            padding: '3px 10px',
            borderRadius: 20,
            fontSize: 12,
            fontWeight: 600,
            background: roleColors.bg,
            color: roleColors.color,
            flexShrink: 0,
          }}>
            {ROLE_LABELS[profile?.role ?? 'customer']}
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: 0 }}>
          {(['profil', 'rolle'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                padding: '8px 16px',
                fontSize: 13,
                fontWeight: 600,
                background: 'none',
                border: 'none',
                borderBottom: tab === t ? '2px solid #E51A14' : '2px solid transparent',
                color: tab === t ? '#E51A14' : '#64748b',
                cursor: 'pointer',
                transition: 'color 0.15s',
                marginBottom: -1,
              }}
            >
              {t === 'profil' ? 'Profil' : 'Rolle & Rechte'}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
        {tab === 'profil' && (
          <>
            {/* Kontakt */}
            <Section title="Kontakt" icon={Mail}>
              <Field label="Vorname" value={profile?.first_name} />
              <Field label="Nachname" value={profile?.last_name} />
              <Field label="E-Mail" value={profile?.email} />
              <Field label="Anrede" value={profile?.salutation} />
              <Field label="Telefon" value={profile?.phone} />
              <Field label="Sprache" value={profile?.language?.toUpperCase()} />
              {role === 'customer' && (
                <Field label="Kontotyp" value={isBusiness ? 'Geschäftskunde (B2B)' : 'Privatkunde (B2C)'} />
              )}
            </Section>

            {/* Adresse */}
            {hasAddress && (
              <Section title="Adresse" icon={MapPin}>
                <Field label="Strasse" value={[profile?.address_line1, profile?.address_line2].filter(Boolean).join(', ')} />
                <Field label="Ort" value={[profile?.postal_code, profile?.city].filter(Boolean).join(' ')} />
                <Field label="Kanton" value={profile?.state_canton} />
                <Field label="Land" value={profile?.country} />
              </Section>
            )}

            {/* Firmendaten (B2B customers & suppliers) */}
            {(isBusiness || hasCompanyInfo) && (
              <Section title="Firma / Geschäft" icon={Building2}>
                <Field label="Firmenname" value={profile?.company_name} />
                <Field label="Rechtsform" value={profile?.company_legal_form} />
                <Field label="UID-Nummer" value={profile?.uid_number} />
                <Field label="MWST-Nummer" value={profile?.vat_number} />
                <Field label="Handelsregister-Nr." value={profile?.trade_register_nr} />
                <Field label="Kanton HR" value={profile?.trade_register_canton} />
                <Field label="Website" value={profile?.company_website} />
                <Field label="Rechnungs-E-Mail Firma" value={profile?.company_billing_email} />
              </Section>
            )}

            {/* Anstellung (employees & admins only) */}
            {isEmployee && (
              <Section title="Anstellung" icon={Briefcase}>
                <Field label="Abteilung" value={profile?.department} />
                <Field label="Funktion" value={profile?.job_title} />
                <Field label="Eintrittsdatum" value={profile?.employment_start_date ? new Date(profile.employment_start_date).toLocaleDateString('de-CH') : null} />
                <Field label="Pensum" value={profile?.weekly_hours ? `${profile.weekly_hours}h/Woche` : null} />
              </Section>
            )}

            {/* Lieferadressen (customers & suppliers) */}
            {isCustomerOrSupplier && (isBusiness ? hasB2bShipping : hasB2cShipping) && (
              <Section title={isBusiness ? 'Lieferadresse (Firma)' : 'Lieferadresse (Privat)'} icon={Truck}>
                {isBusiness ? (
                  <>
                    <Field label="Firmenname" value={profile?.ship_b2b_company} />
                    <Field label="Ansprechperson" value={profile?.ship_b2b_contact} />
                    <Field label="Strasse" value={[profile?.ship_b2b_address_line1, profile?.ship_b2b_address_line2].filter(Boolean).join(', ')} />
                    <Field label="Ort" value={[profile?.ship_b2b_postal_code, profile?.ship_b2b_city].filter(Boolean).join(' ')} />
                    <Field label="Land" value={profile?.ship_b2b_country} />
                  </>
                ) : (
                  <>
                    <Field label="Vorname" value={profile?.ship_b2c_first_name} />
                    <Field label="Nachname" value={profile?.ship_b2c_last_name} />
                    <Field label="Strasse" value={[profile?.ship_b2c_address_line1, profile?.ship_b2c_address_line2].filter(Boolean).join(', ')} />
                    <Field label="Ort" value={[profile?.ship_b2c_postal_code, profile?.ship_b2c_city].filter(Boolean).join(' ')} />
                    <Field label="Land" value={profile?.ship_b2c_country} />
                  </>
                )}
              </Section>
            )}

            {/* Rechnungsadresse (customers & suppliers) */}
            {isCustomerOrSupplier && hasInvoice && (
              <Section title="Rechnungsadresse" icon={FileText}>
                {isBusiness && <Field label="Firmenname" value={profile?.invoice_company} />}
                <Field label="Name" value={[profile?.invoice_first_name, profile?.invoice_last_name].filter(Boolean).join(' ') || null} />
                <Field label="Strasse" value={[profile?.invoice_address_line1, profile?.invoice_address_line2].filter(Boolean).join(', ')} />
                <Field label="Ort" value={[profile?.invoice_postal_code, profile?.invoice_city].filter(Boolean).join(' ')} />
                <Field label="Land" value={profile?.invoice_country} />
                <Field label="Rechnungs-E-Mail" value={profile?.invoice_email} />
                {isBusiness && <Field label="USt-ID / MWST-Nr." value={profile?.invoice_vat_id} />}
              </Section>
            )}

            {/* Online Shop / CRM (customers) */}
            {role === 'customer' && hasShopInfo && (
              <Section title="Online Shop / CRM" icon={ShoppingBag}>
                <Field label="Kundengruppe" value={profile?.customer_group} />
                <Field label="Kreditlimit (CHF)" value={profile?.credit_limit != null ? String(profile.credit_limit) : null} />
                <Field label="Marketing" value={profile?.accepts_marketing ? 'Einverstanden' : 'Nicht einverstanden'} />
                <Field label="AGB akzeptiert" value={profile?.terms_accepted_at ? new Date(profile.terms_accepted_at).toLocaleDateString('de-CH') : 'Automatisch beim Login'} />
              </Section>
            )}

          </>
        )}

        {tab === 'rolle' && (
          <div>
            <div style={{ marginBottom: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <Shield style={{ width: 14, height: 14, color: '#64748b' }} />
                <h4 style={{ fontSize: 12, fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em', margin: 0 }}>
                  Plattformrolle
                </h4>
              </div>

              {isAdmin ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <select
                    value={roleValue}
                    onChange={(e) => setRoleValue(e.target.value as UserPlatformRole)}
                    style={{
                      padding: '9px 12px',
                      borderRadius: 8,
                      border: '1px solid #E2E8F0',
                      fontSize: 14,
                      color: '#0F172A',
                      background: '#fff',
                      cursor: 'pointer',
                      outline: 'none',
                    }}
                  >
                    <option value="customer">Kunde</option>
                    <option value="supplier">Lieferant</option>
                    <option value="employee">Mitarbeiter</option>
                    <option value="admin">Administrator</option>
                  </select>

                  {saveError && (
                    <p style={{ fontSize: 13, color: '#DC2626', margin: 0 }}>{saveError}</p>
                  )}

                  <button
                    onClick={handleRoleSave}
                    disabled={saving || roleValue === (profile?.role ?? 'customer')}
                    style={{
                      padding: '9px 18px',
                      borderRadius: 8,
                      border: 'none',
                      background: '#E51A14',
                      color: '#fff',
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: saving || roleValue === (profile?.role ?? 'customer') ? 'not-allowed' : 'pointer',
                      opacity: saving || roleValue === (profile?.role ?? 'customer') ? 0.5 : 1,
                      alignSelf: 'flex-start',
                    }}
                  >
                    {saving ? 'Speichert…' : saved ? 'Gespeichert ✓' : 'Rolle speichern'}
                  </button>
                </div>
              ) : (
                <div style={{ padding: '12px 16px', borderRadius: 8, background: '#F8FAFC', border: '1px solid #E2E8F0' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{
                      padding: '3px 10px',
                      borderRadius: 20,
                      fontSize: 12,
                      fontWeight: 600,
                      background: ROLE_COLORS[profile?.role ?? 'customer'].bg,
                      color: ROLE_COLORS[profile?.role ?? 'customer'].color,
                    }}>
                      {ROLE_LABELS[profile?.role ?? 'customer']}
                    </div>
                    <span style={{ fontSize: 13, color: '#64748b' }}>
                      Rollenänderungen sind nur Admins vorbehalten.
                    </span>
                  </div>
                </div>
              )}
            </div>

            <div style={{ padding: '12px 16px', borderRadius: 8, background: '#FFFBEB', border: '1px solid #FDE68A' }}>
              <p style={{ fontSize: 12, color: '#92400E', margin: 0, lineHeight: 1.5 }}>
                <strong>Rollenübersicht:</strong> Kunden und Lieferanten haben keinen ERP-Zugang. Mitarbeiter und Admins können das ERP verwenden. Nur Admins können Rollen und Einstellungen verwalten.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div style={{ padding: '12px 24px', borderTop: '1px solid #E2E8F0', background: '#F8FAFC' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Users style={{ width: 13, height: 13, color: '#94a3b8' }} />
            <span style={{ fontSize: 12, color: '#94a3b8' }}>Benutzer</span>
          </div>
          <span style={{ fontSize: 12, color: '#94a3b8' }}>·</span>
          <span style={{ fontSize: 12, color: '#94a3b8' }}>
            Registriert: {profile?.created_at ? new Date(profile.created_at).toLocaleDateString('de-CH') : '—'}
          </span>
          {profile?.last_login_at && (
            <>
              <span style={{ fontSize: 12, color: '#94a3b8' }}>·</span>
              <span style={{ fontSize: 12, color: '#94a3b8' }}>
                Letzte Anmeldung: {new Date(profile.last_login_at).toLocaleDateString('de-CH')}
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
