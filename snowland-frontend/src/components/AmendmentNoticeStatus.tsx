type Receipt={in_app:string;email:string;local_test:boolean}
export default function AmendmentNoticeStatus({receipt}:{receipt?:Receipt}) {
  if(!receipt)return null
  const email=receipt.email==='sent'
    ?receipt.local_test?'本機郵件測試通過（未對外寄送）':'郵件服務已接受寄送（不代表已讀）'
    :({failed:'Email 發送未確認，請由行政核對發送紀錄，勿重複修改訂單。',queued:'Email 等待發送',sending:'Email 結果待確認，請勿重複寄送。',cancelled:'舊通知已停止寄送，請以最新訂單為準。',not_configured:'會員未設定有效 Email，未寄送郵件。'} as Record<string,string>)[receipt.email]||'Email 狀態待確認'
  return <div className="space-y-1 text-sm leading-6" role="status"><p>{receipt.in_app==='sent'?'會員站內通知已建立。':'會員站內通知尚未建立，請確認訂購帳號。'}</p><p>{email}</p></div>
}
