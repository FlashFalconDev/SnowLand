import React, { useRef, useState } from 'react';
import { useSiteLocale } from '../../contexts/SiteLocale';

const WIDTH = 1000;
const HEIGHT = 400;
const MAX_POINTS = 3000;

function SignatureLines({ strokes }) {
  return strokes.map((stroke, index) => <polyline key={index}
    points={stroke.map(point => point.join(',')).join(' ')}
    fill="none" stroke="#172537" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />);
}

export function WaiverSignaturePreview({ strokes, label }) {
  return <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={label}
    className="mt-2 h-24 w-full max-w-sm rounded border border-[#cbd5e1] bg-white">
    <SignatureLines strokes={strokes} />
  </svg>;
}

export default function WaiverSignaturePad({ value, onConfirm, disabled }) {
  const { t } = useSiteLocale();
  const dialog = useRef(null);
  const pointer = useRef(null);
  const pointCount = useRef(0);
  const [strokes, setStrokes] = useState([]);
  const hasInk = strokes.some(stroke => stroke.some(([x, y]) => x !== stroke[0][0] || y !== stroke[0][1]));

  function point(event) {
    const rect = event.currentTarget.getBoundingClientRect();
    const scale = (value, size, max) => Math.min(max, Math.max(0, Math.round(value / size * max)));
    return [scale(event.clientX - rect.left, rect.width, WIDTH), scale(event.clientY - rect.top, rect.height, HEIGHT)];
  }

  function start(event) {
    if (!event.isPrimary || event.button !== 0 || pointCount.current >= MAX_POINTS || strokes.length >= 100) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    pointer.current = event.pointerId;
    pointCount.current += 1;
    const first = point(event);
    setStrokes(current => [...current, [first]]);
  }

  function draw(event) {
    if (pointer.current !== event.pointerId || pointCount.current >= MAX_POINTS) return;
    pointCount.current += 1;
    const next = point(event);
    setStrokes(current => [...current.slice(0, -1), [...current.at(-1), next]]);
  }

  function stop(event) {
    if (pointer.current === event.pointerId) pointer.current = null;
  }

  return <>
    <button type="button" disabled={disabled} onClick={() => {
      const initial = value || [];
      setStrokes(initial);
      pointCount.current = initial.reduce((sum, stroke) => sum + stroke.length, 0);
      dialog.current.showModal();
    }} className="mt-2 min-h-11 rounded-full border border-[#2b5f8f] px-4 text-sm font-semibold text-[#2b5f8f] disabled:opacity-40">
      {t(value?.length ? '重新手寫簽名' : '開啟電子簽名板')}
    </button>
    <dialog ref={dialog} aria-label={t('電子簽名')} onClose={() => { pointer.current = null; }}
      className="fixed inset-0 m-0 h-dvh max-h-none w-screen max-w-none flex-col gap-4 overflow-auto bg-white p-4 text-[#1f2937] open:flex sm:p-6">
      <header className="flex items-start justify-between gap-4">
        <div><h2 className="text-xl font-semibold">{t('電子簽名')}</h2><p className="mt-1 text-sm">{t('請用手指或滑鼠在框內簽名。')}</p></div>
        <button type="button" className="min-h-11 px-3" onClick={() => dialog.current.close()}>{t('取消')}</button>
      </header>
      <div className="flex flex-1 flex-col items-center justify-center">
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} aria-label={t('手寫簽名區')}
          className="aspect-[5/2] w-full max-w-5xl touch-none select-none rounded-lg border-2 border-dashed border-[#94a3b8] bg-[#f8fafc]"
          onPointerDown={start} onPointerMove={draw} onPointerUp={stop} onPointerCancel={stop} onLostPointerCapture={stop}>
          <SignatureLines strokes={strokes} />
        </svg>
      </div>
      <div className="flex justify-end gap-3">
        <button type="button" onClick={() => { pointer.current = null; pointCount.current = 0; setStrokes([]); }} className="min-h-11 rounded-full border px-4">{t('清除重簽')}</button>
        <button type="button" disabled={!hasInk} onClick={() => { onConfirm(strokes); dialog.current.close(); }}
          className="min-h-11 rounded-full bg-[#2b5f8f] px-4 text-white disabled:opacity-40">{t('完成簽名')}</button>
      </div>
    </dialog>
  </>;
}
