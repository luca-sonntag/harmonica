import React, { useEffect, useRef, useState } from 'react';

interface SheetPage {
  page_number: number;
  png_url: string;
  svg_url: string;
  caption: string;
}

interface TranscriptionResult {
  job_id: string;
  title: string;
  original_filename: string;
  media_kind: 'VIDEO' | 'AUDIO';
  conversion_step: string;
  duration_s: number;
  tuning: string;
  time_signature: string;
  measures_count: number;
  druck_measures: number;
  zug_measures: number;
  rows_used: string[];
  processing_time_s: number;
  video_frame_url: string | null;
  original_audio_url: string;
  synthesized_audio_url: string;
  stereo_diff_audio_url: string;
  pdf_url: string;
  musicxml_url: string;
  pages: SheetPage[];
}

interface PipelineStage {
  id: string;
  step: string;
  title: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  duration_s: number | null;
  detail: string;
}

interface TelemetryLog {
  time: string;
  level: string;
  text: string;
}

interface JobStatusResponse {
  job_id: string;
  filename: string;
  title: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  progress_percent: number;
  current_stage_id: string;
  current_stage_label: string;
  current_stage_detail: string;
  elapsed_s: number;
  stages: PipelineStage[];
  logs: TelemetryLog[];
  error: string | null;
  result: TranscriptionResult | null;
}

type ViewMode = 'sheet' | 'pdf' | 'progress';
type PageDisplayFilter = 'all' | number;
type AudioTrackMode = 'stereo' | 'synth' | 'original';

function formatSeconds(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}s`;
}

export default function App() {
  const [result, setResult] = useState<TranscriptionResult | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [customTitle, setCustomTitle] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [activeJob, setActiveJob] = useState<JobStatusResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState<boolean>(false);

  const [viewMode, setViewMode] = useState<ViewMode>('sheet');
  const [pageFilter, setPageFilter] = useState<PageDisplayFilter>('all');
  const [zoomed, setZoomed] = useState<boolean>(false);
  const [audioMode, setAudioMode] = useState<AudioTrackMode>('stereo');
  const [systemReadyLabel] = useState<string>('Notensatz bereit (Stimmung G-C-F-B)');

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const sseRef = useRef<EventSource | null>(null);
  const pollIntervalRef = useRef<any>(null);

  useEffect(() => {
    return () => {
      cleanupStreams();
    };
  }, []);

  function cleanupStreams() {
    if (sseRef.current) {
      sseRef.current.close();
      sseRef.current = null;
    }
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }

  function handleFilePicked(file: File | undefined) {
    if (!file) return;
    setSelectedFile(file);
    setErrorMsg(null);
    if (!customTitle.trim()) {
      const baseName = file.name.replace(/\.[^/.]+$/, '');
      setCustomTitle(baseName);
    }
  }

  function startJobTracking(jobId: string) {
    cleanupStreams();

    function handleJobUpdate(job: JobStatusResponse) {
      setActiveJob(job);
      if (job.status === 'completed' && job.result) {
        setResult(job.result);
        setIsLoading(false);
        cleanupStreams();
      } else if (job.status === 'failed') {
        setErrorMsg(job.error || 'Verarbeitung fehlgeschlagen.');
        setIsLoading(false);
        cleanupStreams();
      }
    }

    function startPollingFallback() {
      if (pollIntervalRef.current) return;
      pollIntervalRef.current = setInterval(async () => {
        try {
          const resp = await fetch(`/api/jobs/${jobId}`);
          if (!resp.ok) return;
          const data: JobStatusResponse = await resp.json();
          handleJobUpdate(data);
        } catch {
          // ignore transient polling errors
        }
      }, 600);
    }

    try {
      const es = new EventSource(`/api/jobs/${jobId}/stream`);
      sseRef.current = es;

      es.onmessage = (event) => {
        try {
          const data: JobStatusResponse = JSON.parse(event.data);
          handleJobUpdate(data);
        } catch (err) {
          console.warn('Failed to parse SSE event', err);
        }
      };

      es.onerror = () => {
        if (sseRef.current) {
          sseRef.current.close();
          sseRef.current = null;
        }
        startPollingFallback();
      };
    } catch {
      startPollingFallback();
    }
  }

  async function handleRunPipeline(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedFile) return;

    setErrorMsg(null);
    setIsLoading(true);
    setViewMode('progress');

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('title', customTitle.trim());

      const resp = await fetch('/api/transcribe', {
        method: 'POST',
        body: formData,
      });

      if (!resp.ok) {
        const errJson = await resp.json().catch(() => ({}));
        throw new Error(errJson.detail || `Serverfehler (${resp.status})`);
      }

      const initialData: JobStatusResponse = await resp.json();
      setActiveJob(initialData);

      if (initialData.status === 'completed' && initialData.result) {
        setResult(initialData.result);
        setIsLoading(false);
        setPageFilter('all');
        return;
      }

      startJobTracking(initialData.job_id);
    } catch (err) {
      setIsLoading(false);
      setErrorMsg(err instanceof Error ? err.message : 'Fehler bei der Verarbeitung.');
    }
  }

  const activeAudioUrl =
    result == null
      ? ''
      : audioMode === 'stereo'
        ? result.stereo_diff_audio_url
        : audioMode === 'synth'
          ? result.synthesized_audio_url
          : result.original_audio_url;

  const visiblePages =
    result == null
      ? []
      : pageFilter === 'all'
        ? result.pages
        : result.pages.filter((p) => p.page_number === pageFilter);

  return (
    <div>
      {/* Editorial Masthead */}
      <header className="masthead">
        <div className="masthead-top">
          <span className="masthead-kicker">
            Notenwerkbank · Steirische Harmonika (Stimmung G-C-F-B · System Max Rosenzopf)
          </span>
          <span className="masthead-status">
            <span className="status-dot" />
            {systemReadyLabel}
          </span>
        </div>
        <div className="masthead-title-row">
          <h1 className="masthead-title">Normalnoten &amp; Griffschrift</h1>
          <p className="masthead-subtitle">
            Vom Klang zum Notenblatt: Aufnahme einspeisen → Melodie &amp; Bässe erkennen → Optimale Balgführung → Spielfertiges Notenblatt
          </p>
        </div>
      </header>

      <main className="workbench">
        {/* Left Column: Upload, and conditionally specs & verification when loaded */}
        <aside className="sidebar-column">
          {/* [01] Datei-Upload (Audio & Video) - Always necessary */}
          <section className="panel-section">
            <div className="section-header">
              <div>
                <span className="section-index">[01] Quelle einspeisen</span>
                <h2 className="section-heading">Audio- oder Videoaufnahme</h2>
              </div>
            </div>

            <form onSubmit={handleRunPipeline}>
              <div
                className={`dropzone ${dragActive ? 'drag-active' : ''}`}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragActive(true);
                }}
                onDragLeave={() => setDragActive(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragActive(false);
                  handleFilePicked(e.dataTransfer.files?.[0]);
                }}
              >
                <div className="dropzone-formats">
                  Video (.MP4, .MOV) · Audio (.WAV, .MP3, .M4A)
                </div>
                <div className="dropzone-main">
                  Aufnahme hier ablegen oder antippen zum Auswählen
                </div>
                <p className="dropzone-hint">
                  Nimm eine Video- oder Tonaufnahme deines Stücks (z. B. Handy-Aufnahme oder MP3).
                  Das Notenblatt wird automatisch daraus erstellt.
                </p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="audio/*,video/*,.mp4,.mov,.webm,.mkv,.wav,.mp3,.m4a,.ogg,.flac"
                  style={{ display: 'none' }}
                  onChange={(e) => handleFilePicked(e.target.files?.[0])}
                />
              </div>

              {selectedFile && (
                <div className="file-selected-banner">
                  <span>
                    <strong>Ausgewählt:</strong> {selectedFile.name} (
                    {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB)
                  </span>
                </div>
              )}

              <div className="input-field-group">
                <label className="input-label" htmlFor="piece-title-input">
                  Werktitel auf dem Notenblatt (Optional)
                </label>
                <input
                  id="piece-title-input"
                  className="text-input"
                  type="text"
                  placeholder="z.B. Steirische Polka in C"
                  value={customTitle}
                  onChange={(e) => setCustomTitle(e.target.value)}
                  disabled={isLoading}
                />
              </div>

              <div className="btn-row">
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={!selectedFile || isLoading}
                >
                  {isLoading
                    ? `Notenblatt wird erstellt (${activeJob?.progress_percent ?? 0}%)…`
                    : 'Noten & Griffschrift erstellen'}
                </button>
              </div>
            </form>
          </section>

          {/* [02] Werkblatt-Protokoll: Only visible when activeJob or result exists */}
          {(result || (activeJob && activeJob.status === 'running')) && (
            <section className="panel-section">
              <div className="section-header">
                <div>
                  <span className="section-index">[02] Werkblatt-Protokoll</span>
                  <h2 className="section-heading">Stück &amp; Balgführung</h2>
                </div>
              </div>

              {result ? (
                <>
                  {result.video_frame_url && (
                    <div className="video-preview-frame">
                      <img
                        src={result.video_frame_url}
                        alt="Standbild der Harmonika-Aufnahme"
                      />
                      <div className="video-frame-caption">
                        <span>AUFNAHME: {result.original_filename}</span>
                        <span>{result.media_kind === 'VIDEO' ? 'VIDEO' : 'AUDIO'}</span>
                      </div>
                    </div>
                  )}

                  <table className="spec-table">
                    <tbody>
                      <tr>
                        <th>Aufnahme</th>
                        <td>{result.original_filename}</td>
                      </tr>
                      <tr>
                        <th>Format</th>
                        <td>{result.conversion_step}</td>
                      </tr>
                      <tr>
                        <th>Spieldauer &amp; Takt</th>
                        <td>
                          {result.duration_s.toFixed(1)} s · {result.time_signature} ({result.measures_count} Takte)
                        </td>
                      </tr>
                      <tr>
                        <th>Balgführung</th>
                        <td>
                          {result.druck_measures} Takte Druck · {result.zug_measures} Takte Zug
                        </td>
                      </tr>
                      <tr>
                        <th>Verwendete Reihen</th>
                        <td>{result.rows_used.join(' / ')}</td>
                      </tr>
                      <tr>
                        <th>Erstellt in</th>
                        <td>{result.processing_time_s.toFixed(1)} Sekunden</td>
                      </tr>
                    </tbody>
                  </table>
                </>
              ) : activeJob ? (
                <div className="active-job-mini-status">
                  <table className="spec-table">
                    <tbody>
                      <tr>
                        <th>Aufnahme</th>
                        <td>{activeJob.filename}</td>
                      </tr>
                      <tr>
                        <th>Status</th>
                        <td>
                          <span className={`status-pill pill-${activeJob.status}`}>
                            {activeJob.status === 'running'
                              ? `● In Arbeit (${activeJob.progress_percent}%)`
                              : activeJob.status.toUpperCase()}
                          </span>
                        </td>
                      </tr>
                      <tr>
                        <th>Aktueller Schritt</th>
                        <td>{activeJob.current_stage_label}</td>
                      </tr>
                      <tr>
                        <th>Dauer</th>
                        <td>{formatSeconds(activeJob.elapsed_s)}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              ) : null}
            </section>
          )}

          {/* [03] Hörprobe: Only visible when result exists */}
          {result && (
            <section className="panel-section">
              <div className="section-header">
                <div>
                  <span className="section-index">[03] Hörprobe</span>
                  <h2 className="section-heading">Akustischer Gehörabgleich</h2>
                </div>
              </div>

              <div className="audio-tabs" role="tablist">
                <button
                  type="button"
                  className={`audio-tab ${audioMode === 'stereo' ? 'active' : ''}`}
                  onClick={() => setAudioMode('stereo')}
                >
                  Gehörvergleich (L/R)
                </button>
                <button
                  type="button"
                  className={`audio-tab ${audioMode === 'synth' ? 'active' : ''}`}
                  onClick={() => setAudioMode('synth')}
                >
                  Nur Notensatz
                </button>
                <button
                  type="button"
                  className={`audio-tab ${audioMode === 'original' ? 'active' : ''}`}
                  onClick={() => setAudioMode('original')}
                >
                  Originalaufnahme
                </button>
              </div>

              <audio
                key={activeAudioUrl}
                className="audio-player-element"
                controls
                preload="metadata"
                src={activeAudioUrl}
              />
              <p className="audio-hint">
                {audioMode === 'stereo' &&
                  'Links: Deine Originalaufnahme · Rechts: Klang exakt nach dem erstellten Notenblatt.'}
                {audioMode === 'synth' &&
                  'Spielt ausschließlich die Melodie und Begleitbässe des erzeugten Notenblatts.'}
                {audioMode === 'original' &&
                  'Die Tonspur deiner hochgeladenen Aufnahme.'}
              </p>
            </section>
          )}

          {/* [04] Griffschrift-Kurzlegende: Only visible when result exists */}
          {result && (
            <section className="panel-section">
              <div className="section-header">
                <div>
                  <span className="section-index">[04] Lesehilfe</span>
                  <h2 className="section-heading">Griffschrift nach Max Rosenzopf</h2>
                </div>
              </div>
              <div className="legend-grid">
                <div className="legend-item">
                  <span className="legend-symbol">● Runder Notenkopf</span>
                  <span className="legend-desc">1. oder 2. Reihe (Grundtonart)</span>
                </div>
                <div className="legend-item">
                  <span className="legend-symbol">× Kreuz-Notenkopf</span>
                  <span className="legend-desc">3. oder 4. Reihe (Trio/Nebentonarten)</span>
                </div>
                <div className="legend-item">
                  <span className="legend-symbol">▬ Druckbalken</span>
                  <span className="legend-desc">Balg zusammendrücken (ohne Balken = Balg auf Zug)</span>
                </div>
                <div className="legend-item">
                  <span className="legend-symbol">B b / C c</span>
                  <span className="legend-desc">Grundbass &amp; Begleitakkord (2. bzw. 3. Reihe)</span>
                </div>
              </div>
            </section>
          )}
        </aside>

        {/* Right Stage: Sheet Music Viewer + Embedded PDF Viewer + Download */}
        <section className="stage-column">
          {/* Stage Toolbar: Only rendered when there are views or active progress to display */}
          {(result || activeJob) && (
            <div className="stage-toolbar">
              <div className="view-mode-group" role="tablist" aria-label="Ansichtsmodus">
                {result && (
                  <>
                    <button
                      type="button"
                      className={`mode-btn ${viewMode === 'sheet' ? 'active' : ''}`}
                      onClick={() => setViewMode('sheet')}
                    >
                      Noten &amp; Griffschrift ({result.pages.length} Seiten)
                    </button>
                    <button
                      type="button"
                      className={`mode-btn ${viewMode === 'pdf' ? 'active' : ''}`}
                      onClick={() => setViewMode('pdf')}
                    >
                      Notenblatt als PDF
                    </button>
                  </>
                )}
                {activeJob && (
                  <button
                    type="button"
                    className={`mode-btn ${viewMode === 'progress' ? 'active' : ''}`}
                    onClick={() => setViewMode('progress')}
                  >
                    Schritt-für-Schritt Verlauf {isLoading ? `(${activeJob.progress_percent}%)` : '✓'}
                  </button>
                )}
              </div>

              {result && (
                <div className="toolbar-actions">
                  <button
                    type="button"
                    className={`mode-btn ${zoomed ? 'active' : ''}`}
                    onClick={() => setZoomed(!zoomed)}
                  >
                    {zoomed ? 'Normalansicht' : 'Vergrößern (+)'}
                  </button>
                  <a
                    className="btn btn-secondary"
                    href={result.musicxml_url}
                    download={`${result.job_id}_Normalnoten_Griffschrift.musicxml`}
                    style={{ backgroundColor: 'var(--bg-sheet)', color: 'var(--ink)' }}
                  >
                    Notendatei (.musicxml)
                  </a>
                  <a
                    className="btn btn-copper"
                    href={`${result.pdf_url}?download=true`}
                    download={`${result.job_id}_Normalnoten_Griffschrift_A4.pdf`}
                  >
                    DIN-A4 Noten drucken (PDF)
                  </a>
                </div>
              )}
            </div>
          )}

          <div className="stage-viewport">
            {errorMsg && (
              <div className="status-callout error">
                <strong>HINWEIS:</strong> {errorMsg}
              </div>
            )}

            {/* LIVE PIPELINE PROGRESS BOARD */}
            {viewMode === 'progress' && activeJob && (
              <div className="pipeline-progress-board">
                {/* Header with Title, Status & Big Percentage */}
                <div className="progress-board-header">
                  <div>
                    <span className="progress-kicker">
                      [NOTENSATZ IN ARBEIT · AUFTRAG #{activeJob.job_id}]
                    </span>
                    <h2 className="progress-board-title">{activeJob.filename}</h2>
                    <p className="progress-board-subtitle">
                      {activeJob.current_stage_label} — {activeJob.current_stage_detail}
                    </p>
                  </div>
                  <div className="progress-metrics-box">
                    <span className="progress-timer">
                      {formatSeconds(activeJob.elapsed_s)}
                    </span>
                    <span className="progress-percent-huge">
                      {activeJob.progress_percent}%
                    </span>
                  </div>
                </div>

                {/* Tactile Mechanical Progress Bar */}
                <div className="progress-gauge-container">
                  <div className="progress-gauge-track">
                    <div
                      className="progress-gauge-fill"
                      style={{ width: `${Math.max(activeJob.progress_percent, 2)}%` }}
                    />
                    <div className="progress-gauge-ticks">
                      {[1, 2, 3, 4, 5, 6, 7].map((tick) => (
                        <span
                          key={tick}
                          className="gauge-tick"
                          style={{ left: `${(tick / 8) * 100}%` }}
                        />
                      ))}
                    </div>
                  </div>
                  <div className="progress-gauge-meta">
                    <span className="gauge-stage-tag">
                      SCHRITT {activeJob.stages.findIndex((s) => s.id === activeJob.current_stage_id) + 1} VON 8
                    </span>
                    <span className="gauge-state-badge">
                      {activeJob.status === 'completed'
                        ? '✓ NOTENBLATT FERTIG'
                        : activeJob.status === 'failed'
                          ? '✕ ABGEBROCHEN'
                          : '● WIRD ERSTELLT'}
                    </span>
                  </div>
                </div>

                {/* Stage-by-Stage Ledger (8 Steps) */}
                <div className="pipeline-stages-list">
                  {activeJob.stages.map((stage) => {
                    const isRunning = stage.status === 'running';
                    const isDone = stage.status === 'completed';
                    const isFail = stage.status === 'failed';

                    return (
                      <div
                        key={stage.id}
                        className={`pipeline-stage-card status-${stage.status}`}
                      >
                        <div className="stage-card-left">
                          <span className="stage-card-step">[{stage.step}]</span>
                          <div className="stage-card-info">
                            <strong className="stage-card-title">{stage.title}</strong>
                            <p className="stage-card-desc">{stage.description}</p>
                            {stage.detail && (
                              <p className="stage-card-detail">
                                ↳ {stage.detail}
                              </p>
                            )}
                          </div>
                        </div>

                        <div className="stage-card-right">
                          {isDone && (
                            <span className="stage-badge badge-done">
                              ✓ FERTIG {stage.duration_s ? `(${stage.duration_s.toFixed(1)}s)` : ''}
                            </span>
                          )}
                          {isRunning && (
                            <span className="stage-badge badge-running">
                              <span className="running-pulse-dot" /> IN ARBEIT
                            </span>
                          )}
                          {isFail && (
                            <span className="stage-badge badge-failed">
                              ✕ HINWEIS
                            </span>
                          )}
                          {stage.status === 'pending' && (
                            <span className="stage-badge badge-pending">
                              ○ WARTEND
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Action Row when Completed */}
                {result && (
                  <div className="progress-success-action-row">
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => setViewMode('sheet')}
                    >
                      Zum Notenblatt wechseln ({result.pages.length} Seiten) →
                    </button>
                    <a
                      className="btn btn-copper"
                      href={`${result.pdf_url}?download=true`}
                      download={`${result.job_id}_Normalnoten_Griffschrift_A4.pdf`}
                    >
                      Notenblatt drucken (PDF)
                    </a>
                  </div>
                )}

                {/* Action Row when Failed / Notice */}
                {activeJob.status === 'failed' && (
                  <div className="progress-success-action-row">
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => {
                        setActiveJob(null);
                        setViewMode('sheet');
                        setSelectedFile(null);
                      }}
                    >
                      ← Andere Aufnahme auswählen
                    </button>
                  </div>
                )}

                {/* Monospace Log View */}
                <div className="telemetry-terminal-box">
                  <div className="telemetry-terminal-bar">
                    <span className="terminal-title">
                      SCHRITT-FÜR-SCHRITT VERLAUF ({activeJob.logs.length} EINTRÄGE)
                    </span>
                    <span className="terminal-indicator">
                      {activeJob.status === 'running' ? '● AKTIV' : 'BEREIT'}
                    </span>
                  </div>
                  <div className="telemetry-terminal-viewport">
                    {activeJob.logs.map((log, idx) => (
                      <div key={idx} className={`terminal-line level-${log.level}`}>
                        <span className="terminal-time">[{log.time}]</span>
                        <span className="terminal-msg">{log.text}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* MINIMALIST, FOCUSED EMPTY STATE CANVAS (ONLY NECESSARY UI) */}
            {!result && !isLoading && viewMode !== 'progress' && (
              <div className="empty-stage-canvas">
                <div
                  className={`empty-blueprint-sheet drop-active-target ${dragActive ? 'drag-active' : ''}`}
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragActive(true);
                  }}
                  onDragLeave={() => setDragActive(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragActive(false);
                    handleFilePicked(e.dataTransfer.files?.[0]);
                  }}
                >
                  <div className="blueprint-corner top-left">+</div>
                  <div className="blueprint-corner top-right">+</div>
                  <div className="blueprint-corner bottom-left">+</div>
                  <div className="blueprint-corner bottom-right">+</div>

                  <div className="blueprint-header">
                    <span className="blueprint-tag">DIN A4 NOTENBOGEN · STIMMUNG G-C-F-B</span>
                    <span className="blueprint-id">SYSTEM MAX ROSENZOPF</span>
                  </div>

                  <div className="blueprint-body empty-focused-body">
                    <h3 className="blueprint-title">Musikaufnahme hier ablegen</h3>
                    <p className="blueprint-lead">
                      Ziehe eine Video- oder Tonaufnahme deines Stücks hierher oder wähle links eine Datei aus, um
                      automatisch Normalnoten und spielbare Griffschrift zu erstellen.
                    </p>

                    <div className="empty-format-pills">
                      <span className="format-pill">MP4</span>
                      <span className="format-pill">MOV</span>
                      <span className="format-pill">WAV</span>
                      <span className="format-pill">MP3</span>
                      <span className="format-pill">M4A</span>
                    </div>

                    <div className="blueprint-cta-row">
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={(e) => {
                          e.stopPropagation();
                          fileInputRef.current?.click();
                        }}
                      >
                        Aufnahme auswählen
                      </button>
                      <span className="blueprint-cta-hint">
                        Unterstützt Video- und Tonaufnahmen (Handy, MP3, WAV)
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* SHEET MUSIC VIEW */}
            {result && viewMode === 'sheet' && (
              <>
                <div className="page-switcher-bar">
                  <span>
                    <strong>STÜCK:</strong> {result.title}
                  </span>
                  <div className="page-pill-group">
                    <button
                      type="button"
                      className={`mode-btn ${pageFilter === 'all' ? 'active' : ''}`}
                      onClick={() => setPageFilter('all')}
                    >
                      Alle {result.pages.length} Seiten untereinander
                    </button>
                    {result.pages.map((p) => (
                      <button
                        key={p.page_number}
                        type="button"
                        className={`mode-btn ${pageFilter === p.page_number ? 'active' : ''}`}
                        onClick={() => setPageFilter(p.page_number)}
                      >
                        Seite {p.page_number}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="sheet-pages-stack">
                  {visiblePages.map((page) => (
                    <article
                      key={page.page_number}
                      className={`sheet-page-card ${zoomed ? 'zoomed' : ''}`}
                    >
                      <div className="sheet-page-header">
                        <span>{page.caption}</span>
                        <span>DIN A4 · STIMMUNG G-C-F-B · SYSTEM ROSENZOPF</span>
                      </div>
                      <img
                        className="sheet-page-image"
                        src={page.png_url}
                        alt={page.caption}
                        loading="lazy"
                      />
                    </article>
                  ))}
                </div>
              </>
            )}

            {/* ORIGINAL PDF EMBED VIEW */}
            {result && viewMode === 'pdf' && (
              <div className="pdf-embed-wrapper">
                <iframe
                  className="pdf-iframe"
                  src={`${result.pdf_url}#toolbar=1&navpanes=0&scrollbar=1`}
                  title="DIN-A4 Notenblatt als PDF"
                />
              </div>
            )}
          </div>
        </section>
      </main>

      <footer className="footer-spec">
        <div className="footer-row">
          <span>Harmonika-Stimmung: G-C-F-B (4-reihig)</span>
          <span>Griffschrift: System Max Rosenzopf</span>
          <span>Notensatz: Zweizeilig (Normalnoten oben, Griffschrift unten mit durchgehendem Druckbalken)</span>
          <span>Balgführung: Minimierte Balgwechsel · Spielbare Handspanne</span>
        </div>
      </footer>
    </div>
  );
}
