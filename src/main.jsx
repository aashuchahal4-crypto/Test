import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { invoke } from '@tauri-apps/api/core';
import './styles.css';

const api = async (path, payload) => {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
};

const getApi = async path => {
  const response = await fetch(path);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
};

const call = async (command, payload = {}) => {
  if (window.__TAURI_INTERNALS__) return invoke(command, payload);
  if (command === 'ai_status') return JSON.stringify(await getApi('/api/ai-status'));
  if (command === 'image_engines_status') return JSON.stringify(await getApi('/api/image-engines'));
  if (command === 'generate_scenes') return JSON.stringify(await api('/api/generate-scenes', payload));
  if (command === 'generate_images') return JSON.stringify(await api('/api/generate-images', payload.request));
  if (command === 'render_video') return JSON.stringify(await api('/api/render-video', payload.request));
  if (command === 'reveal_path') {
    alert(`Output saved locally:\n${payload.path}`);
    return null;
  }
  throw new Error(`Unknown command: ${command}`);
};

const imageEngineFallback = [
  { id: 'pollinations', label: 'Pollinations (fast)', available: true },
  { id: 'cloudflare', label: 'Cloudflare AI (stable)', available: false },
  { id: 'replicate', label: 'Replicate (multi-model)', available: false },
  { id: 'puter', label: 'Puter.js (frontend fallback)', available: true },
  { id: 'templates', label: 'Templates (always safe)', available: true }
];

const sampleProject = {
  id: 'draft',
  prompt: '',
  video_type: 'explainer',
  duration: 24,
  style: 'neon',
  language: 'en-US',
  voice: 'auto',
  created_at: new Date().toISOString(),
  scenes: []
};

function App() {
  const [prompt, setPrompt] = useState('Explain how Snapdragon X NPU acceleration makes local AI useful for creators.');
  const [videoType, setVideoType] = useState('explainer');
  const [duration, setDuration] = useState(24);
  const [style, setStyle] = useState('neon');
  const [language, setLanguage] = useState('en-US');
  const [voice, setVoice] = useState('auto');
  const [project, setProject] = useState(sampleProject);
  const [generateImages, setGenerateImages] = useState(false);
  const [imageEngine, setImageEngine] = useState('pollinations');
  const [imageEngines, setImageEngines] = useState(imageEngineFallback);
  const [status, setStatus] = useState('Ready. Foundry Local will select the best available QNN NPU model.');
  const [aiStatus, setAiStatus] = useState({ backend: 'Foundry Local', model: 'Detecting...', device: 'NPU (QNN)' });
  const [renderResult, setRenderResult] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isRendering, setIsRendering] = useState(false);
  const [renderProgress, setRenderProgress] = useState(null);
  const [generationProgress, setGenerationProgress] = useState(null);
  const [imageProgress, setImageProgress] = useState(null);
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'system');
  const totalDuration = useMemo(() => project.scenes.reduce((sum, scene) => sum + Number(scene.duration || 0), 0), [project]);
  const selectedImageEngine = imageEngines.find(engine => engine.id === imageEngine) || imageEngines[0] || imageEngineFallback[0];

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    refreshAiStatus();
    refreshImageEngines();
  }, []);

  async function refreshAiStatus() {
    try {
      const text = await call('ai_status');
      const parsed = JSON.parse(text);
      setAiStatus(parsed);
      refreshImageEngines();
      setStatus(`AI Backend: ${parsed.backend}. Model: ${parsed.model}. Device: ${parsed.device}.`);
    } catch (error) {
      setAiStatus({ backend: 'Foundry Local', model: 'Unavailable', device: 'NPU (QNN)', error: error.message || String(error) });
      setStatus(`Foundry Local unavailable: ${error.message || error}`);
    }
  }

  async function refreshImageEngines() {
    try {
      const text = await call('image_engines_status');
      const parsed = JSON.parse(text);
      const engines = parsed.image_engines?.engines || parsed.engines;
      const defaultEngine = parsed.image_engines?.default || parsed.default || 'pollinations';
      if (Array.isArray(engines) && engines.length) {
        setImageEngines(engines);
        setImageEngine(current => engines.some(engine => engine.id === current) ? current : defaultEngine);
      }
    } catch (error) {
      setImageEngines(imageEngineFallback.map(engine => engine.id === 'cloudflare' || engine.id === 'replicate' ? { ...engine, available: false, error: error.message || String(error) } : engine));
    }
  }

  async function generateScenes() {
    if (isGenerating || isRendering) return;
    setIsGenerating(true);
    setStatus('Generating scene JSON with Foundry Local on NPU...');
    setGenerationProgress({ progress: 4, message: 'Starting local NPU script + scene generation' });
    setRenderResult(null);
    setRenderProgress(null);
    const progressTimer = window.setInterval(() => {
      setGenerationProgress(prev => prev ? { ...prev, progress: Math.min(92, (prev.progress || 0) + 6), message: prev.progress > 55 ? 'Validating strict scene JSON schema' : 'Generating script and scene plan locally' } : prev);
    }, 700);
    try {
      const text = await call('generate_scenes', { prompt, videoType, duration: Number(duration), style, language, voice, generateImages, imageEngine });
      const parsed = JSON.parse(text);
      setProject({ ...parsed, voice });
      await refreshAiStatus();
      setGenerationProgress({ progress: 100, message: 'Scene JSON validated' });
      setStatus(`Generated ${parsed.scenes.length} editable scenes with Foundry Local NPU inference.`);
    } catch (error) {
      setGenerationProgress({ progress: 100, message: 'Generation failed' });
      setStatus(`Scene generation failed: ${error.message || error}`);
    } finally {
      window.clearInterval(progressTimer);
      setIsGenerating(false);
    }
  }

  async function generateImagePreviews() {
    if (isGenerating || isRendering) return;
    if (!project.scenes.length) {
      setStatus('Generate or add scenes before creating image previews.');
      return;
    }
    setIsRendering(true);
    setImageProgress({ progress: 0, message: `Starting ${selectedImageEngine?.label || imageEngine} image previews` });
    setStatus(`Generating scene previews with ${selectedImageEngine?.label || imageEngine}.`);
    try {
      const text = await call('generate_images', { request: { engine: imageEngine, projectJson: JSON.stringify({ ...project, generate_images: true, image_engine: imageEngine }, null, 2) } });
      const started = JSON.parse(text);
      if (!started.job_id) {
        setProject(started);
        setImageProgress({ progress: 100, message: 'Scene images ready' });
        setStatus('Scene previews are ready.');
        return;
      }
      await pollJob(started.job_id, setImageProgress, job => {
        setProject(job.result);
        setStatus('Scene previews are ready.');
      });
    } catch (error) {
      setImageProgress({ progress: 100, message: 'Image preview generation failed' });
      setStatus(`Image previews failed: ${error.message || error}`);
    } finally {
      setIsRendering(false);
    }
  }

  async function renderVideo() {
    if (isRendering || isGenerating) return;
    if (!project.scenes.length) {
      setStatus('Generate or add at least one scene first.');
      return;
    }
    setIsRendering(true);
    setRenderResult(null);
    setRenderProgress({ progress: 0, message: 'Starting CPU render job' });
    setStatus('Rendering locally with FFmpeg on CPU. NPU remains reserved for AI inference.');
    try {
      const renderProject = { ...project, language, voice, generate_images: generateImages, image_engine: imageEngine };
      const text = await call('render_video', { request: { projectJson: JSON.stringify(renderProject, null, 2) } });
      const started = JSON.parse(text);
      if (!started.job_id) {
        setRenderResult(started);
        setRenderProgress({ progress: 100, message: 'Render complete' });
        setStatus(`Rendered ${started.scenes} scenes to ${started.video}`);
        return;
      }
      await pollRenderJob(started.job_id);
    } catch (error) {
      setRenderProgress({ progress: 100, message: 'Render failed' });
      setStatus(`Render failed: ${error.message || error}`);
    } finally {
      setIsRendering(false);
    }
  }

  async function pollRenderJob(jobId) {
    await pollJob(jobId, setRenderProgress, job => {
      setRenderResult(job.result);
      setRenderProgress({ progress: 100, message: job.result?.temp_cleaned ? 'Render complete. Temporary scene chunks cleaned.' : 'Render complete.' });
      setStatus(`Rendered ${job.result.scenes} scenes to ${job.result.video}`);
    });
  }

  async function pollJob(jobId, setProgress, onComplete) {
    while (true) {
      await new Promise(resolve => setTimeout(resolve, 900));
      const response = await fetch(`/api/render-progress?id=${encodeURIComponent(jobId)}`);
      const job = await response.json();
      if (!response.ok) throw new Error(job.error || `HTTP ${response.status}`);
      setProgress({ progress: job.progress || 0, message: job.message || job.status });
      setStatus(`${job.message || 'Rendering'} (${job.progress || 0}%)`);
      if (job.status === 'complete') {
        onComplete(job);
        return;
      }
      if (job.status === 'error') throw new Error(job.error || 'Render failed');
    }
  }

  function updateScene(index, field, value) {
    const numericFields = new Set(['duration', 'transition_duration']);
    setProject(prev => ({
      ...prev,
      scenes: prev.scenes.map((scene, i) => i === index ? { ...scene, [field]: numericFields.has(field) ? Number(value) : value } : scene)
    }));
  }

  function addScene() {
    setProject(prev => ({
      ...prev,
      scenes: [
        ...prev.scenes,
          {
            id: prev.scenes.length + 1,
            duration: 5,
            visual_prompt: `${style} visual scene with readable captions`,
            voice_text: 'Add narration for this scene.',
            subtitle: 'Add subtitle for this scene.',
            camera_movement: 'slow_zoom_in',
            transition: 'fade',
            transition_duration: 0.45,
            effects: 'slow_zoom',
            style
          }
      ]
    }));
  }

  function removeScene(index) {
    setProject(prev => ({
      ...prev,
      scenes: prev.scenes.filter((_, i) => i !== index).map((scene, i) => ({ ...scene, id: i + 1 }))
    }));
  }

  function moveScene(index, direction) {
    setProject(prev => {
      const nextIndex = index + direction;
      if (nextIndex < 0 || nextIndex >= prev.scenes.length) return prev;
      const scenes = [...prev.scenes];
      [scenes[index], scenes[nextIndex]] = [scenes[nextIndex], scenes[index]];
      return { ...prev, scenes: scenes.map((scene, i) => ({ ...scene, id: i + 1 })) };
    });
  }

  function assetUrl(path) {
    return path ? `/api/asset?path=${encodeURIComponent(path)}` : '';
  }

  return (
    <main>
      <section className="hero">
        <div>
          <div className="topline">
            <p className="eyebrow">Snapdragon X NPU local AI studio</p>
            <div className="theme-switch" aria-label="Theme selector">
              {['system', 'dark', 'light'].map(value => (
                <button
                  key={value}
                  type="button"
                  className={theme === value ? 'active' : ''}
                  onClick={() => setTheme(value)}
                >
                  {value}
                </button>
              ))}
            </div>
          </div>
          <h1>Foundry Local → NPU scene AI → CPU MP4 render</h1>
          <p className="subcopy">This build uses Microsoft Foundry Local only. It automatically selects a QNN NPU model, sends OpenAI-compatible chat requests locally, and keeps FFmpeg rendering on CPU.</p>
        </div>
        <div className="status-card">
          <span>AI Backend</span>
          <div className="backend-lines">
            <p><strong>{aiStatus.backend || 'Foundry Local'}</strong></p>
            <p>Model: <code>{aiStatus.model || 'Unavailable'}</code></p>
            <p>Device: <code>{aiStatus.device || 'NPU (QNN)'}</code></p>
            {aiStatus.error && <p className="error-text">{aiStatus.error}</p>}
          </div>
          <button className="secondary compact" onClick={refreshAiStatus} disabled={isGenerating || isRendering}>Refresh NPU status</button>
        </div>
      </section>

      <section className="status-strip">{status}</section>

      <section className="grid">
        <aside className="panel controls">
          <h2>Video Input</h2>
          <label>Idea prompt<textarea value={prompt} onChange={e => setPrompt(e.target.value)} rows={7} /></label>
          <div className="two">
            <label>Video type<select value={videoType} onChange={e => setVideoType(e.target.value)}><option>explainer</option><option>short</option><option>story</option><option>tutorial</option><option>ad</option></select></label>
            <label>Duration<input type="number" min="9" max="180" value={duration} onChange={e => setDuration(e.target.value)} /></label>
          </div>
          <div className="two">
            <label>Style<select value={style} onChange={e => setStyle(e.target.value)}><option>neon</option><option>brainrot</option><option>cinematic</option><option>documentary</option><option>minimal</option></select></label>
            <label>Language<select value={language} onChange={e => setLanguage(e.target.value)}><option value="en-US">English (US)</option><option value="en-GB">English (UK)</option><option value="hi-IN">Hindi</option><option value="es-ES">Spanish</option><option value="fr-FR">French</option><option value="de-DE">German</option><option value="it-IT">Italian</option><option value="pt-BR">Portuguese</option><option value="ja-JP">Japanese</option><option value="ko-KR">Korean</option></select></label>
          </div>
          <label>Voice<select value={voice} onChange={e => setVoice(e.target.value)}><option value="auto">Auto matching language</option><option value="female">Female voice</option><option value="male">Male voice</option></select></label>
          <label>Image engine<select value={imageEngine} onChange={e => setImageEngine(e.target.value)}>{imageEngines.map(engine => <option key={engine.id} value={engine.id}>{engine.label}</option>)}</select></label>
          <label className="check-row"><input type="checkbox" checked={generateImages} onChange={e => setGenerateImages(e.target.checked)} /> Generate scene images during render</label>
          <div className="mini-status"><strong>Image engine:</strong> {selectedImageEngine?.label || imageEngine} • {selectedImageEngine?.available ? 'Ready' : `Needs ${selectedImageEngine?.missing?.join(', ') || 'configuration'}`}</div>
          <button onClick={generateScenes} disabled={isGenerating || isRendering}>{isGenerating ? 'Generating with Foundry...' : 'Generate scene JSON on NPU'}</button>
          {generationProgress && (
            <div className="progress-card">
              <div className="progress-row"><span>{generationProgress.message}</span><strong>{Math.round(generationProgress.progress || 0)}%</strong></div>
              <div className="progress-track"><div style={{ width: `${Math.min(100, Math.max(0, generationProgress.progress || 0))}%` }} /></div>
              <small>Strict schema validation + retry runs before scenes reach the editor.</small>
            </div>
          )}
          <button className="secondary" onClick={addScene} disabled={isGenerating || isRendering}>Add blank scene</button>
          <button className="secondary" onClick={generateImagePreviews} disabled={isGenerating || isRendering || !project.scenes.length}>Generate image previews</button>
          {imageProgress && (
            <div className="progress-card">
              <div className="progress-row"><span>{imageProgress.message}</span><strong>{Math.round(imageProgress.progress || 0)}%</strong></div>
              <div className="progress-track"><div style={{ width: `${Math.min(100, Math.max(0, imageProgress.progress || 0))}%` }} /></div>
              <small>Images are cached locally and reused by the renderer.</small>
            </div>
          )}
          <button className="render" onClick={renderVideo} disabled={isGenerating || isRendering}>{isRendering ? 'Rendering on CPU...' : 'Render MP4 on CPU'}</button>
          {renderProgress && (
            <div className="progress-card">
              <div className="progress-row"><span>{renderProgress.message}</span><strong>{Math.round(renderProgress.progress || 0)}%</strong></div>
              <div className="progress-track"><div style={{ width: `${Math.min(100, Math.max(0, renderProgress.progress || 0))}%` }} /></div>
              <small>Text AI uses NPU. Image providers generate scene art; FFmpeg rendering stays on CPU.</small>
            </div>
          )}
        </aside>

        <section className="panel timeline">
          <div className="timeline-head">
            <div><h2>Scene Timeline</h2><p>{project.scenes.length} scenes • {totalDuration.toFixed(1)}s editable timeline</p></div>
            <code>{project.id}</code>
          </div>
          {!project.scenes.length && <div className="empty">No scenes yet. Generate from Foundry Local or add one manually.</div>}
          {project.scenes.map((scene, index) => (
            <article className="scene" key={`${scene.id}-${index}`}>
              <div className="scene-id">{scene.id}</div>
              <div className="scene-body">
                {scene.image_path ? <img className="scene-preview" src={assetUrl(scene.image_path)} alt={`Scene ${scene.id} preview`} /> : <div className="scene-preview placeholder">No preview yet</div>}
                <div className="three">
                  <label>Duration<input type="number" min="2" step="0.5" value={scene.duration} onChange={e => updateScene(index, 'duration', e.target.value)} /></label>
                  <label>Transition<select value={scene.transition || 'fade'} onChange={e => updateScene(index, 'transition', e.target.value)}><option>cut</option><option>fade</option><option>push</option><option>flash</option></select></label>
                  <label>Transition sec<input type="number" min="0" max="1.2" step="0.05" value={scene.transition_duration ?? 0.45} onChange={e => updateScene(index, 'transition_duration', e.target.value)} /></label>
                </div>
                <div className="three">
                  <label>Camera<select value={scene.camera_movement || 'slow_zoom_in'} onChange={e => updateScene(index, 'camera_movement', e.target.value)}><option>slow_zoom_in</option><option>slow_zoom_out</option><option>pan_left</option><option>pan_right</option><option>tilt_up</option><option>static</option></select></label>
                  <label>Effects<select value={scene.effects || 'slow_zoom'} onChange={e => updateScene(index, 'effects', e.target.value)}><option>slow_zoom</option><option>caption_pop</option><option>pan_left</option><option>pulse</option><option>grain</option></select></label>
                  <label>Style<input value={scene.style || style} onChange={e => updateScene(index, 'style', e.target.value)} /></label>
                </div>
                <label>Visual prompt<textarea rows="2" value={scene.visual_prompt} onChange={e => updateScene(index, 'visual_prompt', e.target.value)} /></label>
                <label>Voiceover<textarea rows="3" value={scene.voice_text} onChange={e => updateScene(index, 'voice_text', e.target.value)} /></label>
                <label>Subtitle<textarea rows="2" value={scene.subtitle || scene.voice_text} onChange={e => updateScene(index, 'subtitle', e.target.value)} /></label>
              </div>
              <div className="scene-actions">
                <button className="secondary compact" onClick={() => moveScene(index, -1)} disabled={index === 0}>Up</button>
                <button className="secondary compact" onClick={() => moveScene(index, 1)} disabled={index === project.scenes.length - 1}>Down</button>
                <button className="danger" onClick={() => removeScene(index)}>Remove</button>
              </div>
            </article>
          ))}
        </section>
      </section>

      <section className="panel output">
        <h2>Export Manager</h2>
        {renderResult ? (
          <div className="result">
            <p><strong>Video:</strong> <code>{renderResult.video}</code></p>
            <p><strong>Subtitles:</strong> <code>{renderResult.subtitles}</code></p>
            <p><strong>Project JSON:</strong> <code>{renderResult.project}</code></p>
            {renderResult.temp_cleaned && <p><strong>Cleanup:</strong> temporary scene/audio chunks were deleted automatically.</p>}
            <button onClick={() => call('reveal_path', { path: renderResult.video })}>Open rendered video</button>
          </div>
        ) : <p>Render outputs appear in <code>storage/outputs</code>.</p>}
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
