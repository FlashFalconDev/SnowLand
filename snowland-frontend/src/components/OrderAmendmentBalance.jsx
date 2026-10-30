import React, { useCallback, useEffect, useRef, useState } from 'react';

const labels={topup_due:'待補款',topup_reported:'補款待核對',refund_account_due:'待填退款帳戶',refund_due:'退款處理中',settled:'差額已結清',no_difference:'無待收退差額',included_in_order:'已併入訂單付款',superseded:'已由新版取代',cancelled:'已併入取消結算'};
const inputClass='mt-2 min-h-11 w-full rounded border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#1f2937] disabled:opacity-60';
const amount=(value,currency='TWD')=>`${currency==='JPY'?'日幣 JPY ¥':'NT$'} ${Math.abs(Number(value)||0).toLocaleString()}`;

function BalanceRow({row,requestJson,url,onReload,onRefresh}) {
  const [reference,setReference]=useState(''),[bank,setBank]=useState(row.refund_bank||{}),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[uncertain,setUncertain]=useState(false);
  const requestKey=useRef(crypto.randomUUID()),locked=useRef(false);
  const isTopup=row.status==='topup_due',isRefund=['refund_account_due','refund_due'].includes(row.status);
  const settlement=row.settlement, nativeBalance=settlement?.currency==='JPY'?settlement.balance_amount:row.balance_amount;
  const bankKeys=['bank_name','account_number','account_holder'];
  const bankChanged=[...bankKeys,'overseas_details'].some(key=>(bank[key]||'').trim()!==(row.refund_bank?.[key]||'').trim());
  const valid=isTopup?/^[0-9]{5}$/.test(reference):bankKeys.every(key=>bank[key]?.trim())&&(row.status==='refund_account_due'||bankChanged||uncertain);
  const submit=async event=>{
    event.preventDefault();if(locked.current||!valid)return;
    locked.current=true;setBusy(true);setMessage('');
    try {
      const result=await requestJson(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({amendment_id:row.id,expected_updated_at:row.updated_at,request_key:requestKey.current,action:isTopup?'report_topup':'refund_account',...(isTopup?{reference}:{bank}),...(settlement?.currency==='JPY'?{currency:'JPY',expected_amount:Math.abs(nativeBalance)}:{})})});
      if(result.data?.id!==row.id)throw new Error('伺服器沒有回傳可確認的結果，請以相同識別碼重試。');
      setUncertain(false);setMessage(result.message);requestKey.current=crypto.randomUUID();await onReload();
      try{await onRefresh();}catch{setMessage('資料已回報，但訂單畫面尚未更新，請重新載入；不需要重新匯款。');}
    }catch(error){setMessage(error.message);if(error.status&&error.status<500){setUncertain(false);requestKey.current=crypto.randomUUID();await onReload();}else setUncertain(true);}
    finally{locked.current=false;setBusy(false);}
  };
  return <article className="space-y-4 rounded-sm border border-[#dbe3ec] bg-white p-5 text-[#1f2937]">
    <div className="flex flex-wrap justify-between gap-2"><h4 className="font-semibold">第 {row.version} 版修改差額</h4><span className="rounded-full bg-[#eef4fa] px-3 py-1 text-xs font-semibold text-[#2b5f8f]">{labels[row.status]||row.status}</span></div>
    <p className="text-sm">{nativeBalance>0?'補款':nativeBalance<0?'退還差額':'差額'}：<strong>{amount(nativeBalance,settlement?.currency)}</strong></p>
    {settlement?.currency==='JPY'&&<p className="text-sm leading-7 text-[#64748b]">台幣計價差額基準 {amount(row.balance_amount)}；沿用訂單匯率1 TWD＝{settlement.rate} JPY。實際收退為上方日幣金額，台幣基準不是另一筆款項。</p>}
    {row.review_message&&<p role="status" className="rounded bg-amber-50 p-3 text-sm text-amber-900">上次回報未通過：{row.review_message}</p>}
    {isTopup&&<section className="space-y-2 rounded bg-[#f5f8fc] p-4 text-sm"><h5 className="font-semibold">請匯款至此帳戶</h5>{['bank_name','bank_branch','account_number','account_holder'].map((key,index)=><p key={key} className="break-all">{['銀行','分行','帳號','戶名'][index]}：{row.bank_snapshot?.[key]||(key==='bank_branch'?'—':'未設定，請聯絡客服確認')}</p>)}{row.bank_snapshot?.overseas_details&&<p className="whitespace-pre-wrap">{row.bank_snapshot.overseas_details}</p>}<p className="pt-2 text-xs leading-6 text-[#64748b]">這是修改當時的收款帳戶。請確認金額並完成匯款後，再回報帳號末五碼；此頁不會自動扣款。</p></section>}
    {row.status==='topup_reported'&&<p className="text-sm leading-7">已回報末五碼 {row.topup_reference}，等待 SnowLand 查核銀行收款；請勿重複匯款。</p>}
    {(isTopup||isRefund)&&<form onSubmit={submit} className="space-y-4">
      {isRefund&&settlement?.currency==='JPY'&&<p className="text-sm leading-7">請提供可接收日幣的帳戶。若需跨國匯款，可補充分行、SWIFT或中間行等必要資料，行政會核對後處理。</p>}
      <fieldset disabled={busy||uncertain} className="space-y-3">
        {isTopup?<label className="block text-sm font-semibold">匯款帳號末五碼<input className={inputClass} inputMode="numeric" maxLength={5} value={reference} onChange={event=>setReference(event.target.value)} autoComplete="off"/></label>:<><p className="text-sm leading-7">請確認退款銀行、帳號及戶名。此處只提供帳戶資料，不代表款項已退回。</p>{['bank_name','account_number','account_holder'].map((key,index)=><label className="block text-sm font-semibold" key={key}>{['退款銀行','退款帳號','戶名'][index]}<input className={inputClass} maxLength={key==='account_number'?80:100} value={bank[key]||''} onChange={event=>setBank({...bank,[key]:event.target.value})}/></label>)}</>}
        {isRefund&&settlement?.currency==='JPY'&&<label className="block text-sm font-semibold">海外退款資料（選填）<textarea className={`${inputClass} min-h-24`} maxLength={1000} value={bank.overseas_details||''} onChange={event=>setBank({...bank,overseas_details:event.target.value})}/></label>}
      </fieldset>
      <button disabled={busy||!valid} type="submit" className="min-h-11 rounded-full bg-[#2b5f8f] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{busy?'正在回報…':uncertain?'查詢／重試這次回報':isTopup?'我已匯款，送出末五碼':row.status==='refund_due'?'更新退款帳戶':'送出退款帳戶'}</button>
    </form>}
    {row.status==='settled'&&<p className="text-sm text-[#64748b]">SnowLand 已完成差額核對。若仍有問題，請聯絡客服並提供訂單編號。</p>}
    {message&&<p role="status" className="whitespace-pre-wrap rounded bg-[#eef4fa] p-3 text-sm leading-7 text-[#1e4e73]">{message}</p>}
  </article>;
}

export default function OrderAmendmentBalance({orderId,requestJson,onRefresh,cancellationStatus}) {
  const [items,setItems]=useState([]),[error,setError]=useState(''),[loaded,setLoaded]=useState(false);
  const url=`/member-amendments/${orderId}/`;
  const load=useCallback(async()=>{try{const result=await requestJson(url);setItems(result.items||[]);setError('');}catch(error){setError(error.message);}finally{setLoaded(true);}},[requestJson,url]);
  useEffect(()=>{load();},[load]);
  if(loaded&&!error&&!items.length)return null;
  if(['requested','approved','refunded'].includes(cancellationStatus))return <p role="status" className="rounded border border-[#b6d6ec] bg-[#eaf4fb] p-4 text-sm leading-7 text-[#1e4e73]">{cancellationStatus==='refunded'?'原補退差額已併入取消結算，請勿再補款。':'訂單正在取消／退款流程，補退差額暫停處理。請勿再補款，退款以 SnowLand 核對實收款後確認的金額為準。'}</p>;
  if(!loaded)return <p role="status" className="text-sm text-[#64748b]">正在核對訂單修改差額…</p>;
  if(error)return <section role="alert" className="rounded border border-red-200 bg-red-50 p-4 text-sm text-red-800">差額資料未能載入：{error}<button onClick={load} className="ml-2 min-h-11 underline">重新載入</button></section>;
  if(!items.length)return null;
  return <section className="space-y-4"><h3 className="text-xl font-semibold">訂單修改與補退差額</h3><p className="text-sm leading-7 text-[#64748b]">訂單已付款是指原訂單款項。修改後的補款與退款會在這裡分開顯示，不會重複收原訂單金額。</p>{items.filter(row=>row.status!=='superseded').map(row=><BalanceRow key={row.id} row={row} url={url} requestJson={requestJson} onReload={load} onRefresh={onRefresh}/>)}</section>;
}
