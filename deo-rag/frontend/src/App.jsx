import { useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';

const DEFAULT_API_PORT = 5200;
const LOCALHOST_API_URL = /^https?:\/\/(localhost|127\.0\.0\.1)(?::\d+)?$/i;

const getApiBaseUrl = () => {
  const configuredUrl = import.meta.env.VITE_API_BASE_URL?.trim();
  if (configuredUrl && !LOCALHOST_API_URL.test(configuredUrl)) {
    return configuredUrl;
  }

  if (typeof window !== 'undefined' && window.location?.hostname) {
    return `${window.location.protocol}//${window.location.hostname}:${DEFAULT_API_PORT}`;
  }

  return `http://127.0.0.1:${DEFAULT_API_PORT}`;
};

const API_BASE_URL = getApiBaseUrl();

const NAV_ITEMS = [
  { id: 'overview', label: 'Overview' },
  { id: 'knowledge-bases', label: 'Data Libraries' },
  { id: 'documents', label: 'Documents' },
  { id: 'ingest', label: 'Ingest' },
  { id: 'chat', label: 'Chat' },
  { id: 'settings', label: 'Settings' },
  { id: 'hardware-placement', label: 'Hardware' },
];

export default function App() {
  const [backendHealth, setBackendHealth] = useState('unknown');
  const [knowledgeBases, setKnowledgeBases] = useState([]);
  const [activeKnowledgeBase, setActiveKnowledgeBase] = useState('unflagged');
  const [newKnowledgeBaseName, setNewKnowledgeBaseName] = useState('');
  const [kbMessage, setKbMessage] = useState('');
  const [kbError, setKbError] = useState('');
  const [creatingKnowledgeBase, setCreatingKnowledgeBase] = useState(false);
  const [switchingKnowledgeBase, setSwitchingKnowledgeBase] = useState(false);
  const [deletingKnowledgeBase, setDeletingKnowledgeBase] = useState(false);
  const [kbDeleteConfirm, setKbDeleteConfirm] = useState('');
  const [settings, setSettings] = useState(null);
  const [editSettings, setEditSettings] = useState(null);
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState('');
  const [question, setQuestion] = useState('');
  const [queryScope, setQueryScope] = useState('active');
  const [answer, setAnswer] = useState('');
  const [sources, setSources] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [ingestStatus, setIngestStatus] = useState(null);
  const [ingestError, setIngestError] = useState('');
  const [chunkSize, setChunkSize] = useState(800);
  const [chunkOverlap, setChunkOverlap] = useState(120);
  const [replaceCollection, setReplaceCollection] = useState(false);
  const [theme, setTheme] = useState(() => {
    if (typeof window === 'undefined') {
      return 'dark';
    }

    try {
      const savedTheme = window.localStorage.getItem('deo-rag-theme');
      if (savedTheme === 'light' || savedTheme === 'dark') {
        return savedTheme;
      }
    } catch {
      // Ignore storage access failures and fall back to system preference.
    }

    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });
  const [activeSection, setActiveSection] = useState('overview');
  const [hardwareProfile, setHardwareProfile] = useState(null);
  const [hardwareLoading, setHardwareLoading] = useState(false);
  const [hardwareRecalibrating, setHardwareRecalibrating] = useState(false);
  const [hardwareUiMessage, setHardwareUiMessage] = useState('');

  const canAsk = useMemo(() => question.trim().length > 0 && !loading, [question, loading]);
  const canUpload = useMemo(() => selectedFiles.length > 0 && !uploading, [selectedFiles, uploading]);
  const canIngest = useMemo(() => !ingesting && !uploading, [ingesting, uploading]);
  const canClearData = useMemo(() => !ingesting && !uploading, [ingesting, uploading]);
  const canCreateKnowledgeBase = useMemo(
    () => newKnowledgeBaseName.trim().length > 0 && !creatingKnowledgeBase,
    [newKnowledgeBaseName, creatingKnowledgeBase]
  );
  const ingestProgress = ingestStatus?.progress || null;

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;

    try {
      window.localStorage.setItem('deo-rag-theme', theme);
    } catch {
      // Ignore storage access failures.
    }
  }, [theme]);

  const withKnowledgeBase = (path, knowledgeBaseOverride = null) => {
    const kb = (knowledgeBaseOverride || activeKnowledgeBase)?.trim();
    if (!kb) {
      return `${API_BASE_URL}${path}`;
    }

    const joiner = path.includes('?') ? '&' : '?';
    return `${API_BASE_URL}${path}${joiner}knowledge_base=${encodeURIComponent(kb)}`;
  };

  const overallProgressPercent = useMemo(() => {
    if (!ingestProgress || !ingestProgress.total_files) {
      return 0;
    }

    const completed = Number(ingestProgress.completed_files || 0);
    const current = Number(ingestProgress.current_file_progress || 0) / 100;
    const pct = ((completed + current) / ingestProgress.total_files) * 100;
    return Math.max(0, Math.min(100, Math.round(pct)));
  }, [ingestProgress]);

  const nonDefaultKnowledgeBases = useMemo(
    () => knowledgeBases.filter((knowledgeBase) => knowledgeBase !== 'unflagged'),
    [knowledgeBases]
  );

  const knowledgeBaseCount = useMemo(() => {
    if (knowledgeBases.length === 0) {
      return 1;
    }

    return knowledgeBases.length;
  }, [knowledgeBases]);

  const activeKnowledgeBaseLabel = activeKnowledgeBase || 'unflagged';
  const documentCount = documents.length;
  const sourceCount = sources.length;
  const ingestState = ingestStatus?.status || 'idle';

  const refreshDocuments = async (knowledgeBaseOverride = null) => {
    try {
      const response = await fetch(withKnowledgeBase('/documents', knowledgeBaseOverride));
      if (!response.ok) {
        throw new Error(`Failed to fetch documents (${response.status})`);
      }

      const data = await response.json();
      setDocuments(Array.isArray(data.documents) ? data.documents : []);
    } catch (err) {
      setError(err.message || 'Failed to load documents.');
    }
  };

  const refreshBackendHealth = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/health`);
      setBackendHealth(response.ok ? 'online' : 'degraded');
    } catch {
      setBackendHealth('offline');
    }
  };

  const refreshHardware = async () => {
    setHardwareLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/hardware`);
      if (!response.ok) {
        throw new Error(`Hardware snapshot failed (${response.status})`);
      }

      const data = await response.json();
      setHardwareProfile(data);
    } catch {
      setHardwareProfile(null);
    } finally {
      setHardwareLoading(false);
    }
  };

  const handleHardwareRecalibrate = async () => {
    setHardwareRecalibrating(true);
    setHardwareUiMessage('');
    try {
      const response = await fetch(`${API_BASE_URL}/hardware/recalibrate`, { method: 'POST' });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `Recalibrate failed (${response.status})`);
      }

      const data = await response.json();
      setHardwareProfile(data);
      setHardwareUiMessage('Hardware profile updated for this machine.');
    } catch (err) {
      setHardwareUiMessage(err.message || 'Recalibrate failed.');
    } finally {
      setHardwareRecalibrating(false);
    }
  };

  const refreshSettings = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/settings`);
      if (!response.ok) {
        throw new Error(`Failed to fetch settings (${response.status})`);
      }

      const data = await response.json();
      setSettings(data);
      if (data.active_knowledge_base) {
        setActiveKnowledgeBase(data.active_knowledge_base);
      }
      setEditSettings({
        llm_model: data.llm_model,
        llm_temperature: data.llm_temperature,
        ollama_num_ctx: data.ollama_num_ctx,
        ollama_num_predict: data.ollama_num_predict,
        retriever_top_k: data.retriever_top_k,
        ingest_chunk_size: data.ingest_chunk_size,
        ingest_chunk_overlap: data.ingest_chunk_overlap,
      });
    } catch (err) {
      setError(err.message || 'Failed to load settings.');
    }
  };

  const refreshKnowledgeBases = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/knowledge-bases`);
      if (!response.ok) {
        throw new Error(`Failed to fetch data libraries (${response.status})`);
      }

      const data = await response.json();
      const list = Array.isArray(data.knowledge_bases) ? data.knowledge_bases : [];
      setKnowledgeBases(list);

      if (data.active_knowledge_base) {
        setActiveKnowledgeBase(data.active_knowledge_base);
        return data.active_knowledge_base;
      } else if (list.length > 0 && !list.includes(activeKnowledgeBase)) {
        setActiveKnowledgeBase(list[0]);
        return list[0];
      }

      return activeKnowledgeBase;
    } catch (err) {
      setKbError(err.message || 'Failed to load data libraries.');
      return activeKnowledgeBase;
    }
  };

  const handleKnowledgeBaseSwitch = async (nextKnowledgeBase) => {
    if (!nextKnowledgeBase || switchingKnowledgeBase) {
      return;
    }

    setKbError('');
    setKbMessage('');
    setSwitchingKnowledgeBase(true);

    try {
      const response = await fetch(`${API_BASE_URL}/knowledge-bases/active`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ knowledge_base: nextKnowledgeBase }),
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || `Failed to switch data library (${response.status})`);
      }

      setActiveKnowledgeBase(nextKnowledgeBase);
      setKbMessage(`Active data library: ${nextKnowledgeBase}`);
      await refreshKnowledgeBases();
      await refreshDocuments(nextKnowledgeBase);
      await fetchIngestStatus(nextKnowledgeBase);
      await refreshSettings();
      setAnswer('');
      setSources([]);
    } catch (err) {
      setKbError(err.message || 'Failed to switch data library.');
    } finally {
      setSwitchingKnowledgeBase(false);
    }
  };

  const handleKnowledgeBaseCreate = async (event) => {
    event.preventDefault();
    if (!canCreateKnowledgeBase) {
      return;
    }

    const candidate = newKnowledgeBaseName.trim();
    setCreatingKnowledgeBase(true);
    setKbError('');
    setKbMessage('');

    try {
      const response = await fetch(`${API_BASE_URL}/knowledge-bases`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ knowledge_base: candidate }),
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || `Failed to create data library (${response.status})`);
      }

      setNewKnowledgeBaseName('');
      await refreshKnowledgeBases();
      setKbMessage(`Data library created: ${candidate}`);
      await handleKnowledgeBaseSwitch(candidate);
    } catch (err) {
      setKbError(err.message || 'Failed to create data library.');
    } finally {
      setCreatingKnowledgeBase(false);
    }
  };

  const handleKnowledgeBaseDelete = async (event) => {
    event.preventDefault();
    if (!kbDeleteConfirm) {
      return;
    }

    const kbToDelete = kbDeleteConfirm.trim();
    setDeletingKnowledgeBase(true);
    setKbError('');
    setKbMessage('');

    try {
      const response = await fetch(`${API_BASE_URL}/knowledge-bases/${encodeURIComponent(kbToDelete)}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || `Failed to delete data library (${response.status})`);
      }

      setKbDeleteConfirm('');
      await refreshKnowledgeBases();
      setKbMessage(`Data library deleted: ${kbToDelete}`);
      await refreshDocuments();
      await fetchIngestStatus();
      await refreshSettings();
      setAnswer('');
      setSources([]);
    } catch (err) {
      setKbError(err.message || 'Failed to delete data library.');
    } finally {
      setDeletingKnowledgeBase(false);
    }
  };

  const handleSettingChange = (key, value) => {
    setEditSettings((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleSaveSettings = async (event) => {
    event.preventDefault();
    if (!editSettings || savingSettings) {
      return;
    }

    setSavingSettings(true);
    setSettingsMessage('');
    setError('');

    try {
      const payload = {
        llm_model: String(editSettings.llm_model).trim(),
        llm_temperature: Number(editSettings.llm_temperature),
        ollama_num_ctx: Number(editSettings.ollama_num_ctx),
        ollama_num_predict: Number(editSettings.ollama_num_predict),
        retriever_top_k: Number(editSettings.retriever_top_k),
        ingest_chunk_size: Number(editSettings.ingest_chunk_size),
        ingest_chunk_overlap: Number(editSettings.ingest_chunk_overlap),
      };

      const response = await fetch(`${API_BASE_URL}/settings`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || `Failed to save settings (${response.status})`);
      }

      setSettings(data.settings || null);
      setChunkSize(data.settings?.ingest_chunk_size ?? editSettings.ingest_chunk_size);
      setChunkOverlap(data.settings?.ingest_chunk_overlap ?? editSettings.ingest_chunk_overlap);
      setSettingsMessage('Settings saved. New values are active for new queries.');
    } catch (err) {
      setSettingsMessage('');
      setError(err.message || 'Failed to save settings.');
    } finally {
      setSavingSettings(false);
    }
  };

  const handleClearData = async () => {
    if (ingesting) {
      setError('Cannot clear data while ingestion is running. Wait for completion, then clear.');
      return;
    }

    const confirmed = window.confirm(
      'Clear uploaded PDFs and delete the current vectorstore collection for this data library? This will remove previously ingested data.'
    );

    if (!confirmed) {
      return;
    }

    setError('');
    setIngestError('');
    setSettingsMessage('');

    try {
      const response = await fetch(`${API_BASE_URL}/data/clear`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          delete_files: true,
          delete_vectorstore: true,
          knowledge_base: activeKnowledgeBase,
        }),
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        if (response.status === 409) {
          throw new Error('Cannot clear data while ingestion is running. Wait for completion, then clear.');
        }
        throw new Error(data.detail || `Failed to clear data (${response.status})`);
      }

      setDocuments([]);
      setIngestStatus({
        status: 'idle',
        job_id: null,
        started_at: null,
        finished_at: null,
        error: null,
        result: null,
        progress: null,
      });
      setIngesting(false);
      refreshSettings();
      setSettingsMessage(
        `Cleared ${Array.isArray(data.deleted_files) ? data.deleted_files.length : 0} files in ${activeKnowledgeBase}${data.deleted_vectorstore ? ' and vectorstore collection.' : '.'}`
      );
    } catch (err) {
      setError(err.message || 'Failed to clear data.');
    }
  };

  const fetchIngestStatus = async (knowledgeBaseOverride = null) => {
    const kb = knowledgeBaseOverride || activeKnowledgeBase;
    try {
      const response = await fetch(
        `${API_BASE_URL}/ingest/status?knowledge_base=${encodeURIComponent(kb)}`
      );
      if (!response.ok) {
        throw new Error(`Failed to fetch ingest status (${response.status})`);
      }

      const data = await response.json();
      setIngestStatus(data);
      setIngesting(data.status === 'running');

      if (data.status === 'completed') {
        setIngestError('');
        refreshDocuments();
      }

      if (data.status === 'failed') {
        setIngestError(data.error || 'Ingestion failed.');
      }
    } catch (err) {
      setIngestError(err.message || 'Failed to read ingest status.');
      setIngesting(false);
    }
  };

  useEffect(() => {
    const bootstrap = async () => {
      await refreshBackendHealth();
      const initialKnowledgeBase = await refreshKnowledgeBases();
      await refreshSettings();
      await refreshHardware();
      await refreshDocuments(initialKnowledgeBase);
      await fetchIngestStatus(initialKnowledgeBase);
    };

    bootstrap();
  }, []);

  useEffect(() => {
    if (!ingesting) {
      return undefined;
    }

    const timer = setInterval(fetchIngestStatus, 2000);
    return () => clearInterval(timer);
  }, [ingesting, activeKnowledgeBase]);

  const handleFileSelection = (event) => {
    const files = Array.from(event.target.files || []);
    setSelectedFiles(files);
  };

  const handleUpload = async (event) => {
    event.preventDefault();
    if (!canUpload) {
      return;
    }

    setUploading(true);
    setError('');

    try {
      const formData = new FormData();
      selectedFiles.forEach((file) => formData.append('files', file));

      const response = await fetch(withKnowledgeBase('/upload'), {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `Upload failed (${response.status})`);
      }

      setSelectedFiles([]);
      await refreshDocuments();
    } catch (err) {
      setError(err.message || 'Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const handleIngestStart = async (event) => {
    event.preventDefault();
    if (!canIngest) {
      return;
    }

    setIngestError('');

    try {
      const response = await fetch(`${API_BASE_URL}/ingest/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          chunk_size: Number(chunkSize),
          chunk_overlap: Number(chunkOverlap),
          replace_collection: replaceCollection,
          knowledge_base: activeKnowledgeBase,
        }),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `Failed to start ingest (${response.status})`);
      }

      setIngesting(true);
      await fetchIngestStatus();
    } catch (err) {
      setIngestError(err.message || 'Failed to start ingest.');
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!canAsk) {
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE_URL}/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: question.trim(),
          knowledge_base: activeKnowledgeBase,
          query_scope: queryScope,
        }),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `Request failed with status ${response.status}`);
      }

      const data = await response.json();
      setAnswer(data.answer || 'No answer returned.');
      setSources(Array.isArray(data.sources) ? data.sources : []);
    } catch (err) {
      setAnswer('');
      setSources([]);
      setError(err.message || 'Failed to query backend.');
    } finally {
      setLoading(false);
    }
  };

  const refreshDashboard = () => {
    refreshBackendHealth();
    refreshKnowledgeBases();
    refreshSettings();
    refreshHardware();
    refreshDocuments();
    fetchIngestStatus();
  };

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">DEO</div>
          <div>
            <p className="brand-kicker">DEO RAG Console</p>
            <h1>Defence estates workspace</h1>
          </div>
        </div>

        <div className="sidebar-section">
          <p className="section-label">System status</p>
          <div className="status-stack">
            <div className="status-card">
              <span className={`health-pill health-${backendHealth}`}>Backend {backendHealth}</span>
              <strong>{settings?.llm_provider || 'Loading...'}</strong>
              <span className="muted">{settings?.embedding_model || 'Fetching settings...'}</span>
            </div>
            <div className="status-card">
              <span className="status-label">Active library</span>
              <strong>{activeKnowledgeBaseLabel}</strong>
              <span className="muted">{knowledgeBaseCount} available collections</span>
            </div>
            <div className="status-card">
              <span className="status-label">Documents</span>
              <strong>{documentCount}</strong>
              <span className="muted">PDFs in the active library</span>
            </div>
            <div className="status-card">
              <span className="status-label">Ingestion</span>
              <strong>{ingestState}</strong>
              <span className="muted">
                {ingestProgress ? `${overallProgressPercent}% indexed` : 'Idle until you start ingestion'}
              </span>
            </div>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Dashboard navigation">
          {NAV_ITEMS.map((item) => (
            <a
              key={item.id}
              href={`#${item.id}`}
              className={activeSection === item.id ? 'nav-link active' : 'nav-link'}
              onClick={() => setActiveSection(item.id)}
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="sidebar-footer">
          <span className="section-label">Vector collection</span>
          <strong>{settings?.collection_name || 'DEO collection'}</strong>
          <p className="muted">Each data library maps to an isolated collection for retrieval.</p>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Dashboard</p>
            <h2>DEO RAG Assistant</h2>
            <p className="subtitle">
              Upload Defence Estates documents, ingest them into Data Libraries, and answer questions from one library or all libraries.
            </p>
          </div>

          <div className="topbar-actions">
            <button type="button" className="ghost-button" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
              {theme === 'dark' ? 'Light mode' : 'Dark mode'}
            </button>
            <button type="button" className="secondary-button" onClick={refreshDashboard}>
              Refresh dashboard
            </button>
          </div>
        </header>

        <section id="overview" className="overview-grid">
          <article className="overview-card accent">
            <span className="overview-label">Active data library</span>
            <strong>{activeKnowledgeBaseLabel}</strong>
            <p>Active-mode queries and ingestion are scoped to this library.</p>
          </article>
          <article className="overview-card">
            <span className="overview-label">Documents</span>
            <strong>{documentCount}</strong>
            <p>{documentCount === 1 ? 'PDF currently stored' : 'PDFs currently stored'}</p>
          </article>
          <article className="overview-card">
            <span className="overview-label">Sources referred</span>
            <strong>{sourceCount}</strong>
            <p>Most recent answer sources</p>
          </article>
          <article className="overview-card">
            <span className="overview-label">Backend</span>
            <strong>{backendHealth}</strong>
            <p>{settings?.llm_model || 'Awaiting settings'}</p>
          </article>
        </section>

        {kbMessage || kbError || settingsMessage || ingestError || error ? (
          <section className="alert-stack">
            {kbMessage ? <div className="alert success">{kbMessage}</div> : null}
            {settingsMessage ? <div className="alert success">{settingsMessage}</div> : null}
            {kbError ? <div className="alert danger">{kbError}</div> : null}
            {ingestError ? <div className="alert danger">{ingestError}</div> : null}
            {error ? <div className="alert danger">{error}</div> : null}
          </section>
        ) : null}

        <section id="knowledge-bases" className="panel panel-wide">
          <div className="panel-header">
            <div>
              <p className="section-label">Data Libraries</p>
              <h3>Manage isolated DEO record libraries</h3>
            </div>
            <button type="button" className="danger-button" onClick={handleClearData} disabled={!canClearData}>
              {ingesting ? 'Clear disabled during ingest' : 'Clear active data'}
            </button>
          </div>

          <div className="panel-grid two-up">
            <form className="stack-form" onSubmit={(event) => event.preventDefault()}>
              <label htmlFor="kb-select">Switch active data library</label>
              <select
                id="kb-select"
                value={activeKnowledgeBase}
                onChange={(e) => handleKnowledgeBaseSwitch(e.target.value)}
                disabled={switchingKnowledgeBase || ingesting}
              >
                {knowledgeBases.length === 0 ? (
                  <option value="unflagged">unflagged</option>
                ) : (
                  knowledgeBases.map((kb) => (
                    <option key={kb} value={kb}>
                      {kb}
                    </option>
                  ))
                )}
              </select>

              <label htmlFor="kb-new">Create new data library</label>
              <input
                id="kb-new"
                type="text"
                value={newKnowledgeBaseName}
                onChange={(e) => setNewKnowledgeBaseName(e.target.value)}
                placeholder="Example: lease-case-files"
                disabled={creatingKnowledgeBase || ingesting}
              />
              <button type="button" className="primary-button" onClick={handleKnowledgeBaseCreate} disabled={!canCreateKnowledgeBase || ingesting}>
                {creatingKnowledgeBase ? 'Creating...' : 'Create and switch'}
              </button>
            </form>

            <form className="stack-form danger-form" onSubmit={handleKnowledgeBaseDelete}>
              <label htmlFor="kb-delete">Delete data library</label>
              <p className="helper-text">
                Permanently removes the library folder, all ingested vectors, and its ingest history. Unflagged cannot be deleted.
              </p>
              {kbDeleteConfirm !== '' ? (
                <div className="warning-box">
                  <strong>Review before deleting</strong>
                  <ul>
                    <li>All documents in {kbDeleteConfirm}</li>
                    <li>All vectors in the database collection</li>
                    <li>All ingestion state for that library</li>
                  </ul>
                </div>
              ) : null}
              <select
                id="kb-delete"
                value={kbDeleteConfirm}
                onChange={(e) => setKbDeleteConfirm(e.target.value)}
                disabled={deletingKnowledgeBase || ingesting}
              >
                <option value="">Select a data library to delete</option>
                {nonDefaultKnowledgeBases.map((kb) => (
                  <option key={kb} value={kb}>
                    {kb}
                  </option>
                ))}
              </select>
              <button type="submit" className="danger-button" disabled={kbDeleteConfirm === '' || deletingKnowledgeBase || ingesting}>
                {deletingKnowledgeBase ? 'Deleting...' : 'Delete library'}
              </button>
            </form>
          </div>

          <div className="inline-summary">
            <div>
              <span className="section-label">Active collection</span>
              <strong>{settings?.collection_name || 'Loading...'}</strong>
            </div>
            <div>
              <span className="section-label">Data Libraries</span>
              <strong>{knowledgeBaseCount}</strong>
            </div>
            <div>
              <span className="section-label">Current docs</span>
              <strong>{documentCount}</strong>
            </div>
          </div>
        </section>

        <section id="documents" className="panel panel-wide">
          <div className="panel-header">
            <div>
              <p className="section-label">Documents</p>
              <h3>Upload PDFs into the active data library</h3>
            </div>
            <span className="muted">{selectedFiles.length} selected</span>
          </div>

          <div className="panel-grid two-up">
            <form onSubmit={handleUpload} className="stack-form">
              <label htmlFor="files">Upload PDFs</label>
              <input id="files" type="file" accept="application/pdf" multiple onChange={handleFileSelection} />
              <button type="submit" className="primary-button" disabled={!canUpload}>
                {uploading ? 'Uploading...' : 'Upload files'}
              </button>
              <p className="helper-text">Files are stored in the selected data library before ingestion.</p>
            </form>

            <div className="document-list-card">
              <div className="document-list-header">
                <span className="section-label">Current documents</span>
                <strong>{documents.length}</strong>
              </div>
              {documents.length > 0 ? (
                <ul className="document-list">
                  {documents.map((doc) => (
                    <li key={doc}>{doc}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted">No PDFs uploaded in this data library yet.</p>
              )}
            </div>
          </div>
        </section>

        <section id="ingest" className="panel panel-wide">
          <div className="panel-header">
            <div>
              <p className="section-label">Ingestion</p>
              <h3>Chunk and index documents for retrieval</h3>
            </div>
            <span className={`health-pill health-${backendHealth}`}>Backend {backendHealth}</span>
          </div>

          <form onSubmit={handleIngestStart} className="panel-grid two-up ingest-layout">
            <div className="stack-form">
              <label htmlFor="chunk-size">Chunk size</label>
              <input id="chunk-size" type="number" min="100" value={chunkSize} onChange={(e) => setChunkSize(e.target.value)} />

              <label htmlFor="chunk-overlap">Chunk overlap</label>
              <input id="chunk-overlap" type="number" min="0" value={chunkOverlap} onChange={(e) => setChunkOverlap(e.target.value)} />

              <label className="checkbox-row" htmlFor="replace-collection">
                <input
                  id="replace-collection"
                  type="checkbox"
                  checked={replaceCollection}
                  onChange={(e) => setReplaceCollection(e.target.checked)}
                />
                Replace existing vector collection
              </label>

              <button type="submit" className="primary-button" disabled={!canIngest}>
                {ingesting ? 'Ingesting...' : 'Start ingestion'}
              </button>
            </div>

            <div className="status-box dashboard-status">
              <div className="status-header">
                <div>
                  <span className="section-label">Current state</span>
                  <strong>{ingestStatus?.status || 'idle'}</strong>
                </div>
                {ingestStatus?.job_id ? <span className="chip">Job {ingestStatus.job_id.slice(0, 8)}</span> : null}
              </div>

              {ingestStatus ? (
                <>
                  <div className="progress-section">
                    <div className="progress-label-row">
                      <span>Overall progress</span>
                      <span>{overallProgressPercent}%</span>
                    </div>
                    <div className="progress-track">
                      <div className="progress-fill" style={{ width: `${overallProgressPercent}%` }} />
                    </div>
                  </div>

                  <div className="progress-section">
                    <div className="progress-label-row">
                      <span>Current file</span>
                      <span>{ingestProgress?.current_file_progress || 0}%</span>
                    </div>
                    <p className="muted">{ingestProgress?.current_file || 'Waiting for a file to process'}</p>
                    <div className="progress-track slim">
                      <div className="progress-fill current-file" style={{ width: `${ingestProgress?.current_file_progress || 0}%` }} />
                    </div>
                  </div>

                  {Array.isArray(ingestProgress?.files) && ingestProgress.files.length > 0 ? (
                    <div className="file-progress-list">
                      {ingestProgress.files.map((file) => (
                        <div key={file.file} className="file-progress-item">
                          <div className="file-progress-header">
                            <span>{file.file}</span>
                            <span>{file.status}</span>
                          </div>
                          <div className="progress-track slim">
                            <div className="progress-fill" style={{ width: `${file.progress || 0}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : null}

                  {ingestStatus.result ? (
                    <div className="ingest-result-grid">
                      <div><span>Scanned</span><strong>{ingestStatus.result.scanned_files}</strong></div>
                      <div><span>Parsed</span><strong>{ingestStatus.result.parsed_documents}</strong></div>
                      <div><span>Chunks</span><strong>{ingestStatus.result.chunks_created}</strong></div>
                    </div>
                  ) : null}

                  {ingestStatus.result?.failed_files?.length ? (
                    <div className="failed-list">
                      <span className="section-label">Failed files</span>
                      <ul>
                        {ingestStatus.result.failed_files.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </>
              ) : (
                <p className="muted">No ingest job has run yet.</p>
              )}
            </div>
          </form>
        </section>

        <section id="chat" className="panel panel-wide">
          <div className="panel-header">
            <div>
              <p className="section-label">Chat</p>
              <h3>Ask questions against DEO record libraries</h3>
            </div>
            <span className="chip">{sourceCount} sources referred</span>
          </div>

          <div className="panel-grid two-up chat-layout">
            <form onSubmit={handleSubmit} className="stack-form">
              <label htmlFor="question">Question</label>
              <textarea
                id="question"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Example: What does this lease file say about renewal conditions?"
                rows={7}
              />
              <label htmlFor="query-scope">Query scope</label>
              <select id="query-scope" value={queryScope} onChange={(e) => setQueryScope(e.target.value)}>
                <option value="active">Active library only</option>
                <option value="global">Global search across all libraries</option>
              </select>
              <button type="submit" className="primary-button" disabled={!canAsk}>
                {loading ? 'Thinking...' : 'Ask question'}
              </button>
            </form>

            <div className="answer-card">
              <div className="panel-header compact">
                <div>
                  <span className="section-label">Answer</span>
                  <h4>Retrieved response</h4>
                </div>
              </div>
              <div className={answer ? 'answer-text' : 'muted'}>
                {answer ? (
                  <ReactMarkdown
                    components={{
                      p: ({node, ...props}) => <p {...props} className="markdown-paragraph" />,
                      strong: ({node, ...props}) => <strong {...props} />,
                      em: ({node, ...props}) => <em {...props} />,
                      br: () => <br />,
                      ul: ({node, ...props}) => <ul className="markdown-list" {...props} />,
                      ol: ({node, ...props}) => <ol className="markdown-list" {...props} />,
                      li: ({node, ...props}) => <li {...props} />,
                      h1: ({node, ...props}) => <h3 {...props} className="markdown-heading" />,
                      h2: ({node, ...props}) => <h4 {...props} className="markdown-heading" />,
                      h3: ({node, ...props}) => <h5 {...props} className="markdown-heading" />,
                      code: ({node, inline, ...props}) => inline ? <code {...props} className="inline-code" /> : <pre {...props} className="code-block" />,
                    }}
                  >
                    {answer}
                  </ReactMarkdown>
                ) : (
                  <p className="muted">Submit a question to see an answer.</p>
                )}
              </div>

              <div className="sources-block">
                <span className="section-label">Sources Referred</span>
                {sources.length === 0 ? (
                  <p className="muted">No sources referred yet.</p>
                ) : (
                  <ul className="source-list">
                    {sources.map((source, index) => (
                      <li key={`${source.source || 'unknown'}-${index}`}>
                        <a
                          href={source.source_url ? `${API_BASE_URL}${source.source_url}` : undefined}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <strong>{source.parent_source || source.source || 'unknown document'}</strong>
                        </a>
                        <span>{source.library || activeKnowledgeBaseLabel}</span>
                        {Array.isArray(source.pages) && source.pages.length ? (
                          <span>pages {source.pages.join(', ')}</span>
                        ) : source.page ? (
                          <span>page {source.page}</span>
                        ) : null}
                        {source.snippet ? <p className="source-snippet">{source.snippet}</p> : null}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        </section>

        <section id="settings" className="panel panel-wide">
          <div className="panel-header">
            <div>
              <p className="section-label">Settings</p>
              <h3>Runtime configuration</h3>
            </div>
          </div>

          {settings && editSettings ? (
            <form className="settings-form dashboard-settings" onSubmit={handleSaveSettings}>
              <div className="settings-grid stat-grid">
                <div><span>LLM provider</span><strong>{settings.llm_provider}</strong></div>
                <div><span>Embedding provider</span><strong>{settings.embedding_provider}</strong></div>
                <div><span>Embedding model</span><strong>{settings.embedding_model}</strong></div>
                <div><span>Collection</span><strong>{settings.collection_name}</strong></div>
              </div>

              <div className="panel-grid two-up">
                <div className="stack-form">
                  <label htmlFor="llm-model">LLM model</label>
                  <input
                    id="llm-model"
                    type="text"
                    value={editSettings.llm_model}
                    onChange={(e) => handleSettingChange('llm_model', e.target.value)}
                  />

                  <label htmlFor="llm-temp">Temperature</label>
                  <input
                    id="llm-temp"
                    type="number"
                    step="0.1"
                    min="0"
                    value={editSettings.llm_temperature}
                    onChange={(e) => handleSettingChange('llm_temperature', e.target.value)}
                  />

                  <label htmlFor="num-ctx">Context size</label>
                  <input
                    id="num-ctx"
                    type="number"
                    min="1"
                    value={editSettings.ollama_num_ctx}
                    onChange={(e) => handleSettingChange('ollama_num_ctx', e.target.value)}
                  />

                  <label htmlFor="num-predict">Max output tokens</label>
                  <input
                    id="num-predict"
                    type="number"
                    min="1"
                    value={editSettings.ollama_num_predict}
                    onChange={(e) => handleSettingChange('ollama_num_predict', e.target.value)}
                  />
                </div>

                <div className="stack-form">
                  <label htmlFor="top-k">Retriever top-k</label>
                  <input
                    id="top-k"
                    type="number"
                    min="1"
                    value={editSettings.retriever_top_k}
                    onChange={(e) => handleSettingChange('retriever_top_k', e.target.value)}
                  />

                  <label htmlFor="ingest-size">Default ingest chunk size</label>
                  <input
                    id="ingest-size"
                    type="number"
                    min="100"
                    value={editSettings.ingest_chunk_size}
                    onChange={(e) => handleSettingChange('ingest_chunk_size', e.target.value)}
                  />

                  <label htmlFor="ingest-overlap">Default ingest chunk overlap</label>
                  <input
                    id="ingest-overlap"
                    type="number"
                    min="0"
                    value={editSettings.ingest_chunk_overlap}
                    onChange={(e) => handleSettingChange('ingest_chunk_overlap', e.target.value)}
                  />

                  <button type="submit" className="primary-button" disabled={savingSettings}>
                    {savingSettings ? 'Saving...' : 'Save settings'}
                  </button>
                </div>
              </div>
            </form>
          ) : (
            <p className="muted">Loading settings...</p>
          )}
        </section>

        <footer id="hardware-placement" className="hardware-footer panel panel-wide">
          <div className="panel-header hardware-footer-header">
            <div>
              <p className="section-label">Hardware placement</p>
              <h3>Accelerator calibration</h3>
              <p className="subtitle tight">
                Preferred order: NVIDIA CUDA → Intel PyTorch XPU (when installed) → CPU. Ollama chooses its own device;
                this panel reflects detection plus the paths this app controls (Docling, HuggingFace embeddings, PaddleOCR).
              </p>
            </div>
            <div className="hardware-footer-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={refreshHardware}
                disabled={hardwareLoading || hardwareRecalibrating}
              >
                {hardwareLoading ? 'Refreshing…' : 'Refresh'}
              </button>
              <button
                type="button"
                className="primary-button"
                onClick={handleHardwareRecalibrate}
                disabled={hardwareRecalibrating || backendHealth !== 'online'}
              >
                {hardwareRecalibrating ? 'Recalibrating…' : 'Re-calibrate hardware'}
              </button>
            </div>
          </div>

          {hardwareUiMessage ? <div className="alert success hardware-banner">{hardwareUiMessage}</div> : null}

          {!hardwareProfile && hardwareLoading ? (
            <p className="muted">Loading hardware profile…</p>
          ) : null}

          {!hardwareProfile && !hardwareLoading ? (
            <p className="muted">Hardware profile unavailable (is the backend running?).</p>
          ) : null}

          {hardwareProfile ? (
            <div className="hardware-grid">
              <div className="hardware-card">
                <span className="section-label">Resolved usage</span>
                <ul className="hardware-usage-list">
                  {Object.entries(hardwareProfile.usage_summary || {}).map(([key, label]) => (
                    <li key={key}>
                      <span className="hardware-key">{key.replace(/_/g, ' ')}</span>
                      <span className="hardware-val">{String(label)}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="hardware-card">
                <span className="section-label">Ollama snapshot</span>
                <p className="hardware-ollama-summary">{hardwareProfile.ollama?.summary || '—'}</p>
                <p className="helper-text">
                  Endpoint: {hardwareProfile.app_providers?.ollama_base_url || '—'}
                </p>
              </div>

              <div className="hardware-card span-2">
                <span className="section-label">Detected GPUs</span>
                <ul className="hardware-adapter-list">
                  {(hardwareProfile.video_adapters || []).length === 0 ? (
                    <li className="muted">No adapters reported (non-Windows host or probe skipped).</li>
                  ) : (
                    hardwareProfile.video_adapters.map((a) => (
                      <li key={a.name}>
                        <strong>{a.name}</strong>
                        {a.adapter_ram_bytes ? (
                          <span className="muted"> · dedicated VRAM ~{Math.round(a.adapter_ram_bytes / (1024 * 1024))} MiB</span>
                        ) : (
                          <span className="muted"> · integrated / shared system memory</span>
                        )}
                      </li>
                    ))
                  )}
                </ul>
                <div className="hardware-flags">
                  <span className={`chip ${hardwareProfile.nvidia_pytorch_cuda_usable ? 'chip-ok' : ''}`}>
                    NVIDIA PyTorch CUDA: {hardwareProfile.nvidia_pytorch_cuda_usable ? 'usable' : 'no'}
                  </span>
                  <span className={`chip ${hardwareProfile.pytorch_xpu_usable ? 'chip-ok' : ''}`}>
                    PyTorch XPU: {hardwareProfile.pytorch_xpu_usable ? 'yes' : 'no'}
                  </span>
                  <span className="chip">
                    Intel graphics: {hardwareProfile.intel_graphics_detected ? 'detected' : 'not listed'}
                  </span>
                </div>
              </div>

              {(hardwareProfile.notes || []).length ? (
                <div className="hardware-card span-2">
                  <span className="section-label">Notes</span>
                  <ul className="hardware-notes">
                    {hardwareProfile.notes.map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <p className="hardware-meta muted span-2">
                Calibrated at {hardwareProfile.calibrated_at || '—'} · Fallback chain:{' '}
                {(hardwareProfile.fallback_chain_applied || []).join(' → ')}
              </p>
            </div>
          ) : null}
        </footer>
      </div>
    </main>
  );
}
