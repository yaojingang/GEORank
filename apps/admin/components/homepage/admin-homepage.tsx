'use client';

import type {FormEvent} from 'react';
import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useTranslations} from 'next-intl';

import type {AdminHomepageRelease, AdminHomepageResponse} from '@georank/api-sdk';
import {
  activateAdminHomepageRelease,
  cloneAdminHomepageRelease,
  createAdminHomepageRelease,
  deleteAdminHomepageRelease,
  getAdminHomepage,
  getAdminHomepageReleaseSource,
  previewAdminHomepageRelease,
  restoreDefaultAdminHomepage,
  updateAdminHomepageReleaseSource
} from '@georank/api-sdk';

import {HtmlCodeEditor} from './html-code-editor';

type AdminHomepageProps = {
  token: string;
};

function formatBytes(value?: number | null) {
  if (!value) return '0 KB';
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

export function AdminHomepage({token}: AdminHomepageProps) {
  const t = useTranslations('admin.homepage');
  const actions = useTranslations('common.actions');
  const [payload, setPayload] = useState<AdminHomepageResponse | null>(null);
  const [selectedId, setSelectedId] = useState('');
  const [title, setTitle] = useState('');
  const [sourceType, setSourceType] = useState<'single_html' | 'zip_package'>('single_html');
  const [html, setHtml] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [cloning, setCloning] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorLoading, setEditorLoading] = useState(false);
  const [editorSaving, setEditorSaving] = useState(false);
  const [editorHtml, setEditorHtml] = useState('');
  const [savedEditorHtml, setSavedEditorHtml] = useState('');
  const [editorSourceSha256, setEditorSourceSha256] = useState('');
  const [editorError, setEditorError] = useState('');
  const [error, setError] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const selectedIdRef = useRef(selectedId);
  const editorLoadRequestRef = useRef(0);
  const pendingEditorIdRef = useRef('');

  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);

  const loadHomepage = useCallback(async (nextSelectedId?: string) => {
    setLoading(true);
    setError('');
    try {
      const nextPayload = await getAdminHomepage(token);
      setPayload(nextPayload);
      setSelectedId((current) => {
        if (nextSelectedId) return nextSelectedId;
        if (current && nextPayload.releases.some((release) => release.id === current)) return current;
        return (
          nextPayload.releases.find((release) => release.status === 'active')?.id ||
          nextPayload.releases[0]?.id ||
          ''
        );
      });
    } catch (loadError: unknown) {
      setError(loadError instanceof Error ? loadError.message : t('loadFailed'));
    } finally {
      setLoading(false);
    }
  }, [t, token]);

  useEffect(() => {
    void loadHomepage();
  }, [loadHomepage]);

  const selected = useMemo<AdminHomepageRelease | null>(() => {
    return payload?.releases.find((release) => release.id === selectedId) || null;
  }, [payload, selectedId]);
  const editorDirty = editorHtml !== savedEditorHtml;

  useEffect(() => {
    if (!editorOpen || !editorDirty) return;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [editorDirty, editorOpen]);

  const topStats = useMemo(
    () => [
      {label: t('totalReleases'), value: payload?.releases.length || 0, tone: 'brand'},
      {
        label: t('activeReleases'),
        value: payload?.releases.filter((release) => release.status === 'active').length || 0,
        tone: 'success'
      },
      {
        label: t('draftReleases'),
        value: payload?.releases.filter((release) => release.status === 'draft').length || 0,
        tone: 'warning'
      },
      {label: t('runtimeMode'), value: String(payload?.runtime?.mode || 'default'), tone: 'brand'}
    ],
    [payload, t]
  );

  function confirmDiscardEditorChanges() {
    return !editorOpen || !editorDirty || window.confirm(t('editorDiscardConfirm'));
  }

  function handleSelectRelease(releaseId: string) {
    if (releaseId === selectedId || !confirmDiscardEditorChanges()) return;
    setSelectedId(releaseId);
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!confirmDiscardEditorChanges()) return;
    setCreating(true);
    setActionMessage('');
    try {
      const created = await createAdminHomepageRelease(token, {
        title: title.trim(),
        source_type: sourceType,
        html: sourceType === 'single_html' ? html : undefined,
        file: sourceType === 'zip_package' ? file : null
      });
      setActionMessage(t('createdMessage'));
      setTitle('');
      setHtml('');
      setFile(null);
      await loadHomepage(created.id);
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('createFailed'));
    } finally {
      setCreating(false);
    }
  }

  async function handleActivate() {
    if (!selected) return;
    setActionMessage('');
    try {
      await activateAdminHomepageRelease(token, selected.id);
      setActionMessage(t('activatedMessage'));
      await loadHomepage(selected.id);
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('activateFailed'));
    }
  }

  async function handleRestoreDefault() {
    if (!window.confirm(t('restoreConfirm'))) return;
    setActionMessage('');
    try {
      await restoreDefaultAdminHomepage(token);
      setActionMessage(t('restoredMessage'));
      await loadHomepage();
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('restoreFailed'));
    }
  }

  async function handleDelete() {
    if (!selected) return;
    if (!window.confirm(t('deleteConfirm', {title: selected.title}))) return;
    setActionMessage('');
    try {
      await deleteAdminHomepageRelease(token, selected.id);
      setActionMessage(t('deletedMessage'));
      await loadHomepage();
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('deleteFailed'));
    }
  }

  async function handlePreview() {
    if (!selected) return;
    setActionMessage('');
    try {
      const blob = await previewAdminHomepageRelease(token, selected.id);
      const objectUrl = URL.createObjectURL(blob);
      window.open(objectUrl, '_blank', 'noopener,noreferrer');
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 30000);
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('previewFailed'));
    }
  }

  const openEditorForRelease = useCallback(async (releaseId: string) => {
    const requestId = ++editorLoadRequestRef.current;
    setEditorOpen(true);
    setEditorLoading(true);
    setEditorError('');
    try {
      const source = await getAdminHomepageReleaseSource(token, releaseId);
      if (editorLoadRequestRef.current !== requestId || selectedIdRef.current !== releaseId) return;
      setEditorHtml(source.html);
      setSavedEditorHtml(source.html);
      setEditorSourceSha256(source.sha256);
    } catch (actionError: unknown) {
      if (editorLoadRequestRef.current === requestId && selectedIdRef.current === releaseId) {
        setEditorError(actionError instanceof Error ? actionError.message : t('editorLoadFailed'));
      }
    } finally {
      if (editorLoadRequestRef.current === requestId) setEditorLoading(false);
    }
  }, [t, token]);

  useEffect(() => {
    editorLoadRequestRef.current += 1;
    setEditorOpen(false);
    setEditorHtml('');
    setSavedEditorHtml('');
    setEditorSourceSha256('');
    setEditorError('');
    if (pendingEditorIdRef.current && pendingEditorIdRef.current === selectedId) {
      pendingEditorIdRef.current = '';
      void openEditorForRelease(selectedId);
    }
  }, [openEditorForRelease, selectedId]);

  async function handleOpenEditor() {
    if (!selected || selected.is_builtin) return;
    await openEditorForRelease(selected.id);
  }

  async function handleCloneAndEdit() {
    if (!selected || !selected.is_builtin || cloning) return;
    setCloning(true);
    setActionMessage('');
    try {
      const created = await cloneAdminHomepageRelease(token, selected.id);
      pendingEditorIdRef.current = created.id;
      await loadHomepage(created.id);
      setActionMessage(t('clonedMessage'));
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('cloneFailed'));
    } finally {
      setCloning(false);
    }
  }

  function handleCloseEditor() {
    if (editorDirty && !window.confirm(t('editorDiscardConfirm'))) return;
    setEditorOpen(false);
    setEditorHtml('');
    setSavedEditorHtml('');
    setEditorSourceSha256('');
    setEditorError('');
  }

  async function handleSaveEditor() {
    if (!selected || selected.is_builtin || editorSaving || !editorDirty || !editorSourceSha256) return;
    const releaseId = selected.id;
    const submittedHtml = editorHtml;
    setEditorSaving(true);
    setEditorError('');
    setActionMessage('');
    try {
      const result = await updateAdminHomepageReleaseSource(
        token,
        releaseId,
        submittedHtml,
        editorSourceSha256
      );
      if (selectedIdRef.current === releaseId) {
        setSavedEditorHtml(submittedHtml);
        setEditorSourceSha256(result.source_sha256);
        setActionMessage(result.updated_active ? t('editorSavedActive') : t('editorSaved'));
      }
      await loadHomepage(selectedIdRef.current || undefined);
    } catch (actionError: unknown) {
      if (selectedIdRef.current === releaseId) {
        setEditorError(actionError instanceof Error ? actionError.message : t('editorSaveFailed'));
      }
    } finally {
      setEditorSaving(false);
    }
  }

  return (
    <main className="admin-page">
      <section className="admin-page__hero">
        <div>
          <p className="admin-page__eyebrow">Homepage</p>
          <h1>{t('title')}</h1>
          <p>{t('subtitle')}</p>
        </div>
        {actionMessage ? <div className="admin-page__hero-chip">{actionMessage}</div> : null}
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

      <section className="admin-two-column">
        <article className="admin-panel">
          <div className="admin-panel__header">
            <div>
              <p className="admin-panel__eyebrow">Create</p>
              <h2>{t('createTitle')}</h2>
            </div>
          </div>
          <form className="admin-form-stack" onSubmit={handleCreate}>
            <label className="admin-field">
              <span>{t('releaseTitle')}</span>
              <input
                className="admin-input"
                required
                value={title}
                onChange={(event) => setTitle(event.target.value)}
              />
            </label>
            <label className="admin-field">
              <span>{t('sourceType')}</span>
              <select
                className="admin-select"
                value={sourceType}
                onChange={(event) => setSourceType(event.target.value as 'single_html' | 'zip_package')}
              >
                <option value="single_html">{t('singleHtml')}</option>
                <option value="zip_package">{t('zipPackage')}</option>
              </select>
            </label>
            {sourceType === 'single_html' ? (
              <label className="admin-field">
                <span>{t('htmlBody')}</span>
                <textarea
                  className="admin-textarea"
                  required
                  value={html}
                  onChange={(event) => setHtml(event.target.value)}
                />
              </label>
            ) : (
              <label className="admin-field">
                <span>{t('zipFile')}</span>
                <input
                  className="admin-input homepage-file-input"
                  accept=".zip"
                  required
                  type="file"
                  onChange={(event) => setFile(event.target.files?.[0] || null)}
                />
              </label>
            )}
            <button className="admin-button admin-button--primary" disabled={creating} type="submit">
              {creating ? t('creating') : t('createSubmit')}
            </button>
          </form>
        </article>

        <article className="admin-panel">
          <div className="admin-panel__header">
            <div>
              <p className="admin-panel__eyebrow">Releases</p>
              <h2>{t('releaseListTitle')}</h2>
            </div>
            <button className="admin-button admin-button--ghost admin-button--small" onClick={handleRestoreDefault}>
              {t('restoreDefault')}
            </button>
          </div>

          <div className="admin-record-list">
            {loading ? (
              <p className="admin-feed__empty">{t('loading')}</p>
            ) : payload?.releases.length === 0 ? (
              <p className="admin-feed__empty">{t('emptyList')}</p>
            ) : (
              payload?.releases.map((release) => (
                <button
                  className={`admin-record-row ${release.id === selectedId ? 'is-active' : ''}`}
                  key={release.id}
                  type="button"
                  onClick={() => handleSelectRelease(release.id)}
                >
                  <div className="admin-record-row__body">
                    <div className="admin-record-row__title">
                      <strong>{release.title}</strong>
                      <span className={`admin-pill admin-pill--${release.status === 'active' ? 'success' : 'neutral'}`}>
                        {release.status}
                      </span>
                      {release.is_builtin ? <span className="admin-pill admin-pill--brand">{t('builtin')}</span> : null}
                    </div>
                    <p>{release.entry_path || release.storage_path || release.id}</p>
                    <div className="admin-record-row__meta">
                      <span>{release.source_type}</span>
                      <span>{formatBytes(release.extracted_size || release.compressed_size)}</span>
                      <span>{t('fileCount', {count: release.file_count || 0})}</span>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </article>
      </section>

      <section className="admin-panel">
        <div className="admin-panel__header">
          <div>
            <p className="admin-panel__eyebrow">Detail</p>
            <h2>{t('detailTitle')}</h2>
          </div>
          {selected ? (
            <div className="admin-company-detail__actions">
              <button className="admin-button admin-button--ghost admin-button--small" onClick={handlePreview}>
                {t('preview')}
              </button>
              <button
                className="admin-button admin-button--ghost admin-button--small"
                disabled={cloning}
                title={selected.is_builtin ? t('cloneDescription') : undefined}
                onClick={selected.is_builtin ? handleCloneAndEdit : handleOpenEditor}
              >
                {selected.is_builtin ? (cloning ? t('cloning') : t('cloneAndEdit')) : t('editHtml')}
              </button>
              <button
                className="admin-button admin-button--primary admin-button--small"
                disabled={selected.status === 'active' || selected.status === 'failed'}
                onClick={handleActivate}
              >
                {t('activate')}
              </button>
              <button
                className="admin-button admin-button--danger admin-button--small"
                disabled={selected.status === 'active' || selected.is_builtin}
                onClick={handleDelete}
              >
                {actions('delete')}
              </button>
            </div>
          ) : null}
        </div>
        {!selected ? (
          <p className="admin-feed__empty">{t('selectRelease')}</p>
        ) : (
          <div className="admin-detail-grid">
            <div className="admin-detail-card">
              <span>{t('releaseTitle')}</span>
              <strong>{selected.title}</strong>
            </div>
            <div className="admin-detail-card">
              <span>{t('status')}</span>
              <strong>{selected.status}</strong>
            </div>
            <div className="admin-detail-card">
              <span>{t('entryPath')}</span>
              <strong>{selected.entry_path || '—'}</strong>
            </div>
            <div className="admin-detail-card">
              <span>SHA256</span>
              <strong>{selected.sha256 ? selected.sha256.slice(0, 12) : '—'}</strong>
            </div>
          </div>
        )}
        {selected && editorOpen ? (
          <section className="admin-html-editor" aria-label={t('editorTitle')}>
            <div className="admin-html-editor__header">
              <div>
                <div className="admin-html-editor__title-row">
                  <h3>{t('editorTitle')}</h3>
                  <span className={`admin-pill ${editorDirty ? 'admin-pill--warning' : 'admin-pill--success'}`}>
                    {editorDirty ? t('editorUnsaved') : t('editorSavedState')}
                  </span>
                </div>
                <p>{t('editorDescription')}</p>
              </div>
              <button className="admin-button admin-button--ghost admin-button--small" onClick={handleCloseEditor}>
                {actions('cancel')}
              </button>
            </div>
            {editorError ? <div className="admin-inline-error">{editorError}</div> : null}
            {editorLoading ? (
              <div className="admin-html-editor__loading">{t('editorLoading')}</div>
            ) : (
              <HtmlCodeEditor
                ariaLabel={t('editorAriaLabel')}
                value={editorHtml}
                onChange={setEditorHtml}
                onSave={handleSaveEditor}
              />
            )}
            <div className="admin-html-editor__footer">
              <p>{t('editorHint')}</p>
              <div className="admin-company-detail__actions">
                <button className="admin-button admin-button--ghost admin-button--small" onClick={handlePreview}>
                  {t('preview')}
                </button>
                <button
                  className="admin-button admin-button--primary admin-button--small"
                  disabled={editorLoading || editorSaving || !editorDirty}
                  onClick={handleSaveEditor}
                >
                  {editorSaving
                    ? t('editorSaving')
                    : selected.status === 'active'
                      ? t('editorSave')
                      : t('editorSaveDraft')}
                </button>
              </div>
            </div>
          </section>
        ) : null}
      </section>
    </main>
  );
}
