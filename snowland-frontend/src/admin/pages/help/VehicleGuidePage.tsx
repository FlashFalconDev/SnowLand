import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { vehicleGuidePage } from '../../consoleNavigation'

const chapters = [
  ['overview', '整體流程'],
  ['before', '開始前確認'],
  ['finance', '車輛與費率設定'],
  ['coach', '教練借車申請'],
  ['review', '排車與用車審核'],
  ['records', '出車、還車與支出'],
  ['settlement', '費用核准與薪扣'],
  ['result', '完成結果'],
  ['faq', '常見問題'],
  ['sources', '來源與更新'],
] as const

const sectionClass = 'scroll-mt-24 space-y-4 rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800 sm:p-6'
const headingClass = 'text-xl font-bold'

function Step({ id, title, done, children }: {
  id: string
  title: string
  done: string
  children: ReactNode
}) {
  return (
    <section id={id} tabIndex={-1} className="scroll-mt-24 space-y-3 border-t border-gray-200 pt-5 dark:border-gray-700">
      <h3 className="text-lg font-semibold">{title}</h3>
      {children}
      <p className="rounded-lg bg-violet-50 p-3 text-sm text-violet-900 dark:bg-violet-950/50 dark:text-violet-100">
        <strong>完成判準</strong>　{done}
      </p>
    </section>
  )
}

function GuideFigure({ file, caption, width = 1136, height }: {
  file: string
  caption: string
  width?: number
  height: number
}) {
  const src = `/vehicle-guide/${file}.webp`
  return (
    <figure className="space-y-2">
      <a href={src} target="_blank" rel="noreferrer"
        className="block overflow-hidden rounded-lg border border-gray-200 focus-visible:ring-2 focus-visible:ring-violet-600 dark:border-gray-700">
        <img src={src} alt={`放大檢視（另開分頁）｜${caption}`} width={width} height={height} loading="lazy" decoding="async" className="block h-auto w-full" />
      </a>
      <figcaption className="text-sm text-gray-600 dark:text-gray-300">{caption}。選取圖片可另開分頁放大。</figcaption>
    </figure>
  )
}

export default function VehicleGuidePage() {
  const { hash } = useLocation()

  useEffect(() => {
    if (!hash) return
    const target = document.getElementById(hash.slice(1))
    target?.scrollIntoView()
    target?.focus({ preventScroll: true })
  }, [hash])

  return (
    <article className="mx-auto max-w-5xl space-y-5 break-words text-sm leading-relaxed sm:text-base">
      <header className={sectionClass}>
        <h1 className="text-2xl font-bold sm:text-3xl">{vehicleGuidePage.label}</h1>
        <p>適用於校區主管、行政／總部與教練。從員工借車、排車、出還車，到費用核准與結算。</p>
        <nav aria-label="車輛用車說明章節" className="flex flex-wrap gap-2">
          {chapters.map(([id, label]) => (
            <a key={id} href={`#${id}`} className="inline-flex min-h-11 items-center rounded-lg bg-violet-50 px-3 text-sm font-medium text-violet-800 hover:bg-violet-100 dark:bg-violet-950/50 dark:text-violet-200 dark:hover:bg-violet-900">
              {label}
            </a>
          ))}
        </nav>
      </header>

      <section id="overview" className={sectionClass}>
        <h2 className={headingClass}>整體流程</h2>
        <ol className="list-decimal space-y-2 pl-6">
          <li><strong>行政／總部</strong>先準備車輛與費率，讓主管可安排啟用的車。</li>
          <li><strong>教練</strong>提出借車申請，或由<strong>校區主管</strong>依課程需求建立申請。主管核准並排車後交給駕駛。</li>
          <li><strong>駕駛教練</strong>登記出車與還車，附上里程照片和應附的收據。</li>
          <li><strong>校區主管</strong>審核還車紀錄，<strong>行政／總部</strong>接手核准費用。有私用車資時，再由薪資扣款或人工收款結清。</li>
        </ol>
      </section>

      <section id="before" className={sectionClass}>
        <h2 className={headingClass}>開始前確認</h2>
        <ul className="list-disc space-y-2 pl-6">
          <li>校區主管從「營運總覽 → 車輛排班與用車審核」進入，確認右上「目前範圍」是要處理的校區。</li>
          <li>行政／總部從「營運總覽 → 車輛費率與費用核准」進入。儲存全校費率需要全校區權限，核對薪資另需「薪資單與月結」權限。</li>
          <li>教練從「教學與教練 → 我的用車」進入。啟用的帳號須隸屬申請校區，駕駛與同行教練都需要有效的正時薪規則才能申請。</li>
          <li>申請時段、用車畫面與排車日期都用日本時間。出車前先準備可上傳照片的裝置。</li>
        </ul>
      </section>

      <section id="operations" className={sectionClass}>
        <h2 className={headingClass}>圖文操作</h2>
        <Step id="finance" title="車輛與費率設定" done="重新查閱可看到已儲存的設定，主管排車時可選到適用校區的啟用車輛。">
          <p>行政／總部在「車輛設定」選「新增車輛」或既有車輛。填所屬校區、名稱、車牌，依需要勾選「可共用校區」與「啟用車輛」，再按「儲存車輛」。</p>
          <p>具全校區權限的人員在「費率與給薪日」填「每公里費率（日圓）」、「1 台幣可換日圓」、「次月給薪日」，勾選不需排車的雪場，再按「儲存費率」。</p>
          <GuideFigure file="01-fleet-settings" height={502} caption="圖 1｜車輛設定與費率、匯率、給薪日" />
        </Step>
        <Step id="coach" title="教練借車申請" done="「用車紀錄」出現「待核准」。主管安排後，改為「已排車」並顯示車輛。">
          <p>在「我的用車」選用車校區、用途與起訖時間。選「課程用車」時加選上課雪場，按需要勾選同行教練，填用車說明，再按「送出借車申請」。</p>
          <p>用途也可選「其他公用」、「生活採買（免費）」或「私用」。生活採買每週全校共用一次，至少兩位教練同行。同行教練可在「我的用車」查看自己的行程。</p>
          <GuideFigure file="02-coach-request" height={398} caption="圖 2｜我的用車中的借車申請與日本時間欄位" />
        </Step>
        <Step id="review" title="排車與用車審核" done="申請顯示「已排車」及車輛，或顯示「未核准」及原因。還車紀錄通過後顯示「紀錄已審核」。">
          <ol className="list-decimal space-y-2 pl-6">
            <li>在「課程用車需求」找到日期、校區及雪場，按「帶入排車」。核對預填的日本時間 08:00–18:00，選駕駛教練，再按「建立課程用車」。</li>
            <li>在「用車紀錄」的「待核准」行程選「安排車輛」，按「核准並排車」。如要退回，在待核准或已排車的行程填「未核准原因」，再按「不核准」。</li>
            <li>駕駛送出還車紀錄後，查找「待審核」行程，核對出還車里程、照片、支出和應附收據，再按「通過用車審核」。</li>
          </ol>
          <GuideFigure file="03-demand" width={1440} height={1000} caption="圖 3｜課程用車需求帶入校區、雪場和預設時段" />
          <GuideFigure file="04-approve" height={274} caption="圖 4｜待核准行程的安排車輛與不核准原因" />
        </Step>
        <Step id="records" title="出車、還車與支出" done="登記出車後顯示「用車中」，送出還車後顯示「待審核」，並可查到里程、照片及已登記的支出。">
          <ol className="list-decimal space-y-2 pl-6">
            <li>駕駛在核准時段內，到「我的用車」找到「已排車」行程。填「出發里程（公里）」並上傳照片，按「登記出車」。</li>
            <li>還車後填「歸還里程（公里）」及照片。歸還里程須大於或等於出發里程。</li>
            <li>如有支出，按「新增支出」，選「加油」、「過路費」或「車輛雜支」，填正整數日圓金額，再按「送出還車紀錄」。每趟最多 20 筆。</li>
          </ol>
          <p>公用支出與私用代墊油費可核銷，須附收據照片。私用的其他支出由教練自付。費用核准前，駕駛可按「儲存修正」，已審核的紀錄會回到「待審核」。</p>
          <GuideFigure file="05-depart" height={314} caption="圖 5｜已排車行程的出發里程與照片" />
          <GuideFigure file="06-return" height={584} caption="圖 6｜還車里程、日圓支出及收據上傳" />
        </Step>
        <Step id="settlement" title="費用核准、薪扣與人工收款" done="行程顯示「費用已核准」。私用車資可查每人分攤，扣款或收款後確認未扣餘額減少，歸零即結清。">
          <ol className="list-decimal space-y-2 pl-6">
            <li>行政／總部在「車輛費率與費用核准」找到「紀錄已審核」的行程，核對支出和收據後按「核准用車費用」。</li>
            <li>私用車資以里程差乘日圓費率，再換算台幣，由駕駛與同行教練均分。費率、匯率和給薪日會保存在該行程。</li>
            <li>有薪資權限的人員到「財務 → 薪資單與月結」，按「查看明細」，在「稅金與發放幣別」核對並按「儲存核對結果」。車資通常自還車月扣起，超過該月的次月給薪日才核准時，會順延扣款月。系統依同校區、同教練的行程計算，當期稅後淨額是扣款上限。若車資有變，送出前重新儲存核對結果。教練可在「財務 → 我的薪資」查看已送出的薪資單。</li>
            <li>最晚可扣至還車日所屬期間的 4 月薪資，5–12 月還車計至次年 4 月。該 4 月薪資的次月給薪日過後，若畫面顯示「待人工收款」，實際收款後填「實際收款（台幣）」並按「記錄收款」。</li>
          </ol>
          <GuideFigure file="07-settle" height={238} caption="圖 7｜紀錄已審核後，行政可核准用車費用" />
          <GuideFigure file="08-payroll" width={1094} height={617} caption="圖 8｜薪資明細顯示稅後車資扣款及實領金額" />
          <GuideFigure file="09-collect" height={318} caption="圖 9｜薪扣期間結束後，核對餘額並記錄實際收款" />
        </Step>
      </section>

      <section id="result" className={sectionClass}>
        <h2 className={headingClass}>完成結果</h2>
        <p><strong>校區主管</strong>在「紀錄已審核」完成交接。<strong>行政／總部</strong>在「費用已核准」完成費用核准，私用有餘額時追蹤至結清。<strong>教練</strong>在「我的用車」查看處理進度與自己的分攤。</p>
      </section>

      <section id="faq" className={sectionClass}>
        <h2 className={headingClass}>常見問題</h2>
        <details><summary className="cursor-pointer font-semibold">看不到車輛頁或借車申請？</summary><p className="mt-2">請總部核對員工職務、車輛權限與校區。教練看得到「我的用車」但無法提出申請時，請校區確認有效計薪規則。</p></details>
        <details><summary className="cursor-pointer font-semibold">課程需求為空、沒有可選的車，或核准時撞期？</summary><p className="mt-2">先核對「目前範圍」、查詢起迄日及雪場是否需排車。確認車輛已啟用且可供該校區使用，再查看時段重疊的行程。待排課程用車優先，請先處理課程的車輛需求。</p></details>
        <details><summary className="cursor-pointer font-semibold">已排車卻無法登記出車？</summary><p className="mt-2">確認目前在核准時段內、登入的是這趟駕駛本人，並查前一趟是否已還車。</p></details>
        <details><summary className="cursor-pointer font-semibold">找不到費用核准或收款按鈕？</summary><p className="mt-2">費用核准要等主管完成用車審核。人工收款要等薪扣期限結束且仍有餘額。若系統提示餘額已變更，重新載入再核對當前餘額。</p></details>
      </section>

      <section id="sources" className={sectionClass}>
        <h2 className={headingClass}>來源與更新</h2>
        <p>初版 2026-11-24。操作依 SnowLand Console 的車輛審核、車輛財務、我的用車及薪資功能。畫面以本機測試資料拍攝，車牌、人名、里程與金額均為示範，圖 5、圖 6 為送出前的表單。實際設定及可用操作依各校權限。</p>
      </section>
    </article>
  )
}
