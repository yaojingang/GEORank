'use client';

import {useEffect, useMemo, useState} from 'react';
import {useTranslations} from 'next-intl';

import type {AdminSettingsResponse} from '@georank/api-sdk';
import {getAdminSettings, updateAdminSettings} from '@georank/api-sdk';

type AdminSettingsProps = {
  token: string;
};

type FormState = Record<string, string | boolean>;

type FieldDefinition = {
  key: string;
  type: 'text' | 'textarea' | 'password' | 'number' | 'boolean';
  placeholder?: string;
};

const settingSections: Array<{
  key: string;
  titleKey: string;
  descriptionKey: string;
  fields: FieldDefinition[];
}> = [
  {
    key: 'basic',
    titleKey: 'basicTitle',
    descriptionKey: 'basicDescription',
    fields: [
      {key: 'site_name', type: 'text'},
      {key: 'site_description', type: 'textarea'},
      {key: 'default_language', type: 'text'},
      {key: 'timezone', type: 'text'}
    ]
  },
  {
    key: 'llm',
    titleKey: 'llmTitle',
    descriptionKey: 'llmDescription',
    fields: [
      {key: 'llm_base_url', type: 'text'},
      {key: 'llm_model', type: 'text'},
      {key: 'llm_fallback_model', type: 'text'},
      {key: 'codex_base_url', type: 'text'},
      {key: 'codex_model', type: 'text'},
      {key: 'embedding_base_url', type: 'text'},
      {key: 'embedding_model', type: 'text'},
      {key: 'embedding_dimensions', type: 'number'}
    ]
  },
  {
    key: 'api_keys',
    titleKey: 'apiKeysTitle',
    descriptionKey: 'apiKeysDescription',
    fields: [
      {key: 'llm_api_key', type: 'password'},
      {key: 'codex_api_key', type: 'password'},
      {key: 'embedding_api_key', type: 'password'},
      {key: 'google_search_api_key', type: 'password'},
      {key: 'openai_api_key', type: 'password'}
    ]
  },
  {
    key: 'geo_engine',
    titleKey: 'geoEngineTitle',
    descriptionKey: 'geoEngineDescription',
    fields: [
      {key: 'geo_auto_score', type: 'boolean'},
      {key: 'geo_rescan_days', type: 'number'},
      {key: 'geo_score_public', type: 'boolean'},
      {key: 'geo_score_version', type: 'text'}
    ]
  }
];

function toDisplayValue(value: unknown): string | boolean {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return String(value);
  return String(value ?? '');
}

export function AdminSettings({token}: AdminSettingsProps) {
  const t = useTranslations('admin.settings');
  const [settings, setSettings] = useState<AdminSettingsResponse | null>(null);
  const [formState, setFormState] = useState<FormState>({});
  const [loading, setLoading] = useState(true);
  const [actionMessage, setActionMessage] = useState('');
  const [error, setError] = useState('');

  async function loadSettings() {
    setLoading(true);
    setError('');
    try {
      const payload = await getAdminSettings(token);
      setSettings(payload);
      const nextState: FormState = {};
      Object.entries(payload).forEach(([key, item]) => {
        nextState[key] = toDisplayValue(item.value);
      });
      setFormState(nextState);
    } catch (loadError: unknown) {
      setError(loadError instanceof Error ? loadError.message : t('loadFailed'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSettings();
  }, [token]);

  const topStats = useMemo(() => {
    const values = settings ? Object.values(settings) : [];
    const secretCount = values.filter((item) => item.category === 'api_keys').length;
    const publicCount = values.filter((item) => item.is_public).length;
    return [
      {label: t('totalSettings'), value: values.length, tone: 'brand'},
      {label: t('publicSettings'), value: publicCount, tone: 'success'},
      {label: t('secretKeys'), value: secretCount, tone: 'warning'},
      {label: t('groups'), value: settingSections.length, tone: 'brand'}
    ];
  }, [settings, t]);

  async function handleSave() {
    if (!settings) return;
    setActionMessage('');
    try {
      const payload = Object.fromEntries(
        Object.entries(settings).map(([key, item]) => {
          const currentValue = formState[key];
          const originalValue = item.value;
          let value: string | number | boolean = currentValue as string | number | boolean;

          if (typeof originalValue === 'boolean') {
            value = Boolean(currentValue);
          } else if (typeof originalValue === 'number') {
            value = Number(currentValue || 0);
          } else {
            value = String(currentValue ?? '');
          }

          return [
            key,
            {
              value,
              category: item.category,
              is_public: item.is_public
            }
          ];
        })
      );
      await updateAdminSettings(token, payload);
      setActionMessage(t('savedMessage'));
      await loadSettings();
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('saveFailed'));
    }
  }

  return (
    <main className="admin-page">
      <section className="admin-page__hero">
        <div>
          <p className="admin-page__eyebrow">Settings</p>
          <h1>{t('title')}</h1>
          <p>{t('subtitle')}</p>
        </div>
        <div className="admin-detail-list__actions">
          {actionMessage ? <div className="admin-page__hero-chip">{actionMessage}</div> : null}
          <button className="admin-button admin-button--ghost" onClick={loadSettings}>
            {t('refresh')}
          </button>
          <button className="admin-button admin-button--primary" onClick={handleSave}>
            {t('saveSettings')}
          </button>
        </div>
      </section>

      <section className="admin-stat-grid admin-stat-grid--compact">
        {topStats.map((stat) => (
          <article className="admin-stat-card" key={stat.label}>
            <p className="admin-stat-card__label">{stat.label}</p>
            <div className={`admin-stat-card__value admin-tone--${stat.tone}`}>{stat.value}</div>
          </article>
        ))}
      </section>

      {error ? <div className="admin-inline-error">{error}</div> : null}

      {loading ? (
        <div className="admin-panel">{t('loading')}</div>
      ) : (
        <section className="admin-settings-grid">
          {settingSections.map((section) => (
            <article className="admin-panel" key={section.key}>
              <div className="admin-panel__header">
                <div>
                  <p className="admin-panel__eyebrow">{section.key}</p>
                  <h2>{t(`sections.${section.titleKey}`)}</h2>
                  <p>{t(`sections.${section.descriptionKey}`)}</p>
                </div>
              </div>

              <div className="admin-form-stack">
                {section.fields.map((field) => {
                  const currentValue = formState[field.key];
                  const config = settings?.[field.key];
                  const label = (
                    <span>
                      {t(`fields.${field.key}`)}
                      {config ? (
                        <span className="admin-field__meta">
                          {config.is_public ? t('public') : t('internal')} · {config.category}
                        </span>
                      ) : null}
                    </span>
                  );

                  if (field.type === 'boolean') {
                    return (
                      <label className="admin-checkbox-row" key={field.key}>
                        {label}
                        <input
                          type="checkbox"
                          checked={Boolean(currentValue)}
                          onChange={(event) =>
                            setFormState((current) => ({...current, [field.key]: event.target.checked}))
                          }
                        />
                      </label>
                    );
                  }

                  if (field.type === 'textarea') {
                    return (
                      <label className="admin-field" key={field.key}>
                        {label}
                        <textarea
                          className="admin-textarea"
                          value={String(currentValue ?? '')}
                          onChange={(event) =>
                            setFormState((current) => ({...current, [field.key]: event.target.value}))
                          }
                        />
                      </label>
                    );
                  }

                  return (
                    <label className="admin-field" key={field.key}>
                      {label}
                      <input
                        className="admin-input"
                        type={field.type === 'password' ? 'password' : field.type === 'number' ? 'number' : 'text'}
                        value={String(currentValue ?? '')}
                        onChange={(event) =>
                          setFormState((current) => ({...current, [field.key]: event.target.value}))
                        }
                        placeholder={field.placeholder}
                      />
                    </label>
                  );
                })}
              </div>
            </article>
          ))}
        </section>
      )}
    </main>
  );
}
