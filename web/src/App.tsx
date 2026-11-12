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

type ViewMode = 'sheet' | 'pdf';
type PageDisplayFilter = 'all' | number;
type AudioTrackMode = 'stereo' | 'synth' | 'original';

export default function App() {
  const [result, setResult] = useState<TranscriptionResult | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [customTitle, setCustomTitle] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [loadingStage, setLoadingStage] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState<boolean>(false);

  const [viewMode, setViewMode] = useState<ViewMode>('sheet');
  const [pageFilter, setPageFilter] = useState<PageDisplayFilter>('all');
  const [zoomed, setZoomed] = useState<boolean>(false);
  const [audioMode, setAudioMode] = useState<AudioTrackMode>('stereo');
  const [gpuLabel, setGpuLabel] = useState<string>('CUDA / Verovio Ready');

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then((d) => {
        if (d.gpu) {
          setGpuLabel(`${d.gpu} · FFmpeg ${d.ffmpeg_available ? 'Aktiv' : 'Inaktiv'}`);
        }
      })
      .catch(() => {});
  }, []);

  function handleFilePicked(file: File | undefined) {
    if (!file) return;
    setSelectedFile(file);
    setErrorMsg(null);
    if (!customTitle.trim()) {
      const baseName = file.name.replace(/\.[^/.]+$/, '');
      setCustomTitle(baseName);
    }
  }

  async function handleRunPipeline(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedFile) return;

    setErrorMsg(null);
    setIsLoading(true);
    const isVideo = /\.(mp4|mov|webm|mkv|avi|m4v|3gp)$/i.test(selectedFile.name);
    setLoadingStage(
      isVideo
        ? '1/3 FFmpeg extrahiert 22.05 kHz Mono-Audio aus Video → 2/3 KI-Transkription & Viterbi → 3/3 DIN-A4 PDF-Stich…'
        : '1/2 KI-Transkription & Viterbi-Optimierung (Druck/Zug) → 2/2 DIN-A4 PDF-Stich…',
    );

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

      const data: TranscriptionResult = await resp.json();
      setResult(data);
      setPageFilter('all');
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Fehler bei der Verarbeitung.');
    } finally {
      setIsLoading(false);
      setLoadingStage('');
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
            Notenstich-Werkbank · Steirische Harmonika (Stimmung G-C-F-B · System Max Rosenzopf)
          </span>
          <span className="masthead-status">
            <span className="status-dot" />
            {gpuLabel}
          </span>
        </div>
        <div className="masthead-title-row">
          <h1 className="masthead-title">Normalnoten &amp; Griffschrift</h1>
          <p className="masthead-subtitle">
            Video-/Audio-Ingest → KI-Transkription → Viterbi-Zug/Druck-Optimierer → DIN-A4 Druckbogen
          </p>
        </div>
      </header>

      <main className="workbench">
        {/* Left Column: Upload, Technical Spec Ledger & Audio Verification */}
        <aside className="sidebar-column">
          {/* [01] Datei-Upload (Audio & Video) */}
          <section className="panel-section">
            <div className="section-header">
              <div>
                <span className="section-index">[01] Quelle einspeisen</span>
                <h2 className="section-heading">Audio- oder Videodatei</h2>
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
                  Video (.MP4, .MOV, .WEBM) · Audio (.WAV, .MP3, .M4A, .FLAC)
                </div>
                <div className="dropzone-main">
                  Datei hier ablegen oder antippen zum Auswählen
                </div>
                <p className="dropzone-hint">
                  Bei Videodateien extrahiert die Pipeline automatisch die Audiospur (22.05 kHz Mono WAV)
                  vor der Notenübersetzung.
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
                    <strong>Gewählt:</strong> {selectedFile.name} (
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
                />
              </div>

              <div className="btn-row">
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={!selectedFile || isLoading}
                >
                  {isLoading
                    ? 'Pipeline rechnet…'
                    : 'In Noten + Griffschrift übersetzen'}
                </button>
              </div>
            </form>
          </section>

          {/* [02] Technische Werkdaten & Video-Konvertierungs-Status */}
          <section className="panel-section">
            <div className="section-header">
              <div>
                <span className="section-index">[02] Werkblatt-Protokoll</span>
                <h2 className="section-heading">Konvertierung &amp; Analyse</h2>
              </div>
            </div>

            {result ? (
              <>
                {result.video_frame_url && (
                  <div className="video-preview-frame">
                    <img
                      src={result.video_frame_url}
                      alt="Extrahierter Video-Frame der Harmonika-Aufnahme"
                    />
                    <div className="video-frame-caption">
                      <span>QUELLE: {result.original_filename}</span>
                      <span>VIDEO → AUDIO</span>
                    </div>
                  </div>
                )}

                <table className="spec-table">
                  <tbody>
                    <tr>
                      <th>Eingang</th>
                      <td>
                        {result.media_kind}: {result.original_filename}
                      </td>
                    </tr>
                    <tr>
                      <th>Medien-Pipeline</th>
                      <td>{result.conversion_step}</td>
                    </tr>
                    <tr>
                      <th>Laufzeit / Takt</th>
                      <td>
                        {result.duration_s.toFixed(1)} s · {result.time_signature} ({result.measures_count}{' '}
                        Takte)
                      </td>
                    </tr>
                    <tr>
                      <th>Balgrichtung</th>
                      <td>
                        {result.druck_measures} Takte DRUCK · {result.zug_measures} Takte ZUG
                      </td>
                    </tr>
                    <tr>
                      <th>Aktive Reihen</th>
                      <td>{result.rows_used.join(' / ')}</td>
                    </tr>
                  </tbody>
                </table>
              </>
            ) : (
              <div className="empty-panel-placeholder">
                <table className="spec-table muted">
                  <tbody>
                    <tr>
                      <th>Eingang</th>
                      <td>Keine Datei gewählt</td>
                    </tr>
                    <tr>
                      <th>Medien-Pipeline</th>
                      <td>Wartet auf Audio-/Video-Upload…</td>
                    </tr>
                    <tr>
                      <th>Laufzeit / Takt</th>
                      <td>—</td>
                    </tr>
                    <tr>
                      <th>Balgrichtung</th>
                      <td>—</td>
                    </tr>
                    <tr>
                      <th>Aktive Reihen</th>
                      <td>—</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* [03] Akustische Gegenprobe (Audio-Diff) */}
          <section className="panel-section">
            <div className="section-header">
              <div>
                <span className="section-index">[03] Hörprobe</span>
                <h2 className="section-heading">Akustischer Noten-Abgleich</h2>
              </div>
            </div>

            {result ? (
              <>
                <div className="audio-tabs" role="tablist">
                  <button
                    type="button"
                    className={`audio-tab ${audioMode === 'stereo' ? 'active' : ''}`}
                    onClick={() => setAudioMode('stereo')}
                  >
                    Stereo-Diff (L/R)
                  </button>
                  <button
                    type="button"
                    className={`audio-tab ${audioMode === 'synth' ? 'active' : ''}`}
                    onClick={() => setAudioMode('synth')}
                  >
                    Nur Notenblatt
                  </button>
                  <button
                    type="button"
                    className={`audio-tab ${audioMode === 'original' ? 'active' : ''}`}
                    onClick={() => setAudioMode('original')}
                  >
                    Original-Ton
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
                    'Links: Original-Ton aus Video/Audio · Rechts: Synthese exakt nach generiertem Notenblatt.'}
                  {audioMode === 'synth' &&
                    'Spielt ausschließlich die erkannten Diskant-Noten + Helikon-Bässe des Notenblatts.'}
                  {audioMode === 'original' &&
                    'Die per FFmpeg aus der Quell-Datei extrahierte 22.05 kHz Mono-Audiospur.'}
                </p>
              </>
            ) : (
              <div className="empty-panel-placeholder">
                <div className="empty-audio-box">
                  <span className="empty-audio-kicker">3-Kanal Audio-Verifikation</span>
                  <p className="empty-audio-text">
                    Nach der Transkription stehen hier <strong>Stereo-Diff (L/R)</strong>, der{' '}
                    <strong>synthetisierte Harmonika-Notensatz</strong> und das{' '}
                    <strong>Original-Audio</strong> zum direkten Gehörabgleich bereit.
                  </p>
                </div>
              </div>
            )}
          </section>

          {/* [04] Kurz-Legende für Nicht-Musiker */}
          <section className="panel-section">
            <div className="section-header">
              <div>
                <span className="section-index">[04] Lesehilfe</span>
                <h2 className="section-heading">Griffschrift-Codierung</h2>
              </div>
            </div>
            <div className="legend-grid">
              <div className="legend-item">
                <span className="legend-symbol">● Runder Kopf</span>
                <span className="legend-desc">1. Reihe (Raum) oder 2. Reihe (Linie)</span>
              </div>
              <div className="legend-item">
                <span className="legend-symbol">× Kreuz-Kopf</span>
                <span className="legend-desc">3. Reihe (Raum) oder 4. Reihe (Linie)</span>
              </div>
              <div className="legend-item">
                <span className="legend-symbol">▬ Druckbalken</span>
                <span className="legend-desc">Balg zusammendrücken (ohne Balken = Zug)</span>
              </div>
              <div className="legend-item">
                <span className="legend-symbol">B b / C c</span>
                <span className="legend-desc">Grund- &amp; Akkordbass (2. bzw. 3. Reihe)</span>
              </div>
            </div>
          </section>
        </aside>

        {/* Right Stage: Sheet Music Viewer + Embedded PDF Viewer + Download */}
        <section className="stage-column">
          <div className="stage-toolbar">
            <div className="view-mode-group" role="tablist" aria-label="Ansichtsmodus">
              <button
                type="button"
                className={`mode-btn ${viewMode === 'sheet' ? 'active' : ''}`}
                onClick={() => setViewMode('sheet')}
              >
                Noten &amp; Griffschrift {result ? `(${result.pages.length} Seiten)` : '(0 Seiten)'}
              </button>
              <button
                type="button"
                className={`mode-btn ${viewMode === 'pdf' ? 'active' : ''}`}
                onClick={() => setViewMode('pdf')}
                disabled={!result}
                title={!result ? 'Erst nach Upload und Notenübersetzung verfügbar' : undefined}
              >
                Original PDF-Ansicht
              </button>
            </div>

            {result && (
              <div className="toolbar-actions">
                {viewMode === 'sheet' && (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setZoomed((z) => !z)}
                  >
                    {zoomed ? 'Zoom: Standard (A4)' : 'Zoom: Groß (135%)'}
                  </button>
                )}
                <a
                  className="btn btn-Secondary"
                  href={result.musicxml_url}
                  download={`${result.job_id}_kombi.musicxml`}
                  style={{ backgroundColor: 'var(--bg-sheet)', color: 'var(--ink)' }}
                >
                  MusicXML (.xml)
                </a>
                <a
                  className="btn btn-copper"
                  href={`${result.pdf_url}?download=true`}
                  download={`${result.job_id}_Normalnoten_Griffschrift_A4.pdf`}
                >
                  DIN-A4 PDF Herunterladen
                </a>
              </div>
            )}
          </div>

          <div className="stage-viewport">
            {isLoading && (
              <div className="status-callout">
                <strong>VERARBEITUNG LÄUFT:</strong> {loadingStage}
              </div>
            )}

            {errorMsg && (
              <div className="status-callout error">
                <strong>FEHLER:</strong> {errorMsg}
              </div>
            )}

            {!result && !isLoading && !errorMsg && (
              <div className="empty-stage-canvas">
                <div className="empty-blueprint-sheet">
                  <div className="blueprint-corner top-left">+</div>
                  <div className="blueprint-corner top-right">+</div>
                  <div className="blueprint-corner bottom-left">+</div>
                  <div className="blueprint-corner bottom-right">+</div>

                  <div className="blueprint-header">
                    <span className="blueprint-tag">DIN A4 DRUCKBOGEN · 210 × 297 MM · 300 DPI</span>
                    <span className="blueprint-id">NOTENPULT-WERKBANK</span>
                  </div>

                  <div className="blueprint-body">
                    <h3 className="blueprint-title">Noch kein Notenstich geladen</h3>
                    <p className="blueprint-lead">
                      Wähle in der linken Seitenleiste eine Audio- oder Videodatei aus, um die
                      automatische Übersetzung in Normalnoten und spielbare Griffschrift (System Max
                      Rosenzopf) zu starten.
                    </p>

                    <div className="blueprint-workflow-grid">
                      <div className="blueprint-step">
                        <span className="step-num">01</span>
                        <strong>Medien-Ingest</strong>
                        <p>FFmpeg extrahiert bei Videos automatisch eine 22.05 kHz Mono-WAV-Spur.</p>
                      </div>
                      <div className="blueprint-step">
                        <span className="step-num">02</span>
                        <strong>KI-Transkription</strong>
                        <p>Beat-This, MuScriptor, CRNN &amp; Basic Pitch ermitteln Takte &amp; Noten.</p>
                      </div>
                      <div className="blueprint-step">
                        <span className="step-num">03</span>
                        <strong>Rosenzopf-Viterbi</strong>
                        <p>DAG berechnet globale Druck/Zug-Balgrichtung (Handspanne ≤ 5 Knöpfe).</p>
                      </div>
                      <div className="blueprint-step">
                        <span className="step-num">04</span>
                        <strong>Druckfertiges PDF</strong>
                        <p>Verovio graviert Noten + Griffschrift mit durchgehendem Druckbalken.</p>
                      </div>
                    </div>

                    <div className="blueprint-cta-row">
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={() => fileInputRef.current?.click()}
                      >
                        Datei auswählen
                      </button>
                      <span className="blueprint-cta-hint">
                        Unterstützt MP4, MOV, WEBM, WAV, MP3, M4A, FLAC
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {result && viewMode === 'sheet' && (
              <>
                <div className="page-switcher-bar">
                  <span>
                    <strong>WERK:</strong> {result.title}
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
                        <span>DIN A4 · 300 DPI · VEROVIO + ROSENZOPF-STICH</span>
                      </div>
                      <img
                        className="sheet-page-image"
                        src={page.png_url}
                        alt={page.caption}
                        loading="eager"
                      />
                    </article>
                  ))}
                </div>
              </>
            )}

            {result && viewMode === 'pdf' && (
              <div className="pdf-iframe-container">
                <div className="sheet-page-header">
                  <span>DRUCKFERTIGES DOKUMENT: {result.title} (DIN A4)</span>
                  <a
                    href={result.pdf_url}
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: 'var(--accent-pine)', fontWeight: 700 }}
                  >
                    In neuem Browser-Tab öffnen ↗
                  </a>
                </div>
                <iframe
                  className="pdf-iframe"
                  src={result.pdf_url}
                  title="DIN-A4 PDF Vorschau"
                />
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
