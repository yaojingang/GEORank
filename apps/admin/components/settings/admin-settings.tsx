'use client';

import type {FormEvent} from 'react';
import {useCallback, useEffect, useMemo, useState} from 'react';
import {useTranslations} from 'next-intl';

import type {
  AdminApiPolicy,
  AdminApiPolicyResponse,
  AdminFrontendModules,
  AdminLLMProvider,
  AdminLLMProviders,
  AdminSettingsResponse,
  AdminSettingsUpdatePayload,
  AdminSolutionChannels
} from '@georank/api-sdk';
import {
  deleteAdminSetting,
  getAdminApiPolicy,
  getAdminFrontendModules,
  getAdminLLMProviders,
  getAdminSettings,
  getAdminSolutionChannels,
  resetAdminApiPolicy,
  resetAdminFrontendModules,
  resetAdminSolutionChannels,
  testAdminLLMProvider,
  updateAdminApiPolicy,
  updateAdminFrontendModules,
  updateAdminLLMProviders,
  updateAdminSettings,
  updateAdminSolutionChannels
} from '@georank/api-sdk';

type AdminSettingsProps = {
  token: string;
};

type FormState = Record<string, string | boolean>;

type SettingsLoadSection = 'settings' | 'providers' | 'channels' | 'modules' | 'policy';

const settingsLoadSections: SettingsLoadSection[] = [
  'settings',
  'providers',
  'channels',
  'modules',
  'policy'
];

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
  if (typeof value === 'object' && value !== null) return JSON.stringify(value, null, 2);
  return String(value ?? '');
}

function parseSettingValue(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return '';
  if (trimmed === 'true') return true;
  if (trimmed === 'false') return false;
  if (/^-?\d+(\.\d+)?$/.test(trimmed)) return Number(trimmed);
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) return JSON.parse(trimmed);
  return value;
}

function parseList(value: string) {
  return value
    .split(/[\n,，]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function AdminSettings({token}: AdminSettingsProps) {
  const t = useTranslations('admin.settings');
  const actions = useTranslations('common.actions');
  const [settings, setSettings] = useState<AdminSettingsResponse | null>(null);
  const [formState, setFormState] = useState<FormState>({});
  const [llmProviders, setLlmProviders] = useState<AdminLLMProviders | null>(null);
  const [solutionChannels, setSolutionChannels] = useState<AdminSolutionChannels | null>(null);
  const [frontendModules, setFrontendModules] = useState<AdminFrontendModules | null>(null);
  const [apiPolicy, setApiPolicy] = useState<AdminApiPolicyResponse | null>(null);
  const [apiPolicyDraft, setApiPolicyDraft] = useState('{}');
  const [newSettingKey, setNewSettingKey] = useState('');
  const [newSettingCategory, setNewSettingCategory] = useState('basic');
  const [newSettingValue, setNewSettingValue] = useState('');
  const [newSettingPublic, setNewSettingPublic] = useState(false);
  const [loading, setLoading] = useState(true);
  const [actionMessage, setActionMessage] = useState('');
  const [loadErrors, setLoadErrors] = useState<Partial<Record<SettingsLoadSection, string>>>({});

  const parsedApiPolicy = useMemo<AdminApiPolicy | null>(() => {
    try {
      return JSON.parse(apiPolicyDraft) as AdminApiPolicy;
    } catch {
      return null;
    }
  }, [apiPolicyDraft]);

  function updateApiPolicyField<K extends keyof AdminApiPolicy>(key: K, value: AdminApiPolicy[K]) {
    if (!parsedApiPolicy) return;
    setApiPolicyDraft(JSON.stringify({...parsedApiPolicy, [key]: value}, null, 2));
  }

  function updateGuidanceField(key: keyof AdminApiPolicy['byok_guidance'], value: string) {
    if (!parsedApiPolicy) return;
    setApiPolicyDraft(JSON.stringify({
      ...parsedApiPolicy,
      byok_guidance: {...parsedApiPolicy.byok_guidance, [key]: value}
    }, null, 2));
  }

  const loadSettings = useCallback(async (sections: SettingsLoadSection[] = settingsLoadSections) => {
    if (sections.length === settingsLoadSections.length) setLoading(true);
    const loaders: Record<SettingsLoadSection, () => Promise<unknown>> = {
      settings: () => getAdminSettings(token),
      providers: () => getAdminLLMProviders(token),
      channels: () => getAdminSolutionChannels(token),
      modules: () => getAdminFrontendModules(token),
      policy: () => getAdminApiPolicy(token)
    };
    const results = await Promise.allSettled(sections.map((section) => loaders[section]()));
    const nextErrors: Partial<Record<SettingsLoadSection, string>> = {};

    results.forEach((result, index) => {
      const section = sections[index];
      if (result.status === 'rejected') {
        nextErrors[section] = result.reason instanceof Error ? result.reason.message : t('loadFailed');
        return;
      }
      if (section === 'settings') {
        const payload = result.value as AdminSettingsResponse;
        setSettings(payload);
        setFormState(
          Object.fromEntries(
            Object.entries(payload).map(([key, item]) => [key, toDisplayValue(item.value)])
          )
        );
      } else if (section === 'providers') {
        setLlmProviders(result.value as AdminLLMProviders);
      } else if (section === 'channels') {
        setSolutionChannels(result.value as AdminSolutionChannels);
      } else if (section === 'modules') {
        setFrontendModules(result.value as AdminFrontendModules);
      } else {
        const payload = result.value as AdminApiPolicyResponse;
        setApiPolicy(payload);
        setApiPolicyDraft(JSON.stringify(payload.policy || {}, null, 2));
      }
    });

    setLoadErrors((current) => {
      const next = {...current};
      sections.forEach((section) => delete next[section]);
      return {...next, ...nextErrors};
    });
    setLoading(false);
  }, [t, token]);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  const topStats = useMemo(() => {
    const values = settings ? Object.values(settings) : [];
    const secretCount = values.filter((item) => item.category === 'api_keys').length;
    const publicCount = values.filter((item) => item.is_public).length;
    return [
      {label: t('totalSettings'), value: values.length, tone: 'brand'},
      {label: t('publicSettings'), value: publicCount, tone: 'success'},
      {label: t('secretKeys'), value: secretCount, tone: 'warning'},
      {label: t('llmProviders'), value: llmProviders?.provider_count || 0, tone: 'brand'}
    ];
  }, [settings, llmProviders, t]);

  async function handleSave() {
    if (!settings) return;
    setActionMessage('');
    try {
      const editableKeys = new Set(
        settingSections.flatMap((section) => section.fields.map((field) => field.key))
      );
      const payload = Object.fromEntries(
        Object.entries(settings).filter(([key]) => editableKeys.has(key)).map(([key, item]) => {
          const currentValue = formState[key];
          const originalValue = item.value;
          let value: string | number | boolean | Record<string, unknown> = currentValue as
            | string
            | number
            | boolean
            | Record<string, unknown>;

          if (typeof originalValue === 'boolean') {
            value = Boolean(currentValue);
          } else if (typeof originalValue === 'number') {
            value = Number(currentValue || 0);
          } else if (typeof originalValue === 'object' && originalValue !== null) {
            value = JSON.parse(String(currentValue || '{}'));
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
      await updateAdminSettings(token, payload as AdminSettingsUpdatePayload);
      setActionMessage(t('savedMessage'));
      await loadSettings();
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('saveFailed'));
    }
  }

  async function handleCreateSetting(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!newSettingKey.trim()) return;
    setActionMessage('');
    try {
      await updateAdminSettings(token, {
        [newSettingKey.trim()]: {
          value: parseSettingValue(newSettingValue),
          category: newSettingCategory.trim() || 'basic',
          is_public: newSettingPublic
        }
      });
      setActionMessage(t('settingCreated'));
      setNewSettingKey('');
      setNewSettingValue('');
      setNewSettingPublic(false);
      await loadSettings();
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('settingCreateFailed'));
    }
  }

  async function handleDeleteSetting(key: string) {
    if (!window.confirm(t('deleteSettingConfirm', {key}))) return;
    setActionMessage('');
    try {
      await deleteAdminSetting(token, key);
      setActionMessage(t('settingDeleted'));
      await loadSettings();
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('settingDeleteFailed'));
    }
  }

  async function handleSaveLLMProviders() {
    if (!llmProviders) return;
    setActionMessage('');
    try {
      const saved = await updateAdminLLMProviders(token, {
        strategy: llmProviders.strategy,
        providers: llmProviders.providers
      });
      setLlmProviders(saved);
      setActionMessage(t('llmSaved'));
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('llmSaveFailed'));
    }
  }

  async function handleTestProvider(provider: AdminLLMProvider, index: number) {
    setActionMessage('');
    try {
      const result = await testAdminLLMProvider(token, {provider});
      setActionMessage(`${provider.name || index + 1}: ${result.message}`);
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('llmTestFailed'));
    }
  }

  async function handleSaveChannels() {
    if (!solutionChannels) return;
    setActionMessage('');
    try {
      const saved = await updateAdminSolutionChannels(token, {
        default_channel_key: solutionChannels.default_channel_key,
        channels: solutionChannels.channels
      });
      setSolutionChannels(saved);
      setActionMessage(t('channelsSaved'));
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('channelsSaveFailed'));
    }
  }

  async function handleResetChannels() {
    setActionMessage('');
    try {
      const saved = await resetAdminSolutionChannels(token);
      setSolutionChannels(saved);
      setActionMessage(t('channelsReset'));
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('channelsResetFailed'));
    }
  }

  async function handleSaveFrontendModules() {
    if (!frontendModules) return;
    setActionMessage('');
    try {
      const saved = await updateAdminFrontendModules(token, {
        default_module: frontendModules.default_module,
        modules: frontendModules.modules
      });
      setFrontendModules(saved);
      setActionMessage(t('modulesSaved'));
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('modulesSaveFailed'));
    }
  }

  async function handleResetFrontendModules() {
    setActionMessage('');
    try {
      const saved = await resetAdminFrontendModules(token);
      setFrontendModules(saved);
      setActionMessage(t('modulesReset'));
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('modulesResetFailed'));
    }
  }

  async function handleSaveApiPolicy() {
    setActionMessage('');
    try {
      const saved = await updateAdminApiPolicy(token, JSON.parse(apiPolicyDraft));
      setApiPolicy((current) => (current ? {...current, policy: saved.policy} : current));
      setApiPolicyDraft(JSON.stringify(saved.policy, null, 2));
      setActionMessage(t('policySaved'));
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('policySaveFailed'));
    }
  }

  async function handleResetApiPolicy() {
    setActionMessage('');
    try {
      const saved = await resetAdminApiPolicy(token);
      setApiPolicy((current) => (current ? {...current, policy: saved.policy} : current));
      setApiPolicyDraft(JSON.stringify(saved.policy, null, 2));
      setActionMessage(t('policyReset'));
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('policyResetFailed'));
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
          <button
            className="admin-button admin-button--ghost"
            onClick={() => void loadSettings()}
            type="button"
          >
            {t('refresh')}
          </button>
          <button className="admin-button admin-button--primary" onClick={handleSave} type="button">
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

      {Object.entries(loadErrors).map(([section, message]) => (
        <div className="admin-inline-error" key={section}>
          <span>{section}: {message}</span>{' '}
          <button
            className="admin-button admin-button--ghost admin-button--small"
            onClick={() => void loadSettings([section as SettingsLoadSection])}
            type="button"
          >
            {actions('retry')}
          </button>
        </div>
      ))}

      {loading ? (
        <div className="admin-panel">{t('loading')}</div>
      ) : (
        <div className="admin-stack">
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

          <section className="admin-panel">
            <div className="admin-panel__header">
              <div>
                <p className="admin-panel__eyebrow">LLM</p>
                <h2>{t('llmProviderTitle')}</h2>
              </div>
              <div className="admin-company-detail__actions">
                <button
                  className="admin-button admin-button--ghost admin-button--small"
                  type="button"
                  onClick={() =>
                    setLlmProviders((current) =>
                      current
                        ? {
                            ...current,
                            providers: [
                              ...current.providers,
                              {
                                id: `provider-${current.providers.length + 1}`,
                                name: '',
                                base_url: '',
                                model: '',
                                api_key: '',
                                enabled: true,
                                priority: current.providers.length + 1
                              }
                            ]
                          }
                        : current
                    )
                  }
                >
                  {t('addProvider')}
                </button>
                <button className="admin-button admin-button--primary admin-button--small" onClick={handleSaveLLMProviders}>
                  {actions('save')}
                </button>
              </div>
            </div>
            <div className="admin-form-stack">
              <label className="admin-field">
                <span>{t('strategy')}</span>
                <select
                  className="admin-select"
                  value={llmProviders?.strategy || 'failover'}
                  onChange={(event) =>
                    setLlmProviders((current) => (current ? {...current, strategy: event.target.value} : current))
                  }
                >
                  <option value="failover">failover</option>
                  <option value="round_robin">round_robin</option>
                </select>
              </label>
              {llmProviders?.providers.map((provider, index) => (
                <div className="admin-detail-list__item" key={`${provider.id || 'new'}-${index}`}>
                  <div className="admin-form-grid admin-form-grid--two">
                    {(['id', 'name', 'base_url', 'model', 'api_key', 'priority'] as const).map((field) => (
                      <label className="admin-field" key={field}>
                        <span>{t(`providerFields.${field}`)}</span>
                        <input
                          className="admin-input"
                          type={field === 'api_key' ? 'password' : field === 'priority' ? 'number' : 'text'}
                          value={String(provider[field] ?? '')}
                          onChange={(event) =>
                            setLlmProviders((current) =>
                              current
                                ? {
                                    ...current,
                                    providers: current.providers.map((item, itemIndex) =>
                                      itemIndex === index
                                        ? {
                                            ...item,
                                            [field]: field === 'priority' ? Number(event.target.value || 1) : event.target.value
                                          }
                                        : item
                                    )
                                  }
                                : current
                            )
                          }
                        />
                      </label>
                    ))}
                  </div>
                  <label className="admin-checkbox-row">
                    <span>{t('enabled')}</span>
                    <input
                      checked={provider.enabled}
                      type="checkbox"
                      onChange={(event) =>
                        setLlmProviders((current) =>
                          current
                            ? {
                                ...current,
                                providers: current.providers.map((item, itemIndex) =>
                                  itemIndex === index ? {...item, enabled: event.target.checked} : item
                                )
                              }
                            : current
                        )
                      }
                    />
                  </label>
                  <div className="admin-company-detail__actions">
                    <button
                      className="admin-button admin-button--ghost admin-button--small"
                      type="button"
                      onClick={() => handleTestProvider(provider, index)}
                    >
                      {t('testProvider')}
                    </button>
                    <button
                      className="admin-button admin-button--danger admin-button--small"
                      type="button"
                      disabled={(llmProviders?.providers.length || 0) <= 1}
                      onClick={() =>
                        setLlmProviders((current) =>
                          current
                            ? {...current, providers: current.providers.filter((_, itemIndex) => itemIndex !== index)}
                            : current
                        )
                      }
                    >
                      {actions('delete')}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="admin-panel">
            <div className="admin-panel__header">
              <div>
                <p className="admin-panel__eyebrow">Solutions</p>
                <h2>{t('channelsTitle')}</h2>
              </div>
              <div className="admin-company-detail__actions">
                <button
                  className="admin-button admin-button--ghost admin-button--small"
                  type="button"
                  onClick={() =>
                    setSolutionChannels((current) =>
                      current
                        ? {
                            ...current,
                            channels: [
                              ...current.channels,
                              {
                                key: `channel-${current.channels.length + 1}`,
                                name: '',
                                description: '',
                                icon: 'forum',
                                enabled: true,
                                system_hint: '',
                                sample_questions: []
                              }
                            ]
                          }
                        : current
                    )
                  }
                >
                  {t('addChannel')}
                </button>
                <button className="admin-button admin-button--ghost admin-button--small" type="button" onClick={handleResetChannels}>
                  {actions('reset')}
                </button>
                <button className="admin-button admin-button--primary admin-button--small" type="button" onClick={handleSaveChannels}>
                  {actions('save')}
                </button>
              </div>
            </div>
            <label className="admin-field">
              <span>{t('defaultChannel')}</span>
              <select
                className="admin-select"
                value={solutionChannels?.default_channel_key || ''}
                onChange={(event) =>
                  setSolutionChannels((current) => (current ? {...current, default_channel_key: event.target.value} : current))
                }
              >
                {solutionChannels?.channels.map((channel) => (
                  <option key={channel.key} value={channel.key}>
                    {channel.name || channel.key}
                  </option>
                ))}
              </select>
            </label>
            <div className="admin-dimension-grid">
              {solutionChannels?.channels.map((channel, index) => (
                <div className="admin-detail-list__item" key={`${channel.key}-${index}`}>
                  <div className="admin-form-stack">
                    {(['key', 'name', 'description', 'icon', 'system_hint'] as const).map((field) => (
                      <label className="admin-field" key={field}>
                        <span>{t(`channelFields.${field}`)}</span>
                        <input
                          className="admin-input"
                          value={String(channel[field] || '')}
                          onChange={(event) =>
                            setSolutionChannels((current) =>
                              current
                                ? {
                                    ...current,
                                    channels: current.channels.map((item, itemIndex) =>
                                      itemIndex === index ? {...item, [field]: event.target.value} : item
                                    )
                                  }
                                : current
                            )
                          }
                        />
                      </label>
                    ))}
                    <label className="admin-field">
                      <span>{t('sampleQuestions')}</span>
                      <input
                        className="admin-input"
                        value={channel.sample_questions.join(', ')}
                        onChange={(event) =>
                          setSolutionChannels((current) =>
                            current
                              ? {
                                  ...current,
                                  channels: current.channels.map((item, itemIndex) =>
                                    itemIndex === index
                                      ? {...item, sample_questions: parseList(event.target.value)}
                                      : item
                                  )
                                }
                              : current
                          )
                        }
                      />
                    </label>
                    <label className="admin-checkbox-row">
                      <span>{t('enabled')}</span>
                      <input
                        checked={channel.enabled}
                        type="checkbox"
                        onChange={(event) =>
                          setSolutionChannels((current) =>
                            current
                              ? {
                                  ...current,
                                  channels: current.channels.map((item, itemIndex) =>
                                    itemIndex === index ? {...item, enabled: event.target.checked} : item
                                  )
                                }
                              : current
                          )
                        }
                      />
                    </label>
                    <button
                      className="admin-button admin-button--danger admin-button--small"
                      type="button"
                      disabled={(solutionChannels?.channels.length || 0) <= 1}
                      onClick={() =>
                        setSolutionChannels((current) =>
                          current
                            ? {...current, channels: current.channels.filter((_, itemIndex) => itemIndex !== index)}
                            : current
                        )
                      }
                    >
                      {actions('delete')}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="admin-two-column">
            <article className="admin-panel">
              <div className="admin-panel__header">
                <div>
                  <p className="admin-panel__eyebrow">Frontend</p>
                  <h2>{t('frontendModulesTitle')}</h2>
                </div>
                <div className="admin-company-detail__actions">
                  <button className="admin-button admin-button--ghost admin-button--small" onClick={handleResetFrontendModules}>
                    {actions('reset')}
                  </button>
                  <button className="admin-button admin-button--primary admin-button--small" onClick={handleSaveFrontendModules}>
                    {actions('save')}
                  </button>
                </div>
              </div>
              <label className="admin-field">
                <span>{t('defaultModule')}</span>
                <select
                  className="admin-select"
                  value={frontendModules?.default_module || ''}
                  onChange={(event) =>
                    setFrontendModules((current) => (current ? {...current, default_module: event.target.value} : current))
                  }
                >
                  {frontendModules?.modules.map((module) => (
                    <option key={module.key} value={module.key}>
                      {module.name || module.key}
                    </option>
                  ))}
                </select>
              </label>
              <div className="admin-form-stack">
                {frontendModules?.modules.map((module, index) => (
                  <label className="admin-checkbox-row" key={module.key}>
                    <span>
                      {module.name || module.key}
                      <span className="admin-field__meta">{module.description || module.path}</span>
                    </span>
                    <input
                      checked={module.enabled}
                      type="checkbox"
                      onChange={(event) =>
                        setFrontendModules((current) =>
                          current
                            ? {
                                ...current,
                                modules: current.modules.map((item, itemIndex) =>
                                  itemIndex === index ? {...item, enabled: event.target.checked} : item
                                )
                              }
                            : current
                        )
                      }
                    />
                  </label>
                ))}
              </div>
            </article>

            <article className="admin-panel">
              <div className="admin-panel__header">
                <div>
                  <p className="admin-panel__eyebrow">Policy</p>
                  <h2>{t('apiPolicyTitle')}</h2>
                </div>
                <div className="admin-company-detail__actions">
                  <button className="admin-button admin-button--ghost admin-button--small" onClick={handleResetApiPolicy}>
                    {actions('reset')}
                  </button>
                  <button className="admin-button admin-button--primary admin-button--small" onClick={handleSaveApiPolicy}>
                    {actions('save')}
                  </button>
                </div>
              </div>
              {parsedApiPolicy ? (
                <div className="admin-stack">
                  <div className="admin-form-grid admin-form-grid--two">
                    <label className="admin-field">
                      <span>{t('defaultLifetimeGrant')}</span>
                      <input
                        className="admin-input"
                        min={0}
                        type="number"
                        value={parsedApiPolicy.lifetime_token_grant}
                        onChange={(event) => updateApiPolicyField('lifetime_token_grant', Math.max(0, Number(event.target.value || 0)))}
                      />
                    </label>
                    <label className="admin-field">
                      <span>{t('globalDailyLimit')}</span>
                      <input
                        className="admin-input"
                        min={0}
                        type="number"
                        value={parsedApiPolicy.global_daily_token_limit}
                        onChange={(event) => updateApiPolicyField('global_daily_token_limit', Math.max(0, Number(event.target.value || 0)))}
                      />
                    </label>
                    <label className="admin-field">
                      <span>{t('quotaTimezone')}</span>
                      <input
                        className="admin-input"
                        value={parsedApiPolicy.quota_reset_timezone}
                        onChange={(event) => updateApiPolicyField('quota_reset_timezone', event.target.value)}
                      />
                    </label>
                    <label className="admin-field">
                      <span>{t('accessMode')}</span>
                      <select
                        className="admin-select"
                        value={parsedApiPolicy.access_mode}
                        onChange={(event) => updateApiPolicyField('access_mode', event.target.value)}
                      >
                        <option value="lifetime_quota_with_byok">{t('lifetimeMode')}</option>
                        <option value="byok_required">{t('byokOnlyMode')}</option>
                      </select>
                    </label>
                  </div>

                  <div className="admin-section-grid">
                    <label className="admin-checkbox-row">
                      <span>{t('globalBudgetEnabled')}</span>
                      <input
                        checked={parsedApiPolicy.global_budget_enabled}
                        type="checkbox"
                        onChange={(event) => updateApiPolicyField('global_budget_enabled', event.target.checked)}
                      />
                    </label>
                    <label className="admin-checkbox-row">
                      <span>{t('emergencyByokOnly')}</span>
                      <input
                        checked={parsedApiPolicy.emergency_byok_only}
                        type="checkbox"
                        onChange={(event) => updateApiPolicyField('emergency_byok_only', event.target.checked)}
                      />
                    </label>
                    <label className="admin-checkbox-row">
                      <span>{t('allowUserByok')}</span>
                      <input
                        checked={parsedApiPolicy.allow_user_byok}
                        type="checkbox"
                        onChange={(event) => updateApiPolicyField('allow_user_byok', event.target.checked)}
                      />
                    </label>
                  </div>

                  <div className="admin-panel__header">
                    <div>
                      <p className="admin-panel__eyebrow">BYOK</p>
                      <h3>{t('byokGuidanceTitle')}</h3>
                    </div>
                  </div>
                  <div className="admin-form-grid admin-form-grid--two">
                    <label className="admin-field"><span>{t('guidanceHeading')}</span><input className="admin-input" value={parsedApiPolicy.byok_guidance.title} onChange={(event) => updateGuidanceField('title', event.target.value)} /></label>
                    <label className="admin-field"><span>{t('guidanceCta')}</span><input className="admin-input" value={parsedApiPolicy.byok_guidance.cta_label} onChange={(event) => updateGuidanceField('cta_label', event.target.value)} /></label>
                    <label className="admin-field"><span>{t('deepseekOfficialUrl')}</span><input className="admin-input" type="url" value={parsedApiPolicy.byok_guidance.official_url} onChange={(event) => updateGuidanceField('official_url', event.target.value)} /></label>
                    <label className="admin-field"><span>{t('recommendedBaseUrl')}</span><input className="admin-input" type="url" value={parsedApiPolicy.byok_guidance.base_url} onChange={(event) => updateGuidanceField('base_url', event.target.value)} /></label>
                    <label className="admin-field"><span>{t('recommendedModel')}</span><input className="admin-input" value={parsedApiPolicy.byok_guidance.model} onChange={(event) => updateGuidanceField('model', event.target.value)} /></label>
                    <label className="admin-field admin-field--wide"><span>{t('guidanceMessage')}</span><textarea className="admin-textarea" value={parsedApiPolicy.byok_guidance.message} onChange={(event) => updateGuidanceField('message', event.target.value)} /></label>
                  </div>

                  <details className="admin-detail-list__item">
                    <summary>{t('advancedPolicyJson')}</summary>
                    <textarea
                      className="admin-textarea"
                      value={apiPolicyDraft}
                      onChange={(event) => setApiPolicyDraft(event.target.value)}
                    />
                  </details>
                </div>
              ) : (
                <div className="admin-inline-error">{t('invalidPolicyJson')}</div>
              )}
              <div className="admin-inline-notes">
                <span>{t('policyRequests', {count: Number(apiPolicy?.summary?.total_requests || 0)})}</span>
                <span>{t('policyTokens', {count: Number(apiPolicy?.summary?.total_tokens || 0)})}</span>
                <span>{t('globalUsedToday', {count: Number(apiPolicy?.summary?.global_budget?.used_tokens || 0)})}</span>
                <span>{t('globalRemainingToday', {count: Number(apiPolicy?.summary?.global_budget?.remaining_tokens || 0)})}</span>
              </div>
            </article>
          </section>

          <section className="admin-panel">
            <div className="admin-panel__header">
              <div>
                <p className="admin-panel__eyebrow">Registry</p>
                <h2>{t('registryTitle')}</h2>
              </div>
            </div>
            <form className="admin-form-grid" onSubmit={handleCreateSetting}>
              <input
                className="admin-input"
                value={newSettingKey}
                onChange={(event) => setNewSettingKey(event.target.value)}
                placeholder={t('newSettingKey')}
              />
              <input
                className="admin-input"
                value={newSettingCategory}
                onChange={(event) => setNewSettingCategory(event.target.value)}
                placeholder={t('newSettingCategory')}
              />
              <input
                className="admin-input"
                value={newSettingValue}
                onChange={(event) => setNewSettingValue(event.target.value)}
                placeholder={t('newSettingValue')}
              />
              <button className="admin-button admin-button--primary" type="submit">
                {t('createSetting')}
              </button>
            </form>
            <label className="admin-checkbox-row">
              <span>{t('newSettingPublic')}</span>
              <input
                checked={newSettingPublic}
                type="checkbox"
                onChange={(event) => setNewSettingPublic(event.target.checked)}
              />
            </label>
            <div className="admin-record-list">
              {settings
                ? Object.entries(settings).map(([key, item]) => (
                    <div className="admin-record-row" key={key}>
                      <div className="admin-record-row__body">
                        <div className="admin-record-row__title">
                          <strong>{key}</strong>
                          <span className="admin-pill admin-pill--neutral">{item.category}</span>
                          {item.is_public ? <span className="admin-pill admin-pill--brand">{t('public')}</span> : null}
                        </div>
                        <p>{typeof item.value === 'object' ? JSON.stringify(item.value).slice(0, 180) : String(item.value ?? '')}</p>
                      </div>
                      <div className="admin-company-detail__actions">
                        <button
                          className="admin-button admin-button--danger admin-button--small"
                          type="button"
                          onClick={() => handleDeleteSetting(key)}
                        >
                          {actions('delete')}
                        </button>
                      </div>
                    </div>
                  ))
                : null}
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
