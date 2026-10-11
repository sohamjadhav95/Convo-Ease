// Image compression, voice recording and WAV conversion — all in the browser,
// so uploads stay small and every AI provider can read the audio.

export function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || '');
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('This file is not an image the browser can read.')); };
    img.src = url;
  });
}

const PASSTHROUGH_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp']);

/** Resize large photos to at most `maxDim` px and re-encode as JPEG. */
export async function prepareImage(file, { maxDim = 1600, quality = 0.85, maxBytes = 8 * 1024 * 1024 } = {}) {
  if (file.type === 'image/gif') {
    if (file.size > maxBytes) throw new Error('GIF is too large.');
    return { blob: file, mime: 'image/gif' };
  }
  const img = await loadImage(file);
  const scale = Math.min(1, maxDim / Math.max(img.naturalWidth, img.naturalHeight));
  if (scale === 1 && file.size <= 1.2 * 1024 * 1024 && PASSTHROUGH_TYPES.has(file.type)) {
    return { blob: file, mime: file.type };
  }
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(img.naturalWidth * scale));
  canvas.height = Math.max(1, Math.round(img.naturalHeight * scale));
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality));
  if (!blob) throw new Error('Could not process this image.');
  if (blob.size > maxBytes) throw new Error('Image is too large even after compression.');
  return { blob, mime: 'image/jpeg' };
}

// ── Voice recording ─────────────────────────────────────────────────────
export const MAX_RECORDING_SECONDS = 120;

export function canRecord() {
  return Boolean(navigator.mediaDevices?.getUserMedia && window.MediaRecorder);
}

export class VoiceRecorder {
  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
    });
    const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'];
    const mimeType = types.find((type) => MediaRecorder.isTypeSupported?.(type));
    this.recorder = new MediaRecorder(this.stream, mimeType ? { mimeType } : undefined);
    this.chunks = [];
    this.recorder.addEventListener('dataavailable', (event) => {
      if (event.data.size) this.chunks.push(event.data);
    });
    this.startedAt = performance.now();
    this.recorder.start(250);
  }

  get seconds() {
    return this.startedAt ? (performance.now() - this.startedAt) / 1000 : 0;
  }

  stop() {
    return new Promise((resolve) => {
      if (!this.recorder || this.recorder.state === 'inactive') {
        this.release();
        resolve(null);
        return;
      }
      this.recorder.addEventListener('stop', () => {
        const blob = new Blob(this.chunks, { type: this.recorder.mimeType || 'audio/webm' });
        this.release();
        resolve(blob);
      }, { once: true });
      this.recorder.stop();
    });
  }

  cancel() {
    if (this.recorder && this.recorder.state !== 'inactive') this.recorder.stop();
    this.release();
  }

  release() {
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
  }
}

// ── WAV conversion ──────────────────────────────────────────────────────
/** Decode any browser-playable audio and re-encode as 16 kHz mono 16-bit WAV. */
export async function toWav(blob, sampleRate = 16000) {
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  const context = new AudioCtx();
  let decoded;
  try {
    decoded = await context.decodeAudioData(await blob.arrayBuffer());
  } catch {
    throw new Error("This audio format can't be read by your browser.");
  } finally {
    context.close?.();
  }
  const frames = Math.max(1, Math.ceil(decoded.duration * sampleRate));
  const offline = new OfflineAudioContext(1, frames, sampleRate);
  const source = offline.createBufferSource();
  source.buffer = decoded;
  source.connect(offline.destination);
  source.start();
  const rendered = await offline.startRendering();
  return { blob: encodeWav(rendered.getChannelData(0), sampleRate), duration: decoded.duration };
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeString = (offset, text) => { for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i)); };
  writeString(0, 'RIFF');
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, 'data');
  view.setUint32(40, samples.length * 2, true);
  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([view], { type: 'audio/wav' });
}

/** Uploaded audio: keep MP3/WAV as they are, convert everything else to WAV. */
export async function prepareAudioFile(file, acceptedFormats = ['wav', 'mp3']) {
  const name = (file.name || '').toLowerCase();
  const isMp3 = file.type === 'audio/mpeg' || file.type === 'audio/mp3' || name.endsWith('.mp3');
  const isWav = /audio\/(x-)?wav|audio\/wave/.test(file.type) || name.endsWith('.wav');
  if (isMp3 && acceptedFormats.includes('mp3')) return { blob: file, mime: 'audio/mpeg' };
  if (isWav && acceptedFormats.includes('wav')) return { blob: file, mime: 'audio/wav' };
  const { blob } = await toWav(file);
  return { blob, mime: 'audio/wav' };
}
