import React from 'react';

export default function CoachLoadNotice({ isLoading, error, count, retry }) {
  if (isLoading) return <p role="status" className="py-6 text-center text-[#475569]">正在載入教練資料…</p>;
  if (error) return <div role="alert" className="mb-6 rounded-xl border border-red-200 bg-red-50 p-4 text-center text-red-700">教練資料載入失敗。<button type="button" className="ml-2 min-h-11 px-3 underline" onClick={retry}>重新載入</button></div>;
  if (!count) return <p className="py-6 text-center text-[#475569]">目前沒有上架的教練資料。</p>;
  return null;
}
