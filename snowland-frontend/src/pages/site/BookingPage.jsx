import React, { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import coaches from '../../data/site/coaches';
import footerPagesContent from '../../data/site/footerPagesContent';

const steps = [
  { id: 1, title: "服務選擇" },
  { id: 2, title: "加購服務" },
  { id: 3, title: "資料確認" },
  { id: 4, title: "報名完成" },
];

function BookingPage() {
  const winterAddOnRef = useRef(null);
  const stepSectionRef = useRef(null);
  const [activeTab, setActiveTab] = useState("login");
  const [showPassword, setShowPassword] = useState(false);
  const [authDone, setAuthDone] = useState(false);
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [registerEmail, setRegisterEmail] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");
  const [authErrors, setAuthErrors] = useState({
    loginEmail: "",
    loginPassword: "",
    registerEmail: "",
    registerPassword: "",
  });
  const [selectedDesign, setSelectedDesign] = useState("design1");
  const [currentStep, setCurrentStep] = useState(1);
  const [step2Index, setStep2Index] = useState(0);
  const [hasUnderSix, setHasUnderSix] = useState("");
  const [underSixCanRide, setUnderSixCanRide] = useState("");
  const [underSixOneOnOneConfirmed, setUnderSixOneOnOneConfirmed] = useState(false);
  const [skiAddCourseMode, setSkiAddCourseMode] = useState(false);
  const [skiCartItems, setSkiCartItems] = useState([]);
  const [skiAddDateSourceItemId, setSkiAddDateSourceItemId] = useState("");
  const [errors, setErrors] = useState({});
  const [calendarMonth, setCalendarMonth] = useState(() => {
    const today = new Date();
    return new Date(today.getFullYear(), today.getMonth(), 1);
  });
  const [skiDateSlots, setSkiDateSlots] = useState({});
  const [activeSkiDateKey, setActiveSkiDateKey] = useState("");
  const [dateSlotError, setDateSlotError] = useState("");
  const [photoPlanExpanded, setPhotoPlanExpanded] = useState("");
  const [formState, setFormState] = useState({
    serviceType: "",
    skiType: "",
    skiResort: "",
    skiPeople: "",
    skiLevel: "",
    skiCoach: "",
    skiLanguage: "",
    skiDuration: "",
    skiDates: [],
    skiSessionDurations: {},
    skiDateProfiles: {},
    skiAddCourseChoice: "",
    skiEquipment: "",
    skiEquipmentAssistGroupCount: "",
    skiEquipmentAssistBookingIds: [],
    skiEquipmentAssistPeopleCounts: {},
    addPhotoChoice: "",
    addPhotoQuantities: {
      "photo-1h": 0,
      "photo-2h": 0,
      "photo-3h": 0,
    },
    discountCode: "",
    referrerName: "",
    photoSeason: "",
    photoLocation: "",
    photoPlanCategory: "",
    photoPlanSelections: {},
    photoAddOnSelections: {},
    photoTimeNote: "",
    photoSkiBundleChoice: "",
    photoSkiOrderId: "",
    paymentMethod: "",
    cancellationPolicyAccepted: false,
    photoPeople: "",
    contactName: "",
    contactPhone: "",
    contactEmail: "",
  });

  const setField = (key, value) => {
    setFormState((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => ({ ...prev, [key]: "" }));
  };
  const setPhotoPlanSelection = (optionId, nextCount) => {
    setFormState((prev) => {
      const nextSelections = { ...prev.photoPlanSelections };
      const safeCount = Math.max(0, nextCount);
      if (safeCount === 0) {
        delete nextSelections[optionId];
      } else {
        nextSelections[optionId] = safeCount;
      }
      return { ...prev, photoPlanSelections: nextSelections };
    });
    setErrors((prev) => ({ ...prev, photoPlanOption: "" }));
  };
  const setPhotoAddOnSelection = (planId, addOnIndex, nextCount) => {
    setFormState((prev) => {
      const key = `${planId}:${addOnIndex}`;
      const nextSelections = { ...prev.photoAddOnSelections };
      const safeCount = Math.max(0, nextCount);
      if (safeCount === 0) {
        delete nextSelections[key];
      } else {
        nextSelections[key] = safeCount;
      }
      return { ...prev, photoAddOnSelections: nextSelections };
    });
  };
  const clearSkiEquipmentAssistErrors = (prevErrors) => {
    const nextErrors = { ...prevErrors };
    delete nextErrors.skiEquipmentAssistGroupCount;
    delete nextErrors.skiEquipmentAssistSelection;
    Object.keys(nextErrors).forEach((key) => {
      if (key.startsWith("skiEquipmentAssistPeopleCounts:")) {
        delete nextErrors[key];
      }
    });
    return nextErrors;
  };
  const clearSkiEquipmentAssistState = () => {
    setFormState((prev) => ({
      ...prev,
      skiEquipmentAssistGroupCount: "",
      skiEquipmentAssistBookingIds: [],
      skiEquipmentAssistPeopleCounts: {},
    }));
    setErrors((prev) => clearSkiEquipmentAssistErrors(prev));
  };
  const updateSkiEquipmentAssistGroupCount = (nextCount) => {
    const safeCount = Math.max(0, Number.parseInt(nextCount, 10) || 0);
    setFormState((prev) => {
      const nextSelectedIds = prev.skiEquipmentAssistBookingIds.slice(0, safeCount);
      const nextPeopleCounts = Object.fromEntries(
        Object.entries(prev.skiEquipmentAssistPeopleCounts).filter(([id]) =>
          nextSelectedIds.includes(id)
        )
      );
      return {
        ...prev,
        skiEquipmentAssistGroupCount: safeCount ? String(safeCount) : "",
        skiEquipmentAssistBookingIds: nextSelectedIds,
        skiEquipmentAssistPeopleCounts: nextPeopleCounts,
      };
    });
    setErrors((prev) => clearSkiEquipmentAssistErrors(prev));
  };
  const toggleSkiEquipmentAssistBooking = (bookingId) => {
    setFormState((prev) => {
      const alreadySelected = prev.skiEquipmentAssistBookingIds.includes(bookingId);
      if (alreadySelected) {
        const nextSelectedIds = prev.skiEquipmentAssistBookingIds.filter(
          (id) => id !== bookingId
        );
        const nextPeopleCounts = { ...prev.skiEquipmentAssistPeopleCounts };
        delete nextPeopleCounts[bookingId];
        return {
          ...prev,
          skiEquipmentAssistBookingIds: nextSelectedIds,
          skiEquipmentAssistPeopleCounts: nextPeopleCounts,
        };
      }

      const maxCount = Number.parseInt(prev.skiEquipmentAssistGroupCount, 10) || 0;
      if (maxCount > 0 && prev.skiEquipmentAssistBookingIds.length >= maxCount) {
        return prev;
      }

      return {
        ...prev,
        skiEquipmentAssistBookingIds: [...prev.skiEquipmentAssistBookingIds, bookingId],
      };
    });
    setErrors((prev) => {
      const nextErrors = clearSkiEquipmentAssistErrors(prev);
      delete nextErrors[`skiEquipmentAssistPeopleCounts:${bookingId}`];
      return nextErrors;
    });
  };
  const updateSkiEquipmentAssistPeopleCount = (bookingId, nextValue) => {
    const safeValue = nextValue.replace(/[^\d]/g, "");
    setFormState((prev) => ({
      ...prev,
      skiEquipmentAssistPeopleCounts: {
        ...prev.skiEquipmentAssistPeopleCounts,
        [bookingId]: safeValue,
      },
    }));
    setErrors((prev) => {
      const nextErrors = clearSkiEquipmentAssistErrors(prev);
      delete nextErrors[`skiEquipmentAssistPeopleCounts:${bookingId}`];
      return nextErrors;
    });
  };
  useEffect(() => {
    if (!authDone) return;
    const autoEmail = loginEmail.trim() || registerEmail.trim();
    if (!autoEmail || formState.contactEmail) return;
    setField("contactEmail", autoEmail);
  }, [authDone, loginEmail, registerEmail]);
  function buildSkiCartItem() {
    const totalAmount = Math.max(
      0,
      skiCourseFee +
        coachFeeTotal +
        addEquipmentFee +
        addPhotoTotal -
        addPhotoDiscount -
        earlyBirdDiscountTotal
    );

    return {
      skiType: formState.skiType,
      skiResort: formState.skiResort,
      skiPeople: formState.skiPeople,
      skiLevel: formState.skiLevel,
      skiCoach: formState.skiCoach,
      skiLanguage: formState.skiLanguage,
      skiDuration: formState.skiDuration,
      skiDates: [...formState.skiDates],
      skiSessionDurations: { ...(formState.skiSessionDurations || {}) },
      skiDateProfiles: { ...(formState.skiDateProfiles || {}) },
      skiDateSlots: { ...skiDateSlots },
      skiEquipment: formState.skiEquipment,
      addPhotoChoice: formState.addPhotoChoice,
      skiEquipmentAssistGroupCount: formState.skiEquipmentAssistGroupCount,
      skiEquipmentAssistBookingIds: [...formState.skiEquipmentAssistBookingIds],
      skiEquipmentAssistPeopleCounts: { ...formState.skiEquipmentAssistPeopleCounts },
      skiTypeLabel: skiTypeSummaryLabel,
      skiResortLabel: skiResortLabels[formState.skiResort] || "—",
      skiLanguageLabel: skiLanguageLabels[formState.skiLanguage] || "ALL",
      skiPeopleLabel: skiPeopleSummaryLabel,
      skiPeopleCount,
      skiLevelLabel: skiLevelLabels[formState.skiLevel] || "—",
      skiDurationLabel: skiDurationSummaryLabel,
      skiSessions: skiSessions.map((session) => ({
        dateKey: session.dateKey,
        skiType: session.skiType,
        skiTypeLabel: session.skiTypeLabel,
        skiPeople: session.skiPeople,
        skiPeopleCount: session.skiPeopleCount,
        skiPeopleLabel: session.skiPeopleLabel,
        durationLabel: session.durationLabel,
        slotLabel: session.slotLabel || "未選擇時段",
      })),
      dateLabel: selectedDatesLabel,
      timeLabel: selectedDateSlotsLabel,
      totalAmount,
    };
  }
  const commitCurrentSkiCartItem = () => {
    const createSkiCartItemId =
      globalThis.crypto?.randomUUID?.() ??
      `ski-cart-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setSkiCartItems((prev) => [...prev, { ...buildSkiCartItem(), id: createSkiCartItemId }]);
  };
  const resetCurrentSkiDraft = () => {
    setFormState((prev) => ({
      ...prev,
      serviceType: "",
      skiType: "",
      skiResort: "",
      skiPeople: "",
      skiLevel: "",
      skiCoach: "",
      skiLanguage: "",
      skiDuration: "",
      skiDates: [],
      skiSessionDurations: {},
      skiDateProfiles: {},
      skiAddCourseChoice: "",
      skiEquipment: "",
      skiEquipmentAssistGroupCount: "",
      skiEquipmentAssistBookingIds: [],
      skiEquipmentAssistPeopleCounts: {},
      addPhotoChoice: "",
      addPhotoQuantities: {
        "photo-1h": 0,
        "photo-2h": 0,
        "photo-3h": 0,
      },
      photoSeason: "",
      photoLocation: "",
      photoPlanCategory: "",
      photoPlanSelections: {},
      photoAddOnSelections: {},
      photoTimeNote: "",
      photoSkiBundleChoice: "",
      photoSkiOrderId: "",
      photoPeople: "",
    }));
    setCoachSelectionMode("any");
    setCoachQuery("");
    setHasUnderSix("");
    setUnderSixCanRide("");
    setUnderSixOneOnOneConfirmed(false);
    setSkiDateSlots({});
    setActiveSkiDateKey("");
    setSkiAddDateSourceItemId("");
    setDateSlotError("");
    setPhotoPlanExpanded("");
    setErrors((prev) => ({
      ...clearSkiEquipmentAssistErrors(prev),
      serviceType: "",
      skiType: "",
      skiResort: "",
      skiPeople: "",
      skiLevel: "",
      skiCoach: "",
      skiLanguage: "",
      skiDuration: "",
      skiDates: "",
      skiTimeSlot: "",
      skiAddCourseChoice: "",
      skiEquipment: "",
      skiEquipmentAssistGroupCount: "",
      skiEquipmentAssistSelection: "",
      addPhotoChoice: "",
      addPhotoQuantities: "",
      photoSeason: "",
      photoLocation: "",
      photoPlan: "",
      photoPlanOption: "",
      photoSkiBundleChoice: "",
      photoSkiOrderId: "",
      photoPeople: "",
      paymentMethod: "",
      cancellationPolicyAccepted: "",
      contactName: "",
      contactPhone: "",
      contactEmail: "",
    }));
    setSkiAddCourseMode(false);
    setStep2Index(0);
  };
  const removeSkiCartItem = (removeIndex) => {
    if (skiCartItems.length === 1) {
      resetCurrentSkiDraft();
      setSkiCartItems([]);
      return;
    }

    if (removeIndex < 0 || removeIndex >= skiCartItems.length) {
      return;
    }

    const nextItems = skiCartItems.filter((_, index) => index !== removeIndex);
    const nextAssistBookingIds = formState.skiEquipmentAssistBookingIds.filter((id) =>
      nextItems.some((item) => item.id === id)
    );
    const nextAssistPeopleCounts = Object.fromEntries(
      Object.entries(formState.skiEquipmentAssistPeopleCounts).filter(([id]) =>
        nextItems.some((item) => item.id === id)
      )
    );

    setSkiCartItems(nextItems);
    setFormState((prev) => ({
      ...prev,
      skiEquipmentAssistBookingIds: nextAssistBookingIds,
      skiEquipmentAssistPeopleCounts: nextAssistPeopleCounts,
    }));
    setErrors((prev) => clearSkiEquipmentAssistErrors(prev));
  };
  const updateActiveSkiDate = (
    nextDates,
    removedDateKey = null,
    preferredDateKey = null
  ) => {
    if (!nextDates.length) {
      setActiveSkiDateKey("");
      return;
    }
    if (preferredDateKey && nextDates.includes(preferredDateKey)) {
      setActiveSkiDateKey(preferredDateKey);
      return;
    }
    if (removedDateKey && activeSkiDateKey === removedDateKey) {
      setActiveSkiDateKey(nextDates[nextDates.length - 1]);
      return;
    }
    if (!activeSkiDateKey || !nextDates.includes(activeSkiDateKey)) {
      setActiveSkiDateKey(nextDates[nextDates.length - 1]);
    }
  };
  const getSkiSessionDuration = (dateKey) =>
    formState.skiSessionDurations?.[dateKey] || formState.skiDuration || "";
  const getSkiDateProfile = (dateKey) =>
    formState.skiDateProfiles?.[dateKey] || {
      skiType: formState.skiType,
      skiPeople: formState.skiPeople,
      skiDuration: getSkiSessionDuration(dateKey),
    };
  const getActiveSkiDraftProfile = () => {
    const activeProfile =
      activeSkiDateKey && formState.skiDates.includes(activeSkiDateKey)
        ? getSkiDateProfile(activeSkiDateKey)
        : null;
    return {
      skiType: activeProfile?.skiType || formState.skiType,
      skiPeople: activeProfile?.skiPeople || formState.skiPeople,
      skiDuration: activeProfile?.skiDuration || formState.skiDuration,
    };
  };
  const restoreSkiDraftForAddDate = (source, sourceId = source?.id || "") => {
    if (!source) return;

    setFormState((prev) => ({
      ...prev,
      serviceType: "ski",
      skiType: source.skiType || "",
      skiResort: source.skiResort || "",
      skiPeople: source.skiPeople || "",
      skiLevel: source.skiLevel || "",
      skiCoach: source.skiCoach || "",
      skiLanguage: source.skiLanguage || "",
      skiDuration: source.skiDuration || "",
      skiDates: source.skiDates?.length ? [...source.skiDates] : [],
      skiSessionDurations:
        source.skiSessionDurations && Object.keys(source.skiSessionDurations).length
          ? { ...source.skiSessionDurations }
          : {},
      skiDateProfiles:
        source.skiDateProfiles && Object.keys(source.skiDateProfiles).length
          ? { ...source.skiDateProfiles }
          : {},
      skiAddCourseChoice: "add-date",
      skiEquipment: source.skiEquipment || "",
      skiEquipmentAssistGroupCount: source.skiEquipmentAssistGroupCount || "",
      skiEquipmentAssistBookingIds: source.skiEquipmentAssistBookingIds?.length
        ? [...source.skiEquipmentAssistBookingIds]
        : [],
      skiEquipmentAssistPeopleCounts: source.skiEquipmentAssistPeopleCounts
        ? { ...source.skiEquipmentAssistPeopleCounts }
        : {},
      addPhotoChoice: source.addPhotoChoice || "",
    }));

    setSkiDateSlots(source.skiDateSlots ? { ...source.skiDateSlots } : {});
    setActiveSkiDateKey(
      Array.isArray(source.skiDates) && source.skiDates.length > 0
        ? source.skiDates[source.skiDates.length - 1]
        : ""
    );

    setSkiAddDateSourceItemId(sourceId);
    setDateSlotError("");
    setErrors((prev) => ({ ...prev, skiDates: "", skiTimeSlot: "" }));
  };
  const renderSkiCartItemCard = (
    item,
    index,
    { showTotal = false, onRemove, onSelect, titleLabel } = {}
  ) => {
    const sessions =
      Array.isArray(item.skiSessions) && item.skiSessions.length > 0
        ? item.skiSessions
        : [
            {
              dateKey: item.dateLabel || "—",
              durationLabel: item.skiDurationLabel || "—",
              skiPeopleLabel: item.skiPeopleLabel || "—",
              skiType: item.skiType,
              skiTypeLabel: item.skiTypeLabel,
            },
          ];

    return (
      <motion.div
        layout
        key={item.id || `${item.dateLabel}-${item.timeLabel}-${index}`}
        role={onSelect ? "button" : undefined}
        tabIndex={onSelect ? 0 : undefined}
        onClick={onSelect}
        onKeyDown={
          onSelect
            ? (event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect();
                }
              }
            : undefined
        }
        className={`relative rounded-sm border bg-[#f8fafc] px-4 py-4 pr-12 transition-all ${
          onSelect
            ? "cursor-pointer border-[#cbd5e1] hover:border-[#2b5f8f] hover:bg-[#f1f5f9] focus:outline-none focus-visible:border-[#2b5f8f]"
            : "border-[#e2e8f0]"
        }`}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        transition={{ duration: 0.22, ease: "easeOut" }}
      >
        {onRemove && (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onRemove();
            }}
            className="absolute right-3 top-2 text-3xl leading-none text-[#94a3b8] transition-colors hover:text-[#2b5f8f]"
            aria-label={`刪除預約${index + 1}`}
          >
            ×
          </button>
        )}
        <p className="text-xs font-semibold text-[#94a3b8] font-display">
          {titleLabel || `預約${index + 1}`}
        </p>
        <div className="mt-3 space-y-2 text-sm text-[#475569]">
          {sessions.map((session, sessionIndex) => (
            <p
              key={`${item.id || index}-session-${session.dateKey}-${sessionIndex}`}
              className={sessionIndex > 0 ? "border-t border-[#eef2f7] pt-2" : ""}
            >
              日期： {session.dateKey} 時長：{session.durationLabel || "—"} 人數：{session.skiPeopleLabel || "—"} 課程：{session.skiType === "board" ? "單板 Snowboarding" : session.skiType === "ski" ? "雙板 Ski" : session.skiTypeLabel || "—"}
            </p>
          ))}
        </div>
        {showTotal && (
          <p className="mt-4 text-sm font-semibold text-[#1f2937]">
            小計：{formatMoney(item.totalAmount || 0)}
          </p>
        )}
      </motion.div>
    );
  };

  const renderError = (key) =>
    errors[key] ? (
      <p className="mt-2 text-xs text-[#ef4444]">{errors[key]}</p>
    ) : null;
  const goToStep = (stepId) => {
    if (stepId === 1) {
      setCurrentStep(1);
      return;
    }
    if (stepId === 2) {
      if (!formState.serviceType) {
        setCurrentStep(1);
        return;
      }
      setStep2Index(0);
      setCurrentStep(2);
      return;
    }
    if (stepId === 3) {
      setCurrentStep(3);
      return;
    }
    if (stepId === 4) {
      setCurrentStep(4);
    }
  };

  const skiStep2Fields = [
    "skiType",
    "skiResort",
    "skiPeople",
    "skiLevel",
    "skiCoach",
    "skiDuration",
    "skiDate",
    "skiTimeSlot",
    "skiAddCourse",
    "skiEquipment",
    "addPhoto",
  ];
  const photoStep2Fields = [
    "photoSeason",
    "photoLocation",
    "photoPlan",
    "skiDate",
    "photoPeople",
  ];
  const step2Fields =
    formState.serviceType === "photo" ? photoStep2Fields : skiStep2Fields;
  const isSkiAddOnStep =
    formState.serviceType === "ski" &&
    ["skiEquipment", "addPhoto"].includes(step2Fields[step2Index]);
  const serviceTitle =
    formState.serviceType === "ski"
      ? isSkiAddOnStep
        ? "加購服務"
        : "滑雪課程"
      : formState.serviceType === "photo"
        ? "攝影服務"
        : "服務選擇";
  const step2Title =
    formState.serviceType === "ski" && step2Fields[step2Index] === "skiTimeSlot"
        ? "選擇上課時段"
        : serviceTitle;
  const progressStep =
    currentStep === 2 && formState.serviceType === "ski"
      ? isSkiAddOnStep
        ? 2
        : 1
      : currentStep;
  const stepSectionLabel =
    currentStep === 2 && formState.serviceType === "ski"
      ? isSkiAddOnStep
        ? "Step 2"
        : "Step 1"
      : `Step ${currentStep}`;
  const coachLanguageOptions = [
    { id: "", label: "ALL" },
    { id: "中文", label: "中文" },
    { id: "英文", label: "English" },
    { id: "日文", label: "日本語" },
    { id: "粵語", label: "粵語" },
  ];
  const canAdvanceFromPeople =
    !!formState.skiPeople &&
    hasUnderSix &&
    (hasUnderSix === "no" ||
      (underSixCanRide &&
        (underSixCanRide === "yes" || underSixOneOnOneConfirmed)));
  const weekdays = ["M", "T", "W", "T", "F", "S", "S"];
  const [coachQuery, setCoachQuery] = useState("");
  const [coachSelectionMode, setCoachSelectionMode] = useState("any");

  const normalizedCoachQuery = coachQuery.trim().toLowerCase();
  const filteredCoaches = coaches.filter((coach) => {
    const typeMatch = formState.skiType
      ? formState.skiType === "board"
        ? coach.coachType?.includes("單板")
        : coach.coachType?.includes("雙板")
      : true;
    const languageMatch =
      formState.skiLanguage === ""
        ? true
        : formState.skiLanguage === "英文"
          ? coach.languages?.includes("英語") || coach.languages?.includes("英文")
          : coach.languages?.includes(formState.skiLanguage);
    const nameMatch = normalizedCoachQuery
      ? coach.name.toLowerCase().includes(normalizedCoachQuery)
      : true;
    return typeMatch && languageMatch && nameMatch;
  });

  const setSingleSkiDate = (dateKey) => {
    setFormState((prev) => ({
      ...prev,
      skiDates: [dateKey],
      skiSessionDurations: {
        [dateKey]: prev.skiDuration,
      },
      skiDateProfiles: {
        [dateKey]: {
          skiType: prev.skiType,
          skiPeople: prev.skiPeople,
          skiDuration: prev.skiDuration,
        },
      },
    }));
    setSkiDateSlots({});
    setActiveSkiDateKey(dateKey);
    setDateSlotError("");
    setErrors((prev) => ({ ...prev, skiDates: "", skiTimeSlot: "" }));
  };

  const toDateKey = (date) => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  };

  const monthLabel = (date) =>
    date.toLocaleDateString("en-US", { month: "long", year: "numeric" });
  const promoStartDate = new Date(2026, 2, 4);
  const promoEndDate = new Date(2026, 4, 30);
  const isPromoDate = (date) => date >= promoStartDate && date <= promoEndDate;
  const parseDateKey = (dateKey) => {
    const [year, month, day] = dateKey.split("-").map((part) => Number(part));
    if (!year || !month || !day) return null;
    return new Date(year, month - 1, day);
  };
  const skiTypeLabels = { board: "單板 Snowboarding", ski: "雙板 Ski" };
  const skiResortLabels = {
    "off-piste": "野雪嚮導 Off-piste",
    tomamu: "星野 Tomamu",
    furano: "富良野 Furano",
    "minami-furano": "南富良野",
    kamui: "神居 Kamui",
    racey: "夕張 Racey",
    sahoro: "佐幌 Sahoro",
    teine: "手稲 Teine",
    kokusai: "札幌國際 Kokusai",
    kiroro: "喜樂樂 Kiroro",
    rusutsu: "留壽都 Rusutsu",
    niseko: "新雪谷 Niseko",
    "santa-present-park": "聖誕禮物公園 Santa Present Park",
  };
  const skiLevelLabels = {
    none: "無經驗",
    entry: "入門",
    basic: "初階",
    mid: "中階",
    high: "高階",
    pro: "專家",
  };
  const skiDurationLabels = {
    full: "全天",
    half: "半天",
  };
  const skiEquipmentLabels = {
    "rent-self": "自行租借不須協助",
    "own-gear": "自備裝備不須協助",
    "in-class-help": "課程時間內協助",
    "extra-help": "加購協助時間",
  };
  const addPhotoLabels = {
    yes: "是",
    no: "否",
  };
  const addPhotoPlanLabels = {
    "photo-1h": "1 小時快閃旅行",
    "photo-2h": "2 小時經典旅行",
    "photo-3h": "3 小時半日樂活",
  };
  const addPhotoSelectionLabel = Object.entries(formState.addPhotoQuantities)
    .filter(([, count]) => count > 0)
    .map(([id, count]) => `${addPhotoPlanLabels[id] || id} x${count}`)
    .join("、") || "—";
  const photoPlanPricing = {
    "photo-1h": { price: 15000, hours: 1 },
    "photo-2h": { price: 24000, hours: 2 },
    "photo-3h": { price: 32000, hours: 3 },
  };
  const photoServicePlans = {
    winter: [
      {
        id: "winter-basic",
        title: "冬季雪地攝影",
        subtitle: "客製化",
        options: [
          {
            id: "winter-1h",
            label: "1 小時快閃旅行",
            price: 15000,
            details: ["毛片全給", "保證至少 30 張照片", "適合單一地點拍攝"],
            image: "/photography-gallery/gallery-049.jpg",
          },
          {
            id: "winter-2h",
            label: "2 小時經典旅行",
            price: 24000,
            details: ["毛片全給", "保證至少 60 張", "適合家庭、情侶或多場景拍攝"],
            image: "/photography-gallery/gallery-030.jpg",
          },
          {
            id: "winter-3h",
            label: "3 小時半日樂活",
            price: 32000,
            details: ["毛片全給", "保證至少 90 張", "適合滑雪側拍 + 外景寫真"],
            image: "/photography-gallery/gallery-073.jpg",
          },
        ],
        includes: [],
        addOns: ["精修照片 1,000 元/張"],
      },
    ],
    summer: [
      {
        id: "summer-travel",
        title: "旅拍專案",
        subtitle: "客製化",
        image: "/legacy/photography-summer/image-02.jpg",
        options: [
          {
            id: "summer-travel-1h",
            label: "1 小時快閃回憶",
            price: 23800,
            details: ["可選擇 1 個景點", "保障 20 張以上照片"],
          },
          {
            id: "summer-travel-2h",
            label: "2 小時經典旅行",
            price: 32800,
            details: ["可選擇 1～2 個景點", "保障 40 張以上照片"],
          },
          {
            id: "summer-travel-4h",
            label: "4 小時半日樂活",
            price: 42800,
            details: ["可選擇 2～3 個景點", "保障 70 張以上照片"],
          },
        ],
        includes: ["照片全給", "不限人數"],
        addOns: ["精修照片 1,500 元/張", "女生妝髮 5,500 元/位", "男生妝髮 3,500 元/位"],
      },
      {
        id: "summer-light-wedding",
        title: "旅拍輕婚紗專案",
        subtitle: "客製化",
        image: "/legacy/photography-summer/2021-12-15-The Stage 花蓮婚紗-Ron&Susie-130.jpg",
        options: [
          {
            id: "summer-light-wedding-6h",
            label: "2 套 6 小時",
            price: 58900,
            details: [
              "可選擇 2 個景點",
              "保障 30 張以上照片",
              "新娘一組妝髮",
              "新郎一組妝髮",
              "自備 2 套服裝",
              "精修 10 張",
            ],
          },
        ],
        includes: ["調光調色後原檔 JPG 全給", "環保雲端交件"],
        addOns: ["精修 1,500 元/張", "精緻皮革相簿 5,500 元/本"],
      },
      {
        id: "summer-wedding",
        title: "旅拍婚紗專案",
        subtitle: "客製化",
        image: "/legacy/photography-summer/2023-05-28-TheStage Abbie&Gael婚紗拍樣 (230 - 531).jpg",
        options: [
          {
            id: "summer-wedding-4h",
            label: "1 套 4 小時",
            price: 84800,
            details: [
              "可選擇 1 個景點",
              "保障 30 張以上照片",
              "一套禮服（一白）",
              "新娘一組妝髮",
              "新郎一組妝髮",
              "精修 10 張",
            ],
          },
          {
            id: "summer-wedding-6h",
            label: "2 套 6 小時",
            price: 98800,
            details: [
              "可選擇 2 個景點",
              "保障 50 張以上照片",
              "二套禮服（一白一晚）",
              "新娘兩組妝髮",
              "新郎一組妝髮",
              "精修 15 張",
            ],
          },
          {
            id: "summer-wedding-8h",
            label: "3 套 8 小時",
            price: 112800,
            details: [
              "可選擇 2～3 個景點",
              "保障 1000 張以上照片",
              "三套禮服（一白一晚一和）",
              "新娘三組妝髮",
              "新郎一組妝髮",
              "精修 25 張",
            ],
          },
        ],
        includes: ["調光調色後原檔 JPG 全給", "環保雲端交件", "精緻皮革相簿"],
        addOns: ["精修 1,500 元/張"],
      },
    ],
  };
  const photoPlanCategories = photoServicePlans[formState.photoSeason] || [];
  const winterPhotoPlan = photoServicePlans.winter?.[0] || null;
  const allPhotoPlanCategories = Object.values(photoServicePlans).flat();
  const photoPlanOptionMap = allPhotoPlanCategories.reduce((acc, plan) => {
    plan.options.forEach((option) => {
      acc[option.id] = {
        ...option,
        planId: plan.id,
        planTitle: plan.title,
      };
    });
    return acc;
  }, {});
  const selectedPhotoPlanItems = Object.entries(formState.photoPlanSelections)
    .filter(([, count]) => count > 0)
    .map(([id, count]) => ({
      ...photoPlanOptionMap[id],
      count,
    }))
    .filter((item) => item.id);
  const selectedPhotoPlanIds = new Set(
    selectedPhotoPlanItems.map((item) => item.planId)
  );
  const photoPlanSelectionCount = selectedPhotoPlanItems.reduce(
    (sum, item) => sum + item.count,
    0
  );
  const selectedSkiDateKey =
    (activeSkiDateKey && formState.skiDates.includes(activeSkiDateKey)
      ? activeSkiDateKey
      : formState.skiDates[formState.skiDates.length - 1]) || "";
  const selectedSkiDateDuration = selectedSkiDateKey
    ? getSkiSessionDuration(selectedSkiDateKey)
    : "";
  const setSkiDurationForSelectedDate = (nextDuration) => {
    if (selectedSkiDateKey && formState.skiDates.includes(selectedSkiDateKey)) {
      setFormState((prev) => {
        const nextDurations = {
          ...(prev.skiSessionDurations || {}),
          [selectedSkiDateKey]: nextDuration,
        };
        const nextProfiles = { ...(prev.skiDateProfiles || {}) };
        const prevProfile = nextProfiles[selectedSkiDateKey] || {};
        nextProfiles[selectedSkiDateKey] = {
          skiType: prevProfile.skiType || prev.skiType,
          skiPeople: prevProfile.skiPeople || prev.skiPeople,
          skiDuration: nextDuration,
        };
        return {
          ...prev,
          skiDuration: nextDuration,
          skiSessionDurations: nextDurations,
          skiDateProfiles: nextProfiles,
        };
      });
      setSkiDateSlots((prev) => {
        if (!prev[selectedSkiDateKey]) return prev;
        const next = { ...prev };
        delete next[selectedSkiDateKey];
        return next;
      });
    } else {
      setField("skiDuration", nextDuration);
    }
    setDateSlotError("");
    setErrors((prev) => ({ ...prev, skiTimeSlot: "" }));
  };
  const needsSkiTimeSlot = formState.serviceType === "ski" && !!selectedSkiDateDuration;
  const needsPhotoDateSlot = formState.serviceType === "photo";
  const requiresDateSlot = needsSkiTimeSlot || needsPhotoDateSlot;
  const skiSlotLabelById = (slotId) =>
    slotId === "full"
      ? "09:00-15:00"
      : slotId === "am"
        ? "09:00-12:00"
        : slotId === "pm"
          ? "12:30-15:30"
          : "";
  const photoSlotLabelById = (slotId) =>
    slotId === "am"
      ? "上午"
      : slotId === "pm"
        ? "下午"
        : slotId === "flex"
          ? "可彈性安排"
          : "";
  const skiTimeSlotOptions =
    selectedSkiDateDuration === "full"
      ? [{ id: "full", label: "09:00-15:00" }]
      : selectedSkiDateDuration === "half"
        ? [
            { id: "am", label: "09:00-12:00" },
            { id: "pm", label: "12:30-15:30" },
          ]
        : [];
  const skiDateStepSlotLabel = (slotValue) => {
    if (Array.isArray(slotValue)) {
      const slotOrder = { am: 0, pm: 1, flex: 2 };
      const labels = slotValue
        .slice()
        .sort((a, b) => (slotOrder[a] ?? 99) - (slotOrder[b] ?? 99))
        .map((slotId) => photoSlotLabelById(slotId))
        .filter(Boolean);
      return labels.length ? labels.join("、") : "未選擇時段";
    }
    return photoSlotLabelById(slotValue) || "未選擇時段";
  };
  const dateSlotLabel = (slotValue) => {
    if (formState.serviceType === "ski") {
      if (Array.isArray(slotValue)) {
        const slotOrder = { full: 0, am: 1, pm: 2 };
        const labels = slotValue
          .slice()
          .sort((a, b) => (slotOrder[a] ?? 99) - (slotOrder[b] ?? 99))
          .map((slotId) => skiSlotLabelById(slotId))
          .filter(Boolean);
        return labels.length ? labels.join("、") : "未選擇時段";
      }
      return skiSlotLabelById(slotValue) || "未選擇時段";
    }
    return skiDateStepSlotLabel(slotValue) || "未選擇時段";
  };
  const formatSkiSessionSlotLabel = (session) => {
    if (!session) return "未選擇時段";
    return session.slotLabel || "未選擇時段";
  };
  const getDateSlotCount = (slotValue) =>
    Array.isArray(slotValue) ? slotValue.length : slotValue ? 1 : 0;
  const selectedDateSlotCount = formState.skiDates.reduce(
    (sum, dateKey) => sum + getDateSlotCount(skiDateSlots[dateKey]),
    0
  );
  const getTotalSlotCount = (slotsByDate) =>
    formState.skiDates.reduce(
      (sum, dateKey) => sum + getDateSlotCount(slotsByDate[dateKey]),
      0
    );
  const hasAllDateSlots = formState.skiDates.every(
    (dateKey) => getDateSlotCount(skiDateSlots[dateKey]) > 0
  );
  const canAdvanceFromDates =
    formState.serviceType === "photo"
      ? photoPlanSelectionCount > 0 &&
        selectedDateSlotCount === photoPlanSelectionCount
      : formState.skiDates.length > 0;
  const photoPeopleRestrictedToTwo =
    selectedPhotoPlanIds.has("summer-light-wedding") ||
    selectedPhotoPlanIds.has("summer-wedding");
  const photoServiceFee =
    formState.serviceType === "photo"
      ? selectedPhotoPlanItems.reduce(
          (sum, item) => sum + item.price * item.count,
          0
        )
      : 0;
  const selectedPhotoPlanLabel = selectedPhotoPlanItems.length
    ? selectedPhotoPlanItems
        .map((item) => `${item.planTitle} ${item.label} x${item.count}`)
        .join("、")
    : "—";
  const selectedPhotoAddOns = Object.entries(formState.photoAddOnSelections)
    .map(([key, count]) => {
      const [planId, addOnIndex] = key.split(":");
      const plan = allPhotoPlanCategories.find((item) => item.id === planId);
      const addOnText = plan?.addOns?.[Number(addOnIndex)];
      if (!plan || !addOnText) return null;
      return {
        key,
        planTitle: plan.title,
        addOnText,
        count,
      };
    })
    .filter(Boolean);
  const selectedPhotoAddOnLabel = selectedPhotoAddOns.length
    ? selectedPhotoAddOns
        .map((item) => `${item.planTitle} ${item.addOnText} x${item.count}`)
        .join("、")
    : "—";
  const getPhotoPlanHours = (option) => {
    const match = option?.id?.match(/(\d+)h/);
    return match ? Number(match[1]) : 0;
  };
  const photoSkiBundleDiscount =
    formState.serviceType === "photo" &&
    formState.photoSeason === "winter" &&
    formState.photoSkiBundleChoice === "yes"
      ? selectedPhotoPlanItems.reduce(
          (sum, item) => sum + getPhotoPlanHours(item) * 3000 * item.count,
          0
        )
      : 0;
  const winterAddOnLine = winterPhotoPlan?.addOns?.[0] || "";
  const winterAddOnKey = winterPhotoPlan ? `${winterPhotoPlan.id}:0` : "";
  const winterAddOnCount = winterAddOnKey
    ? formState.photoAddOnSelections[winterAddOnKey] || 0
    : 0;
  const winterAddOnMatch = winterAddOnLine.match(/^(.*?)(\d[\d,]*\s*元\/\S+)$/);
  const winterAddOnLabel = winterAddOnMatch
    ? winterAddOnMatch[1].trim()
    : winterAddOnLine;
  const winterAddOnPrice = winterAddOnMatch
    ? `NT$ ${winterAddOnMatch[2].trim().replace(/\s*元\//, "/")}`
    : "";
  const maxPhotoDates =
    formState.serviceType === "photo" ? photoPlanSelectionCount : Number.POSITIVE_INFINITY;

  useEffect(() => {
    if (formState.serviceType !== "photo") return;
    if (photoPlanSelectionCount === 0 && formState.skiDates.length > 0) {
      setField("skiDates", []);
      return;
    }
    if (
      photoPlanSelectionCount > 0 &&
      formState.skiDates.length > photoPlanSelectionCount
    ) {
      setField("skiDates", formState.skiDates.slice(0, photoPlanSelectionCount));
    }
  }, [formState.serviceType, photoPlanSelectionCount]);
  const skiCoursePricing = {
    full: {
      1: 19200,
      2: 22200,
      3: 25200,
      4: 28200,
      5: 31200,
      6: 34200,
    },
    half: {
      1: 14400,
      2: 17400,
      3: 20400,
      4: 23400,
      5: 26400,
      6: 29400,
    },
  };
  const skiCoursePromoPricing = {
    full: {
      1: 15200,
      2: 18200,
      3: 21200,
      4: 24200,
      5: 27200,
      6: 30200,
    },
    half: {
      1: 11400,
      2: 15400,
      3: 18400,
      4: 21400,
      5: 24400,
      6: 27400,
    },
  };
  const addPhotoTotal = Object.entries(formState.addPhotoQuantities).reduce(
    (sum, [id, count]) => sum + (photoPlanPricing[id]?.price || 0) * count,
    0
  );
  const addPhotoDiscount = Object.entries(formState.addPhotoQuantities).reduce(
    (sum, [id, count]) => sum + (photoPlanPricing[id]?.hours || 0) * 3000 * count,
    0
  );
  const skiSessions = formState.skiDates.map((dateKey) => {
    const profile = getSkiDateProfile(dateKey);
    const duration = getSkiSessionDuration(dateKey);
    const skiType = profile.skiType || formState.skiType;
    const skiPeople = profile.skiPeople || formState.skiPeople;
    const skiPeopleCount = Number.parseInt(skiPeople, 10) || 0;
    return {
      dateKey,
      skiType,
      skiPeople,
      skiPeopleCount,
      skiTypeLabel: skiTypeLabels[skiType] || "—",
      skiPeopleLabel: skiPeople || "—",
      duration,
      durationLabel: skiDurationLabels[duration] || "—",
      slotValue: skiDateSlots[dateKey],
      slotLabel: dateSlotLabel(skiDateSlots[dateKey]),
    };
  });
  const skiTypeSummaryLabel = skiSessions.length
    ? skiSessions.every((session) => session.skiTypeLabel === skiSessions[0].skiTypeLabel)
      ? skiSessions[0].skiTypeLabel
      : skiSessions
          .map((session) => `${session.dateKey}（${session.skiTypeLabel}）`)
          .join("、")
    : skiTypeLabels[formState.skiType] || "—";
  const skiPeopleSummaryLabel = skiSessions.length
    ? skiSessions.every((session) => session.skiPeopleLabel === skiSessions[0].skiPeopleLabel)
      ? skiSessions[0].skiPeopleLabel
      : skiSessions
          .map((session) => `${session.dateKey}（${session.skiPeopleLabel}）`)
          .join("、")
    : formState.skiPeople || "—";
  const skiDurationSummaryLabel = skiSessions.length
    ? skiSessions.every((session) => session.durationLabel === skiSessions[0].durationLabel)
      ? skiSessions[0].durationLabel
      : skiSessions
          .map((session) => `${session.dateKey}（${session.durationLabel}）`)
          .join("、")
    : skiDurationLabels[formState.skiDuration] || "—";
  const skiPeopleCount = skiSessions.length
    ? Math.max(...skiSessions.map((session) => session.skiPeopleCount || 0), 0)
    : Number.parseInt(formState.skiPeople, 10);
  const addEquipmentFee =
    formState.skiEquipment === "extra-help"
      ? skiPeopleCount >= 4
        ? 2000
        : skiPeopleCount >= 1
          ? 1000
          : 0
      : 0;
  const normalizedDiscountCode = formState.discountCode.trim();
  const isEarlyBirdDiscount =
    formState.serviceType === "ski" && normalizedDiscountCode === "#2526EBD";
  const getEarlyBirdPerPersonDiscount = (duration) =>
    duration === "full" ? 300 : duration === "half" ? 200 : 0;
  const earlyBirdDiscountTotal =
    isEarlyBirdDiscount && skiPeopleCount
      ? skiSessions.reduce(
          (sum, session) =>
            sum + getEarlyBirdPerPersonDiscount(session.duration) * (session.skiPeopleCount || 0),
          0
        )
      : 0;
  const coachFeeTotal =
    formState.serviceType === "ski"
      ? formState.skiCoach === "any" || !formState.skiCoach
        ? 0
        : formState.skiCoach === "cash" || formState.skiCoach === "lily"
          ? 3000
          : formState.skiCoach === "qizhen"
            ? 1800
            : 1000
      : 0;
  const skiCourseFee =
    formState.serviceType === "ski" && skiSessions.length && skiPeopleCount
      ? (() => {
          return skiSessions.reduce((sum, session) => {
            const parsed = parseDateKey(session.dateKey);
            const isPromo = parsed && isPromoDate(parsed);
            const safePeople = Math.min(Math.max(session.skiPeopleCount || 0, 1), 6);
            const regularRate = skiCoursePricing[session.duration]?.[safePeople] || 0;
            const promoRate = skiCoursePromoPricing[session.duration]?.[safePeople] || 0;
            return sum + (isPromo ? promoRate : regularRate);
          }, 0);
        })()
      : 0;
  const formatMoney = (amount) => `${amount.toLocaleString("en-US")} 元`;
  const orderTotal =
    formState.serviceType === "photo"
      ? Math.max(0, photoServiceFee - photoSkiBundleDiscount)
      : Math.max(
          0,
          skiCourseFee +
            coachFeeTotal +
            addEquipmentFee +
            addPhotoTotal -
            addPhotoDiscount -
            earlyBirdDiscountTotal
        );
  const formatQty = (value) => {
    if (typeof value === "number") return String(value);
    if (value === "" || value === null || value === undefined) return "";
    return String(value);
  };
  const orderLineItems =
    formState.serviceType === "ski"
      ? [
          {
            key: "ski-course",
            label: "滑雪課程",
            qty: 1,
            amount: formatMoney(skiCourseFee),
          },
          {
            key: "ski-equipment",
            label: "加購裝備協助",
            qty: 1,
            amount: formatMoney(addEquipmentFee),
          },
          {
            key: "ski-coach-fee",
            label: "指定教練費",
            qty: coachFeeTotal ? 1 : "",
            amount: formatMoney(coachFeeTotal),
          },
          {
            key: "ski-add-photo",
            label: "加購攝影服務",
            qty: 1,
            amount: formatMoney(addPhotoTotal),
          },
          {
            key: "ski-add-photo-discount",
            label: "加購雪地攝影折扣",
            qty: 1,
            amount: `-${formatMoney(addPhotoDiscount)}`,
          },
          ...(isEarlyBirdDiscount
            ? [
                {
                  key: "ski-early-bird",
                  label: "早鳥限定優惠",
                  qty: 1,
                  amount: `-${formatMoney(earlyBirdDiscountTotal)}`,
                },
              ]
            : []),
        ]
      : [
          ...selectedPhotoPlanItems.map((item) => ({
            key: `photo-${item.id}`,
            label: `攝影服務 ${item.planTitle} ${item.label}`,
            qty: item.count,
            amount: formatMoney(item.price * item.count),
          })),
          {
            key: "photo-subtotal",
            label: "攝影服務小計",
            qty: "",
            amount: formatMoney(photoServiceFee),
            isSubtotal: true,
          },
          ...(photoSkiBundleDiscount > 0
            ? [
                {
                  key: "photo-bundle-discount",
                  label: "滑雪課程加購優惠",
                  qty: "",
                  amount: `-${formatMoney(photoSkiBundleDiscount)}`,
                },
              ]
            : []),
        ];
  const skiLanguageLabels = {
    "": "ALL",
    中文: "中文",
    英文: "英文",
    日文: "日文",
    粵語: "粵語",
  };
  const photoSeasonLabels = {
    winter: "冬季雪地攝影",
    summer: "夏季旅拍攝影",
  };
  const photoLocationLabels = { tomamu: "星野", furano: "富良野" };
  const coachLabel =
    formState.skiCoach === "any"
      ? "不指定教練"
      : coaches.find((coach) => coach.slug === formState.skiCoach)?.name || "—";
  const selectedDatesLabel = skiSessions.length
    ? skiSessions.map((session) => session.dateKey).join("、")
    : "—";
  const selectedDateSlotsLabel = skiSessions.length
    ? skiSessions.map((session) => session.slotLabel || "未選擇時段").join("、")
    : "—";
  const hasSkiDraftSelection =
    formState.serviceType === "ski" &&
    Boolean(
      formState.skiType ||
        formState.skiResort ||
        formState.skiPeople ||
        formState.skiLevel ||
        formState.skiCoach ||
        formState.skiDuration ||
        formState.skiDates.length ||
        formState.skiEquipment ||
        formState.addPhotoChoice
    );
  const currentSkiCartItem =
    formState.serviceType === "ski" && (currentStep < 3 || hasSkiDraftSelection)
      ? { ...buildSkiCartItem(), id: "current-draft" }
      : null;
  const replaceCurrentDraftInItems = (items) => {
    if (!currentSkiCartItem) return [];
    if (!skiAddDateSourceItemId) {
      return items.length ? items : [currentSkiCartItem];
    }
    if (!items.length) {
      return [currentSkiCartItem];
    }
    if (!items.some((item) => item.id === skiAddDateSourceItemId)) {
      return [...items, currentSkiCartItem];
    }
    return items.map((item) =>
      item.id === skiAddDateSourceItemId ? { ...currentSkiCartItem, id: item.id } : item
    );
  };
  const skiCartPreviewItems = currentSkiCartItem
    ? replaceCurrentDraftInItems(skiCartItems)
    : [];
  const skiCartConfirmationItems = currentSkiCartItem
    ? replaceCurrentDraftInItems(skiCartItems)
    : [];
  const skiEquipmentHelpMode =
    formState.skiEquipment === "in-class-help" || formState.skiEquipment === "extra-help";
  const skiEquipmentBookingItems = skiCartPreviewItems.length
    ? skiCartPreviewItems
    : currentSkiCartItem
      ? [currentSkiCartItem]
      : [];
  const skiEquipmentAssistMaxGroups = Math.max(skiEquipmentBookingItems.length, 1);
  const skiEquipmentAssistSelectedBookingIds = formState.skiEquipmentAssistBookingIds.filter(
    (id) => skiEquipmentBookingItems.some((item) => item.id === id)
  );
  const skiEquipmentAssistSelectedItems = skiEquipmentBookingItems.filter((item) =>
    skiEquipmentAssistSelectedBookingIds.includes(item.id)
  );
  const startAddDateFlow = (sourceItem) => {
    if (!sourceItem) return;
    setSkiAddCourseMode(true);
    setField("skiAddCourseChoice", "add-date");
    restoreSkiDraftForAddDate(sourceItem, sourceItem.id);
    setStep2Index(step2Fields.indexOf("skiDuration"));
  };
  const getMonthGrid = (monthDate) => {
    const year = monthDate.getFullYear();
    const month = monthDate.getMonth();
    const firstOfMonth = new Date(year, month, 1);
    const lastOfMonth = new Date(year, month + 1, 0);
    const firstWeekday = (firstOfMonth.getDay() + 6) % 7;
    const totalDays = lastOfMonth.getDate();
    const days = [];
    const prevMonthLast = new Date(year, month, 0).getDate();

    for (let i = firstWeekday - 1; i >= 0; i -= 1) {
      days.push({
        date: new Date(year, month - 1, prevMonthLast - i),
        inMonth: false,
      });
    }

    for (let day = 1; day <= totalDays; day += 1) {
      days.push({ date: new Date(year, month, day), inMonth: true });
    }

    const nextDays = 42 - days.length;
    for (let day = 1; day <= nextDays; day += 1) {
      days.push({ date: new Date(year, month + 1, day), inMonth: false });
    }

    return days;
  };

  useEffect(() => {
    if (!formState.skiDates.length) return;
    const [year, month] = formState.skiDates[0].split("-").map((part) => Number(part));
    if (!year || !month) return;
    setCalendarMonth(new Date(year, month - 1, 1));
  }, [formState.skiDates]);

  useEffect(() => {
    if (!formState.skiDates.length) return;
    setFormState((prev) => {
      if (!prev.skiDates.length) return prev;
      const nextDurations = { ...(prev.skiSessionDurations || {}) };
      let changed = false;
      prev.skiDates.forEach((dateKey) => {
        if (!nextDurations[dateKey] && prev.skiDuration) {
          nextDurations[dateKey] = prev.skiDuration;
          changed = true;
        }
      });
      return changed ? { ...prev, skiSessionDurations: nextDurations } : prev;
    });
  }, [formState.skiDates]);

  useEffect(() => {
    if (!stepSectionRef.current) return;
    if (typeof window === "undefined") return;
    if (currentStep >= 2) {
      stepSectionRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [currentStep]);

  const validateStep1 = () => {
    const nextErrors = {};
    if (!formState.serviceType) {
      nextErrors.serviceType = "請選擇服務";
    }
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const validateStep2 = () => {
    const nextErrors = {};
    if (formState.serviceType === "ski") {
      if (!formState.skiType) nextErrors.skiType = "請選擇課程";
      if (!formState.skiResort) nextErrors.skiResort = "請選擇雪場";
      if (!formState.skiPeople) nextErrors.skiPeople = "請選擇人數";
      if (!formState.skiLevel) nextErrors.skiLevel = "請選擇能力等級";
      if (coachSelectionMode === "specified" && !formState.skiCoach) {
        nextErrors.skiCoach = "請選擇教練";
      }
      if (!formState.skiDuration) nextErrors.skiDuration = "請選擇課程時長";
      if (!formState.skiDates.length) nextErrors.skiDates = "請選擇日期";
      if (needsSkiTimeSlot && !hasAllDateSlots) {
        nextErrors.skiTimeSlot = "請選擇上課時段";
      }
      if (!formState.skiEquipment) nextErrors.skiEquipment = "請選擇裝備需求";
      if (!formState.addPhotoChoice) nextErrors.addPhotoChoice = "請選擇是否加購";
      if (formState.addPhotoChoice === "yes") {
        const totalCount = Object.values(formState.addPhotoQuantities).reduce(
          (sum, count) => sum + count,
          0
        );
        if (totalCount === 0) {
          nextErrors.addPhotoQuantities = "請選擇加購方案數量";
        }
      }
    }
    if (formState.serviceType === "photo") {
      if (!formState.photoSeason) nextErrors.photoSeason = "請選擇攝影服務";
      if (!formState.photoLocation) nextErrors.photoLocation = "請選擇地點";
      if (photoPlanSelectionCount === 0) {
        nextErrors.photoPlanOption = "請選擇拍攝時數";
      }
      if (
        formState.photoSeason === "winter" &&
        photoPlanSelectionCount > 0 &&
        !formState.photoSkiBundleChoice
      ) {
        nextErrors.photoSkiBundleChoice = "請選擇是否已預約滑雪課程";
      }
      if (
        formState.photoSeason === "winter" &&
        formState.photoSkiBundleChoice === "yes" &&
        !formState.photoSkiOrderId.trim()
      ) {
        nextErrors.photoSkiOrderId = "請填寫滑雪課程訂單編號";
      }
      if (!formState.skiDates.length) nextErrors.skiDates = "請選擇日期";
      if (
        photoPlanSelectionCount > 0 &&
        selectedDateSlotCount !== photoPlanSelectionCount
      ) {
        nextErrors.skiDates = `請選擇 ${photoPlanSelectionCount} 個時段`;
      }
    if (!formState.photoPeople) nextErrors.photoPeople = "請選擇人數";
    }
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const validateSkiEquipmentAssistStep = () => {
    const nextErrors = {};
    const selectedGroupCount = Number.parseInt(
      formState.skiEquipmentAssistGroupCount,
      10
    );
    const normalizedGroupCount = Number.isFinite(selectedGroupCount)
      ? selectedGroupCount
      : 0;
    if (!normalizedGroupCount) {
      nextErrors.skiEquipmentAssistGroupCount = "請選擇組數";
    } else if (normalizedGroupCount > skiEquipmentAssistMaxGroups) {
      nextErrors.skiEquipmentAssistGroupCount = "目前預約數不足";
    }

    if (normalizedGroupCount > 0) {
      if (skiEquipmentAssistSelectedBookingIds.length !== normalizedGroupCount) {
        nextErrors.skiEquipmentAssistSelection = "請選擇對應的預約";
      }

      skiEquipmentAssistSelectedItems.forEach((item) => {
        const peopleCount = Number.parseInt(
          formState.skiEquipmentAssistPeopleCounts[item.id],
          10
        );
        if (!Number.isFinite(peopleCount) || peopleCount <= 0) {
          nextErrors[`skiEquipmentAssistPeopleCounts:${item.id}`] = "請填寫人數";
        }
      });
    }

    setErrors((prev) => ({
      ...clearSkiEquipmentAssistErrors(prev),
      ...nextErrors,
    }));
    return Object.keys(nextErrors).length === 0;
  };

  const validateStep3 = () => {
    const nextErrors = {};
    if (!formState.contactPhone.trim()) nextErrors.contactPhone = "請填寫電話";
    if (!formState.paymentMethod) nextErrors.paymentMethod = "請選擇付款方式";
    if (!formState.cancellationPolicyAccepted) {
      nextErrors.cancellationPolicyAccepted = "請勾選同意取消及修改政策";
    }
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const goNext = (step) => {
    if (step === 1 && validateStep1()) {
      setCurrentStep(2);
      return;
    }
    if (step === 2 && validateStep2()) {
      setCurrentStep(3);
      return;
    }
    if (step === 3 && validateStep3()) {
      setCurrentStep(4);
    }
  };

  const hideHero = authDone && selectedDesign === "design1";
  const contactDisplayName = formState.contactName.trim() || "登入後自動帶入";
  const contactDisplayEmail =
    formState.contactEmail || loginEmail || registerEmail || "登入後自動帶入";
  const selectedServiceLabel =
    formState.serviceType === "ski"
      ? "滑雪課程"
      : formState.serviceType === "photo"
        ? "攝影服務"
        : "";
  const hasSelectedDateSlots =
    formState.serviceType === "ski"
      ? hasAllDateSlots
      : formState.serviceType === "photo"
        ? photoPlanSelectionCount > 0 &&
          selectedDateSlotCount === photoPlanSelectionCount
        : false;
  const summaryItems = [];
  const pushSummaryItem = (label, value) => {
    if (!value || value === "—") return;
    summaryItems.push({ label, value });
  };

  if (selectedServiceLabel) {
    pushSummaryItem("服務", selectedServiceLabel);
  }
  if (formState.serviceType === "ski") {
    if (formState.skiType || skiSessions.length > 0) {
      pushSummaryItem("板類", skiTypeSummaryLabel);
    }
    if (formState.skiResort) {
      pushSummaryItem(
        "雪場",
        skiResortLabels[formState.skiResort] || formState.skiResort
      );
    }
    if (formState.skiPeople) {
      const peopleNotes = [];
      if (hasUnderSix) {
        peopleNotes.push(`3足歲-未滿7歲:${hasUnderSix === "yes" ? "是" : "否"}`);
      }
      if (hasUnderSix === "yes" && underSixCanRide) {
        peopleNotes.push(`可自主滑行:${underSixCanRide === "yes" ? "是" : "否"}`);
      }
      if (hasUnderSix === "yes" && underSixOneOnOneConfirmed) {
        peopleNotes.push("一對一已確認");
      }
      pushSummaryItem(
        "人數",
        peopleNotes.length
          ? `${skiPeopleSummaryLabel}（${peopleNotes.join("，")}）`
          : skiPeopleSummaryLabel
      );
    }
    if (formState.skiLevel) {
      pushSummaryItem(
        "能力等級",
        skiLevelLabels[formState.skiLevel] || formState.skiLevel
      );
    }
    if (formState.skiCoach) {
      pushSummaryItem("教練", coachLabel);
    }
    if (formState.skiLanguage) {
      pushSummaryItem(
        "教練語言",
        skiLanguageLabels[formState.skiLanguage] || formState.skiLanguage
      );
    }
    if (skiSessions.length > 0) {
      pushSummaryItem("課程時長", skiDurationSummaryLabel);
    }
    if (formState.skiDates.length > 0) {
      pushSummaryItem("日期", selectedDatesLabel);
    }
    if (hasSelectedDateSlots && formState.skiDates.length > 0) {
      pushSummaryItem("時段", selectedDateSlotsLabel);
    }
    if (formState.skiEquipment) {
      pushSummaryItem(
        "裝備需求",
        skiEquipmentLabels[formState.skiEquipment] || formState.skiEquipment
      );
    }
    if (skiEquipmentHelpMode && formState.skiEquipmentAssistGroupCount) {
      pushSummaryItem(
        "協助組數",
        `${formState.skiEquipmentAssistGroupCount} 組`
      );
      skiEquipmentAssistSelectedItems.forEach((item, index) => {
        const assistPeopleCount =
          formState.skiEquipmentAssistPeopleCounts[item.id] || "—";
        pushSummaryItem(
          `協助預約${index + 1}`,
          `${item.dateLabel}｜${item.timeLabel}｜${assistPeopleCount} 人`
        );
      });
    }
    if (formState.addPhotoChoice) {
      pushSummaryItem(
        "加購攝影",
        addPhotoLabels[formState.addPhotoChoice] || formState.addPhotoChoice
      );
    }
    if (formState.addPhotoChoice === "yes" && addPhotoSelectionLabel !== "—") {
      pushSummaryItem("加購方案", addPhotoSelectionLabel);
    }
    if (skiCartItems.length > 0) {
      skiCartItems.forEach((item, index) => {
        pushSummaryItem(
          `已加入預約${index + 1}`,
          `${item.skiTypeLabel}｜${item.skiResortLabel}｜${item.dateLabel}｜${item.timeLabel}`
        );
      });
    }
  }
  if (formState.serviceType === "photo") {
    if (formState.photoSeason) {
      pushSummaryItem(
        "攝影服務",
        photoSeasonLabels[formState.photoSeason] || formState.photoSeason
      );
    }
    if (formState.photoLocation) {
      pushSummaryItem(
        "地點",
        photoLocationLabels[formState.photoLocation] || formState.photoLocation
      );
    }
    if (selectedPhotoPlanItems.length > 0) {
      pushSummaryItem("方案", selectedPhotoPlanLabel);
    }
    if (selectedPhotoAddOns.length > 0) {
      pushSummaryItem("加購內容", selectedPhotoAddOnLabel);
    }
    if (formState.photoSkiBundleChoice) {
      pushSummaryItem(
        "滑雪課程加購優惠",
        formState.photoSkiBundleChoice === "yes" ? "是" : "否"
      );
    }
    if (formState.photoSkiBundleChoice === "yes" && formState.photoSkiOrderId.trim()) {
      pushSummaryItem("訂單編號", formState.photoSkiOrderId.trim());
    }
    if (formState.photoPeople) {
      pushSummaryItem("人數", formState.photoPeople);
    }
    if (formState.skiDates.length > 0) {
      pushSummaryItem("日期", selectedDatesLabel);
    }
    if (hasSelectedDateSlots && formState.skiDates.length > 0) {
      pushSummaryItem("時段", selectedDateSlotsLabel);
    }
  }
  const isDesign2 = selectedDesign === "design2";

  return (
    <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937] flex flex-col">
      <SiteHeader
        forceTransparent
        forceDarkText={hideHero}
        forceLogoColor={hideHero}
        memberAuthenticated={authDone}
        hideBookingCta={authDone}
      />
      <main className="flex-1 pb-24">
        {!hideHero && (
          <section className="relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-[#1c3b5f] via-[#2b5f8f] to-[#7bbbe7]" />
            <div
              className="absolute inset-0 opacity-40"
              style={{
                backgroundImage:
                  "radial-gradient(circle at 20% 20%, rgba(255,255,255,0.35), transparent 45%), radial-gradient(circle at 70% 30%, rgba(255,255,255,0.25), transparent 50%), radial-gradient(circle at 40% 80%, rgba(255,255,255,0.2), transparent 55%)",
              }}
            />
            <div className="relative max-w-6xl mx-auto px-6 pt-32 pb-20 md:pt-36 md:pb-24 text-white text-center">
              <p className="text-xs font-semibold tracking-[0.3em] uppercase text-white/70 font-display">
                Booking
              </p>
              <h1 className="mt-4 text-3xl md:text-4xl font-semibold tracking-wide font-display">
                預約課程
              </h1>
            </div>
          </section>
        )}

        {!authDone ? (
          <section className="mt-20">
            <div className="mx-auto max-w-3xl px-6 md:px-12">
              <div className="border-b border-[#e2e8f0]">
                <div className="flex flex-wrap items-center justify-center gap-12 md:gap-16 text-base md:text-lg font-semibold text-[#6b7280] font-display">
                  <button
                    type="button"
                    onClick={() => setActiveTab("login")}
                    className={`group relative pb-4 transition-colors duration-200 ${
                      activeTab === "login" ? "text-[#111827]" : "hover:text-[#2b5f8f]"
                    }`}
                    aria-current={activeTab === "login" ? "page" : undefined}
                  >
                    會員登入
                    <span
                      className={`absolute left-0 -bottom-[1px] h-0.5 transition-all duration-300 ${
                        activeTab === "login"
                          ? "w-full bg-[#111827]"
                          : "w-0 bg-[#2b5f8f] group-hover:w-full"
                      }`}
                    />
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveTab("register")}
                    className={`group relative pb-4 transition-colors duration-200 ${
                      activeTab === "register" ? "text-[#111827]" : "hover:text-[#2b5f8f]"
                    }`}
                    aria-current={activeTab === "register" ? "page" : undefined}
                  >
                    註冊會員
                    <span
                      className={`absolute left-0 -bottom-[1px] h-0.5 transition-all duration-300 ${
                        activeTab === "register"
                          ? "w-full bg-[#111827]"
                          : "w-0 bg-[#2b5f8f] group-hover:w-full"
                      }`}
                    />
                  </button>
                </div>
              </div>

              {activeTab === "login" ? (
                <form className="mt-10 space-y-6">
                  <label className="block text-sm font-semibold text-[#1f2937]">
                    電子郵件<span className="text-[#ef4444]">*</span>
                    <input
                      type="text"
                      value={loginEmail}
                      onChange={(event) => {
                        setLoginEmail(event.target.value);
                        if (authErrors.loginEmail) {
                          setAuthErrors((prev) => ({ ...prev, loginEmail: "" }));
                        }
                      }}
                      className="mt-2 w-full rounded-sm border border-transparent bg-[#f3f4f6] px-4 py-3 text-sm text-[#1f2937] focus:outline-none focus:ring-2 focus:ring-[#2b5f8f]/30"
                    />
                    {authErrors.loginEmail && (
                      <p className="mt-2 text-xs text-[#ef4444]">
                        {authErrors.loginEmail}
                      </p>
                    )}
                  </label>
                  <label className="block text-sm font-semibold text-[#1f2937]">
                    密碼<span className="text-[#ef4444]">*</span>
                    <span className="relative mt-2 block">
                      <input
                        type={showPassword ? "text" : "password"}
                        value={loginPassword}
                        onChange={(event) => {
                          setLoginPassword(event.target.value);
                          if (authErrors.loginPassword) {
                            setAuthErrors((prev) => ({ ...prev, loginPassword: "" }));
                          }
                        }}
                        className="w-full rounded-sm border border-transparent bg-[#f3f4f6] px-4 py-3 pr-12 text-sm text-[#1f2937] focus:outline-none focus:ring-2 focus:ring-[#2b5f8f]/30"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword((prev) => !prev)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6b7280]"
                        aria-label={showPassword ? "Hide password" : "Show password"}
                      >
                        {showPassword ? (
                          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                            <path
                              d="M3 12s3.6-6 9-6 9 6 9 6-3.6 6-9 6-9-6-9-6z"
                              stroke="currentColor"
                              strokeWidth="1.5"
                            />
                            <circle cx="12" cy="12" r="3.5" stroke="currentColor" strokeWidth="1.5" />
                          </svg>
                        ) : (
                          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                            <path
                              d="M3 12s3.6-6 9-6 9 6 9 6-3.6 6-9 6-9-6-9-6z"
                              stroke="currentColor"
                              strokeWidth="1.5"
                            />
                            <path d="M4 4l16 16" stroke="currentColor" strokeWidth="1.5" />
                          </svg>
                        )}
                      </button>
                    </span>
                    {authErrors.loginPassword && (
                      <p className="mt-2 text-xs text-[#ef4444]">
                        {authErrors.loginPassword}
                      </p>
                    )}
                  </label>
                  <div className="flex items-center justify-center gap-6 text-sm">
                    <label className="flex items-center gap-2 text-[#475569]">
                      <input type="checkbox" className="h-4 w-4" />
                      記住此帳號
                    </label>
                    <a
                      href="https://www.powderlife.com/my-account/lost-password/"
                      className="text-[#7b93a7] hover:text-[#2b5f8f]"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      忘記密碼
                    </a>
                  </div>
                  <div className="flex justify-center">
                    <button
                      type="button"
                      onClick={() => {
                        const nextErrors = {
                          loginEmail: loginEmail.trim() ? "" : "請輸入電子郵件",
                          loginPassword: loginPassword.trim() ? "" : "請輸入密碼",
                          registerEmail: "",
                          registerPassword: "",
                        };
                        setAuthErrors(nextErrors);
                        if (!nextErrors.loginEmail && !nextErrors.loginPassword) {
                          setAuthDone(true);
                        }
                      }}
                      className="group relative inline-flex items-center justify-center px-10 py-4 text-sm font-bold text-white transition-all duration-300 bg-[#8ec8f0] rounded-full hover:bg-[#7bbbe7] hover:scale-105 hover:shadow-[0_0_30px_rgba(142,200,240,0.6)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#8ec8f0] overflow-hidden"
                    >
                      <div className="absolute inset-0 -translate-x-full group-hover:animate-[shimmer_1.5s_infinite] bg-gradient-to-r from-transparent via-white/20 to-transparent"></div>
                      <span className="relative z-10">會員登入</span>
                    </button>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <a
                      href="https://www.powderlife.com/?wc-api=auth&start=google&return=https%3A%2F%2Fwww.powderlife.com%2Fmy-account%2F"
                      className="flex items-center justify-center gap-3 rounded-lg bg-black px-4 py-2.5 text-sm font-semibold text-white transition-transform duration-200 hover:-translate-y-0.5"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <span className="flex h-7 w-7 items-center justify-center rounded bg-white text-black font-bold">
                        G
                      </span>
                      以Google帳號登入
                    </a>
                    <a
                      href="https://www.powderlife.com/?wc-api=auth&start=line&return=https%3A%2F%2Fwww.powderlife.com%2Fmy-account%2F"
                      className="flex items-center justify-center gap-3 rounded-lg bg-[#06c755] px-4 py-2.5 text-sm font-semibold text-white transition-transform duration-200 hover:-translate-y-0.5"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <span className="flex h-7 w-7 items-center justify-center rounded bg-white text-[#06c755] font-bold">
                        L
                      </span>
                      以Line帳號登入
                    </a>
                  </div>
                </form>
              ) : (
                <form className="mt-10 space-y-6">
                  <label className="block text-sm font-semibold text-[#1f2937]">
                    電子郵件<span className="text-[#ef4444]">*</span>
                    <input
                      type="email"
                      value={registerEmail}
                      onChange={(event) => {
                        setRegisterEmail(event.target.value);
                        if (authErrors.registerEmail) {
                          setAuthErrors((prev) => ({ ...prev, registerEmail: "" }));
                        }
                      }}
                      className="mt-2 w-full rounded-sm border border-transparent bg-[#f3f4f6] px-4 py-3 text-sm text-[#1f2937] focus:outline-none focus:ring-2 focus:ring-[#2b5f8f]/30"
                    />
                    {authErrors.registerEmail && (
                      <p className="mt-2 text-xs text-[#ef4444]">
                        {authErrors.registerEmail}
                      </p>
                    )}
                  </label>
                  <label className="block text-sm font-semibold text-[#1f2937]">
                    密碼<span className="text-[#ef4444]">*</span>
                    <span className="relative mt-2 block">
                      <input
                        type={showPassword ? "text" : "password"}
                        value={registerPassword}
                        onChange={(event) => {
                          setRegisterPassword(event.target.value);
                          if (authErrors.registerPassword) {
                            setAuthErrors((prev) => ({ ...prev, registerPassword: "" }));
                          }
                        }}
                        className="w-full rounded-sm border border-transparent bg-[#f3f4f6] px-4 py-3 pr-12 text-sm text-[#1f2937] focus:outline-none focus:ring-2 focus:ring-[#2b5f8f]/30"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword((prev) => !prev)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6b7280]"
                        aria-label={showPassword ? "Hide password" : "Show password"}
                      >
                        {showPassword ? (
                          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                            <path
                              d="M3 12s3.6-6 9-6 9 6 9 6-3.6 6-9 6-9-6-9-6z"
                              stroke="currentColor"
                              strokeWidth="1.5"
                            />
                            <circle cx="12" cy="12" r="3.5" stroke="currentColor" strokeWidth="1.5" />
                          </svg>
                        ) : (
                          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                            <path
                              d="M3 12s3.6-6 9-6 9 6 9 6-3.6 6-9 6-9-6-9-6z"
                              stroke="currentColor"
                              strokeWidth="1.5"
                            />
                            <path d="M4 4l16 16" stroke="currentColor" strokeWidth="1.5" />
                          </svg>
                        )}
                      </button>
                    </span>
                    {authErrors.registerPassword && (
                      <p className="mt-2 text-xs text-[#ef4444]">
                        {authErrors.registerPassword}
                      </p>
                    )}
                  </label>
                  <p className="text-sm text-[#475569]">
                    您的個人資料將用於提供您在本站的體驗、管理帳號存取，以及我們{" "}
                    <a
                      href="http://localhost:5173/privacy-policy"
                      className="text-[#2b5f8f] underline underline-offset-2"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      隱私權政策
                    </a>
                    {" "}中所述之用途。
                  </p>
                  <div className="flex justify-center">
                    <button
                      type="button"
                      onClick={() => {
                        const nextErrors = {
                          loginEmail: "",
                          loginPassword: "",
                          registerEmail: registerEmail.trim() ? "" : "請輸入電子郵件",
                          registerPassword: registerPassword.trim() ? "" : "請輸入密碼",
                        };
                        setAuthErrors(nextErrors);
                      }}
                      className="group relative inline-flex items-center justify-center px-10 py-4 text-sm font-bold text-white transition-all duration-300 bg-[#8ec8f0] rounded-full hover:bg-[#7bbbe7] hover:scale-105 hover:shadow-[0_0_30px_rgba(142,200,240,0.6)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#8ec8f0] overflow-hidden"
                    >
                      <div className="absolute inset-0 -translate-x-full group-hover:animate-[shimmer_1.5s_infinite] bg-gradient-to-r from-transparent via-white/20 to-transparent"></div>
                      <span className="relative z-10">註冊</span>
                    </button>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <a
                      href="https://www.powderlife.com/?wc-api=auth&start=google&return=https%3A%2F%2Fwww.powderlife.com%2Fmy-account%2F"
                      className="flex items-center justify-center gap-3 rounded-lg bg-black px-4 py-2.5 text-sm font-semibold text-white transition-transform duration-200 hover:-translate-y-0.5"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <span className="flex h-7 w-7 items-center justify-center rounded bg-white text-black font-bold">
                        G
                      </span>
                      以Google帳號註冊
                    </a>
                    <a
                      href="https://www.powderlife.com/?wc-api=auth&start=line&return=https%3A%2F%2Fwww.powderlife.com%2Fmy-account%2F"
                      className="flex items-center justify-center gap-3 rounded-lg bg-[#06c755] px-4 py-2.5 text-sm font-semibold text-white transition-transform duration-200 hover:-translate-y-0.5"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <span className="flex h-7 w-7 items-center justify-center rounded bg-white text-[#06c755] font-bold">
                        L
                      </span>
                      以Line帳號註冊
                    </a>
                  </div>
                </form>
              )}
            </div>
          </section>
        ) : selectedDesign === "design1" || selectedDesign === "design2" ? (
          <section className="pt-32">
            <div
              ref={stepSectionRef}
              className={`mx-auto px-6 md:px-12 ${
                isDesign2
                  ? "max-w-6xl grid gap-8 lg:grid-cols-[280px_1fr]"
                  : "max-w-5xl space-y-10"
              }`}
            >
              <div
                className={`px-6 py-4 md:px-10 md:py-6 ${
                  isDesign2 ? "lg:col-span-2" : ""
                }`}
              >
                <div className="flex flex-wrap items-center justify-center gap-4 md:gap-6">
                  {steps.map((step, index) => (
                    <div key={step.id} className="flex items-center gap-3">
                      {step.id <= 2 ? (
                        <button
                          type="button"
                          onClick={() => goToStep(step.id)}
                          className="flex items-center gap-3 text-left"
                        >
                          <div
                            className={`flex h-10 w-10 items-center justify-center rounded-full border text-sm font-bold ${
                              step.id === progressStep
                                ? "border-[#2b5f8f] bg-[#2b5f8f] text-white"
                                : step.id < progressStep
                                  ? "border-[#2b5f8f] text-[#2b5f8f]"
                                  : "border-[#d4dbe4] text-[#94a3b8]"
                            }`}
                          >
                            {step.id}
                          </div>
                          <span
                            className={`text-sm font-semibold ${
                              step.id === progressStep
                                ? "text-[#1f2937]"
                                : step.id < progressStep
                                  ? "text-[#2b5f8f]"
                                  : "text-[#94a3b8]"
                            }`}
                          >
                            {step.title}
                          </span>
                        </button>
                      ) : (
                        <div className="flex items-center gap-3">
                          <div
                            className={`flex h-10 w-10 items-center justify-center rounded-full border text-sm font-bold ${
                              step.id === progressStep
                                ? "border-[#2b5f8f] bg-[#2b5f8f] text-white"
                                : step.id < progressStep
                                  ? "border-[#2b5f8f] text-[#2b5f8f]"
                                  : "border-[#d4dbe4] text-[#94a3b8]"
                            }`}
                          >
                            {step.id}
                          </div>
                          <span
                            className={`text-sm font-semibold ${
                              step.id === progressStep
                                ? "text-[#1f2937]"
                                : step.id < progressStep
                                  ? "text-[#2b5f8f]"
                                  : "text-[#94a3b8]"
                            }`}
                          >
                            {step.title}
                          </span>
                        </div>
                      )}
                      {index < steps.length - 1 && (
                        <span className="hidden md:block h-px w-10 bg-[#d4dbe4]" />
                      )}
                    </div>
                  ))}
                </div>
              </div>
              {isDesign2 && (
                <aside className="lg:sticky lg:top-24 h-fit rounded-sm border border-[#e2e8f0] bg-white px-5 py-6 shadow-sm">
                  <p className="text-sm font-semibold text-[#1f2937] font-display">
                    已選擇
                  </p>
                  {summaryItems.length ? (
                    <div className="mt-4 space-y-3">
                      {summaryItems.map((item) => (
                        <div
                          key={`${item.label}-${item.value}`}
                          className="rounded-sm border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3"
                        >
                          <p className="text-[11px] font-semibold text-[#94a3b8]">
                            {item.label}
                          </p>
                          <p className="mt-2 text-sm font-semibold text-[#1f2937]">
                            {item.value}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-4 text-sm text-[#94a3b8]">尚未選擇服務</p>
                  )}
                </aside>
              )}

              <div className={isDesign2 ? "space-y-10" : ""}>
                {currentStep === 1 && (
                  <div className="rounded-sm bg-white px-6 py-8 md:px-10 md:py-10">
                    <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                      Step 1
                    </p>
                    <h2 className="mt-3 text-2xl font-semibold text-[#1f2937] font-display">
                      服務選擇
                    </h2>
                    <p className="mt-3 text-sm text-[#64748b]">
                      請問您今天要預約的是？
                    </p>

                    <div className="mt-6 grid gap-4 md:grid-cols-2">
                      {[
                        { id: "ski", label: "滑雪課程" },
                        { id: "photo", label: "攝影服務" },
                      ].map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => {
                            setField("serviceType", item.id);
                            setStep2Index(0);
                            setHasUnderSix("");
                            setUnderSixCanRide("");
                            setUnderSixOneOnOneConfirmed(false);
                            setSkiAddCourseMode(false);
                            setSkiAddDateSourceItemId("");
                            clearSkiEquipmentAssistState();
                            setField("skiAddCourseChoice", "");
                            setSkiDateSlots({});
                            setDateSlotError("");
                            setCurrentStep(2);
                          }}
                          className={`rounded-sm border px-6 py-5 text-left text-sm font-semibold transition-all ${
                            formState.serviceType === item.id
                              ? "border-[#2b5f8f] bg-[#e9eef3]"
                              : "border-[#d4dbe4] bg-[#f8fafc] hover:border-[#2b5f8f]"
                          }`}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                    {renderError("serviceType")}
                  </div>
                )}

                {currentStep === 2 && (
                  <div className="rounded-sm bg-white px-6 py-8 md:px-10 md:py-10">
                    <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                      {stepSectionLabel}
                    </p>
                    <h2 className="mt-3 text-2xl font-semibold text-[#1f2937] font-display">
                      {step2Title}
                    </h2>

                    <div className="mt-6">
                      {formState.serviceType === "ski" && step2Fields[step2Index] === "skiType" && (
                        <div>
                          <p className="text-sm font-semibold text-[#1f2937]">
                            選擇板類<span className="text-[#ef4444]">*</span>
                          </p>
                          <p className="mt-2 text-xs text-[#64748b]">
                            如同時為家人或朋友預約不同板類，請分開預定課程
                          </p>
                          <div className="mt-4 grid gap-3 md:grid-cols-2">
                            {[
                              { id: "board", label: "單板 Snowboarding" },
                              { id: "ski", label: "雙板 Ski" },
                            ].map((item) => (
                              <button
                                key={item.id}
                                type="button"
                                onClick={() => {
                                  setField("skiType", item.id);
                                  setStep2Index((prev) =>
                                    Math.min(prev + 1, step2Fields.length - 1)
                                  );
                                }}
                                className={`rounded-sm border px-6 py-4 text-left text-sm font-semibold transition-all ${
                                  formState.skiType === item.id
                                    ? "border-[#2b5f8f] bg-[#e9eef3]"
                                    : "border-[#d4dbe4] bg-[#f8fafc] hover:border-[#2b5f8f]"
                                }`}
                              >
                                {item.label}
                              </button>
                            ))}
                          </div>
                          {renderError("skiType")}
                        </div>
                      )}

                      {formState.serviceType === "ski" &&
                        step2Fields[step2Index] === "skiResort" && (
                          <div>
                            <p className="text-sm font-semibold text-[#1f2937]">
                              選擇雪場<span className="text-[#ef4444]">*</span>
                            </p>
                            <div className="mt-4 grid gap-3 md:grid-cols-2">
                              {[
                                { id: "off-piste", label: "野雪嚮導 Off-piste" },
                                { id: "tomamu", label: "星野 Tomamu" },
                                { id: "furano", label: "富良野 Furano" },
                                { id: "minami-furano", label: "南富良野" },
                                { id: "kamui", label: "神居 Kamui" },
                                { id: "racey", label: "夕張 Racey" },
                                { id: "sahoro", label: "佐幌 Sahoro" },
                                { id: "teine", label: "手稲 Teine" },
                                { id: "kokusai", label: "札幌國際 Kokusai" },
                                { id: "kiroro", label: "喜樂樂 Kiroro" },
                                { id: "rusutsu", label: "留壽都 Rusutsu" },
                                { id: "niseko", label: "新雪谷 Niseko" },
                                { id: "santa-present-park", label: "聖誕禮物公園 Santa Present Park" },
                              ].map((item) => (
                                <button
                                  key={item.id}
                                  type="button"
                                  onClick={() => {
                                    setField("skiResort", item.id);
                                    setStep2Index((prev) =>
                                      Math.min(prev + 1, step2Fields.length - 1)
                                    );
                                  }}
                                  className={`rounded-sm border px-6 py-4 text-left text-sm font-semibold transition-all ${
                                    formState.skiResort === item.id
                                      ? "border-[#2b5f8f] bg-[#e9eef3]"
                                      : "border-[#d4dbe4] bg-[#f8fafc] hover:border-[#2b5f8f]"
                                  }`}
                                >
                                  {item.label}
                                </button>
                              ))}
                            </div>
                            {renderError("skiResort")}
                          </div>
                        )}

                    {formState.serviceType === "ski" && step2Fields[step2Index] === "skiPeople" && (
                      <div>
                        <p className="text-sm font-semibold text-[#1f2937]">
                          選擇人數<span className="text-[#ef4444]">*</span>
                        </p>
                        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3">
                          {["1", "2", "3", "4", "5", "6"].map((count) => (
                            <button
                              key={count}
                              type="button"
                              onClick={() => {
                                if (count !== formState.skiPeople) {
                                  setHasUnderSix("");
                                  setUnderSixCanRide("");
                                  setUnderSixOneOnOneConfirmed(false);
                                }
                                setField("skiPeople", count);
                              }}
                              className={`rounded-sm border px-6 py-4 text-left text-sm font-semibold transition-all ${
                                formState.skiPeople === count
                                  ? "border-[#2b5f8f] bg-[#e9eef3]"
                                  : "border-[#d4dbe4] bg-[#f8fafc] hover:border-[#2b5f8f]"
                              }`}
                            >
                              {count}
                            </button>
                          ))}
                        </div>
                        <div className="mt-4">
                          <p className="text-sm font-semibold text-[#1f2937]">
                            是否有3足歲 - 未滿7歲學員
                          </p>
                          <div className="mt-3 grid grid-cols-2 gap-3">
                            {[
                              { id: "yes", label: "是" },
                              { id: "no", label: "否" },
                            ].map((item) => (
                              <button
                                key={item.id}
                                type="button"
                                onClick={() => {
                                  setHasUnderSix(item.id);
                                  setUnderSixOneOnOneConfirmed(false);
                                  if (item.id === "no") {
                                    setUnderSixCanRide("");
                                  }
                                }}
                                className={`rounded-sm border px-6 py-4 text-left text-sm font-semibold transition-all ${
                                  hasUnderSix === item.id
                                    ? "border-[#2b5f8f] bg-[#e9eef3]"
                                    : "border-[#d4dbe4] bg-[#f8fafc] hover:border-[#2b5f8f]"
                                }`}
                              >
                                {item.label}
                              </button>
                            ))}
                          </div>
                        </div>
                        {hasUnderSix === "yes" && (
                          <div className="mt-4 space-y-4">
                            <div>
                              <p className="text-sm font-semibold text-[#1f2937]">
                                3足歲 - 未滿7歲學員是否可以自主滑行？
                              </p>
                              <div className="mt-3 grid grid-cols-2 gap-3">
                                {[
                                  { id: "yes", label: "是" },
                                  { id: "no", label: "否" },
                                ].map((item) => (
                                  <button
                                    key={item.id}
                                    type="button"
                                    onClick={() => {
                                      setUnderSixCanRide(item.id);
                                      setUnderSixOneOnOneConfirmed(false);
                                    }}
                                    className={`rounded-sm border px-6 py-4 text-left text-sm font-semibold transition-all ${
                                      underSixCanRide === item.id
                                        ? "border-[#2b5f8f] bg-[#e9eef3]"
                                      : "border-[#d4dbe4] bg-[#f8fafc] hover:border-[#2b5f8f]"
                                    }`}
                                  >
                                    {item.label}
                                  </button>
                                ))}
                              </div>
                            </div>
                            {underSixCanRide === "no" && !underSixOneOnOneConfirmed && (
                              <div className="rounded-sm border border-[#d4dbe4] bg-[#f8fafc] px-4 py-4 text-sm text-[#475569]">
                                <p>
                                  為了確保3足歲 - 未滿7歲學員的安全和學習效果
                                  我們建議您選擇 1 對 1 的教學方式
                                </p>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setUnderSixOneOnOneConfirmed(true);
                                    setField("skiPeople", "1");
                                  }}
                                  className="mt-3 rounded-sm bg-[#2b5f8f] px-4 py-2 text-sm font-semibold text-white"
                                >
                                  確認選擇 1 對 1
                                </button>
                              </div>
                            )}
                          </div>
                        )}
                        {renderError("skiPeople")}
                      </div>
                    )}

                    {formState.serviceType === "ski" && step2Fields[step2Index] === "skiLevel" && (
                      <div>
                        <p className="text-sm font-semibold text-[#1f2937]">
                          能力等級<span className="text-[#ef4444]">*</span>
                        </p>
                        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3">
                          {[
                            { id: "none", label: "無經驗" },
                            { id: "entry", label: "入門" },
                            { id: "basic", label: "初階" },
                            { id: "mid", label: "中階" },
                            { id: "high", label: "高階" },
                            { id: "pro", label: "專家" },
                          ].map((item) => (
                            <button
                              key={item.id}
                              type="button"
                              onClick={() => {
                                setField("skiLevel", item.id);
                                setStep2Index((prev) => Math.min(prev + 1, step2Fields.length - 1));
                              }}
                              className={`rounded-sm border px-6 py-4 text-left text-sm font-semibold transition-all ${
                                formState.skiLevel === item.id
                                  ? "border-[#2b5f8f] bg-[#e9eef3]"
                                  : "border-[#d4dbe4] bg-[#f8fafc] hover:border-[#2b5f8f]"
                              }`}
                            >
                              {item.label}
                            </button>
                          ))}
                        </div>
                        {renderError("skiLevel")}
                      </div>
                    )}

                    {formState.serviceType === "ski" && step2Fields[step2Index] === "skiCoach" && (
                      <div>
                        <p className="text-sm font-semibold text-[#1f2937]">
                          選擇教練<span className="text-[#ef4444]">*</span>
                        </p>
                        <div className="mt-4 grid gap-4 md:grid-cols-2">
                          <button
                            type="button"
                            onClick={() => {
                              setCoachSelectionMode("any");
                              setField("skiCoach", "any");
                              setField("skiLanguage", "");
                              setCoachQuery("");
                            }}
                            className={`rounded-sm border px-6 py-5 text-left transition-all ${
                              coachSelectionMode === "any"
                                ? "border-[#2b5f8f] bg-[#e9eef3]"
                                : "border-[#d4dbe4] bg-[#f8fafc] hover:border-[#2b5f8f]"
                            }`}
                          >
                            <p className="text-base font-semibold text-[#1f2937]">不指定</p>
                            <p className="mt-2 text-sm leading-relaxed text-[#64748b]">
                              系統將自動為您安排適合的教練。
                            </p>
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setCoachSelectionMode("specified");
                              setField("skiCoach", "");
                              setField("skiLanguage", "");
                              setCoachQuery("");
                            }}
                            className={`rounded-sm border px-6 py-5 text-left transition-all ${
                              coachSelectionMode === "specified"
                                ? "border-[#2b5f8f] bg-[#e9eef3]"
                                : "border-[#d4dbe4] bg-[#f8fafc] hover:border-[#2b5f8f]"
                            }`}
                          >
                            <p className="text-base font-semibold text-[#1f2937]">指定教練</p>
                            <p className="mt-2 text-sm leading-relaxed text-[#64748b]">
                              如需指定授課語言，請直接指定教練。
                            </p>
                          </button>
                        </div>
                        {coachSelectionMode === "specified" && (
                          <div className="mt-6 space-y-5">
                            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                              <div className="flex flex-wrap gap-2">
                                {coachLanguageOptions.map((lang) => (
                                  <button
                                    key={lang.label}
                                    type="button"
                                    onClick={() => setField("skiLanguage", lang.id)}
                                    className={`rounded-full border px-4 py-2 text-xs font-semibold transition-all ${
                                      formState.skiLanguage === lang.id
                                        ? "border-[#2b5f8f] bg-[#e9eef3] text-[#1f2937] shadow-[0_0_0_1px_rgba(43,95,143,0.18)]"
                                        : "border-[#d4dbe4] bg-white text-[#64748b] hover:border-[#2b5f8f] hover:text-[#2b5f8f]"
                                    }`}
                                  >
                                    {lang.label}
                                  </button>
                                ))}
                              </div>
                              <div className="relative w-full lg:w-80">
                                <input
                                  type="text"
                                  value={coachQuery}
                                  onChange={(event) => setCoachQuery(event.target.value)}
                                  placeholder="搜尋教練名稱"
                                  className="w-full rounded-sm border border-[#e2e8f0] bg-white px-3 py-2 pr-10 text-sm text-[#1f2937] focus:border-[#2b5f8f] focus:outline-none focus:ring-0"
                                />
                                <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[#94a3b8]">
                                  <svg
                                    viewBox="0 0 24 24"
                                    fill="none"
                                    className="h-4 w-4"
                                    aria-hidden="true"
                                  >
                                    <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="1.6" />
                                    <path d="M16.2 16.2L20 20" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                                  </svg>
                                </span>
                              </div>
                            </div>
                            <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
                              {filteredCoaches.map((coach) => (
                                <button
                                  key={coach.slug}
                                  type="button"
                                  onClick={() => {
                                    setCoachSelectionMode("specified");
                                    setField("skiCoach", coach.slug);
                                  }}
                                  className={`bg-white border rounded-lg overflow-hidden text-center transition-transform duration-300 hover:-translate-y-1 ${
                                    formState.skiCoach === coach.slug
                                      ? "border-[#2b5f8f] shadow-[0_20px_40px_rgba(43,95,143,0.12)]"
                                      : "border-[#e5e9f2] shadow-[0_20px_40px_rgba(15,23,42,0.08)]"
                                  }`}
                                >
                                  <div className="w-full h-48 bg-[#f8fafc]">
                                    <img loading="lazy" decoding="async"
                                      src={coach.image}
                                      alt={coach.name}
                                      className={`w-full h-full object-cover object-top ${
                                        coach.slug === "dylan" ? "coach-image-dylan" : ""
                                      }`}
                                      style={coach.slug === "lily" ? { objectPosition: "center 0%" } : undefined}
                                    />
                                  </div>
                                  <div className="px-6 py-8">
                                    <h3 className="text-lg font-semibold text-[#1f2937] font-lora">{coach.name}</h3>
                                    {coach.coachType && (
                                      <p className="mt-3 text-sm font-semibold text-[#4b5563]">
                                        {coach.coachType}
                                      </p>
                                    )}
                                    {coach.cardBio && (
                                      <p className="mt-3 text-sm leading-relaxed text-[#6b7280]">
                                        {coach.cardBio}
                                      </p>
                                    )}
                                    {coach.languages && (
                                      <p className="mt-3 text-sm font-semibold text-[#64748b]">
                                        {coach.languages}
                                      </p>
                                    )}
                                    <p className="mt-2 text-sm font-semibold text-brand-orange font-display">
                                      + NT$
                                      {coach.slug === "cash" || coach.slug === "lily"
                                        ? "3000"
                                        : coach.slug === "qizhen"
                                          ? "1800"
                                          : "1000"}
                                    </p>
                                  </div>
                                </button>
                              ))}
                            </div>
                            {filteredCoaches.length === 0 && (
                              <p className="text-xs text-[#94a3b8]">
                                沒有符合條件的教練。
                              </p>
                            )}
                          </div>
                        )}
                        {renderError("skiCoach")}
                      </div>
                    )}

                    {formState.serviceType === "ski" && step2Fields[step2Index] === "skiDuration" && (
                      <div>
                        <p className="text-sm font-semibold text-[#1f2937]">
                          選擇課程時長<span className="text-[#ef4444]">*</span>
                        </p>
                        <div className="mt-6 grid gap-4 md:grid-cols-2">
                          {[
                            {
                              id: "full",
                              title: "全天",
                              lines: ["上課時數5小時", "休息一小時"],
                            },
                            {
                              id: "half",
                              title: "半天",
                              lines: ["上課時數3小時"],
                            },
                          ].map((item) => (
                            <button
                              key={item.id}
                              type="button"
                              onClick={() => {
                                setSkiDurationForSelectedDate(item.id);
                                if (formState.skiAddCourseChoice !== "add-date") {
                                  setSkiAddCourseMode(false);
                                  setField("skiAddCourseChoice", "");
                                  setSkiDateSlots({});
                                }
                                const nextIndex = step2Fields.indexOf("skiDate");
                                setStep2Index(nextIndex === -1 ? step2Index + 1 : nextIndex);
                              }}
                              className={`rounded-sm border px-6 py-5 text-left text-sm font-semibold transition-all ${
                                selectedSkiDateDuration === item.id
                                  ? "border-[#2b5f8f] bg-[#e9eef3]"
                                  : "border-[#d4dbe4] bg-[#f8fafc] hover:border-[#2b5f8f]"
                              }`}
                            >
                              <p className="text-base text-[#1f2937]">{item.title}</p>
                              <div className="mt-3 space-y-1 text-xs text-[#64748b]">
                                {item.lines.map((line) => (
                                  <p key={line}>{line}</p>
                                ))}
                              </div>
                            </button>
                          ))}
                        </div>
                        {renderError("skiDuration")}
                      </div>
                    )}

                    {step2Fields[step2Index] === "skiDate" && (
                      <div>
                        <p className="text-sm font-semibold text-[#1f2937]">
                          {formState.serviceType === "photo" ? "拍攝日期" : "選擇日期"}
                          <span className="text-[#ef4444]">*</span>
                        </p>
                        <div className="mt-4">
                          {formState.skiDates.length > 0 && (
                            <div className="flex flex-wrap items-center gap-2">
                              {formState.skiDates.map((dateKey) => (
                                <button
                                  key={dateKey}
                                  type="button"
                                  onClick={() => {
                                    const nextDates = formState.skiDates.filter((item) => item !== dateKey);
                                    setFormState((prev) => {
                                      const nextDurations = { ...(prev.skiSessionDurations || {}) };
                                      delete nextDurations[dateKey];
                                      const nextProfiles = { ...(prev.skiDateProfiles || {}) };
                                      delete nextProfiles[dateKey];
                                      return {
                                        ...prev,
                                        skiDates: nextDates,
                                        skiSessionDurations: nextDurations,
                                        skiDateProfiles: nextProfiles,
                                      };
                                    });
                                    setSkiDateSlots((prev) => {
                                      const next = { ...prev };
                                      delete next[dateKey];
                                      return next;
                                    });
                                    updateActiveSkiDate(nextDates, dateKey);
                                    setDateSlotError("");
                                    setErrors((prev) => ({ ...prev, skiDates: "", skiTimeSlot: "" }));
                                  }}
                                  className={`flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-semibold text-white ${
                                    (() => {
                                      const parsed = parseDateKey(dateKey);
                                      return parsed && isPromoDate(parsed)
                                        ? "border-brand-orange bg-brand-orange"
                                        : "border-[#2b5f8f] bg-[#2b5f8f]";
                                    })()
                                  }`}
                                >
                                  {dateKey}
                                  <span className="text-white/80">X</span>
                                </button>
                              ))}
                            </div>
                          )}
                          {formState.serviceType === "photo" && photoPlanSelectionCount > 0 && (
                            <p className="mt-2 text-xs font-semibold text-[#64748b]">
                              最多可選擇 {maxPhotoDates} 天
                            </p>
                          )}
                        </div>
                        {formState.serviceType === "photo" && formState.skiDates.length > 0 && (
                          <div className="mt-4 space-y-3">
                            {formState.skiDates.map((dateKey) => (
                              <div
                                key={`photo-slot-${dateKey}`}
                                className="flex flex-wrap items-center justify-between gap-3 rounded-sm border border-[#e2e8f0] bg-white px-4 py-3"
                              >
                                <span className="text-sm font-semibold text-[#1f2937]">
                                  {dateKey}
                                </span>
                                <div className="flex gap-2">
                                  {[
                                    { id: "am", label: "上午" },
                                    { id: "pm", label: "下午" },
                                    { id: "flex", label: "可彈性安排" },
                                  ].map((slot) => (
                                    <button
                                      key={`${dateKey}-${slot.id}`}
                                      type="button"
                                      onClick={() => {
                                        setSkiDateSlots((prev) => {
                                          const current = prev[dateKey];
                                          const currentSlots = Array.isArray(current)
                                            ? current
                                            : current
                                              ? [current]
                                              : [];
                                          let nextSlots = currentSlots;
                                          if (slot.id === "flex") {
                                            nextSlots = currentSlots.includes("flex")
                                              ? []
                                              : ["flex"];
                                          } else if (currentSlots.includes(slot.id)) {
                                            nextSlots = currentSlots.filter((id) => id !== slot.id);
                                          } else {
                                            nextSlots = currentSlots
                                              .filter((id) => id !== "flex")
                                              .concat(slot.id);
                                          }
                                          const next = { ...prev, [dateKey]: nextSlots };
                                          if (
                                            photoPlanSelectionCount > 0 &&
                                            getTotalSlotCount(next) > photoPlanSelectionCount
                                          ) {
                                            setDateSlotError(
                                              `最多可選擇 ${photoPlanSelectionCount} 個時段`
                                            );
                                            return prev;
                                          }
                                          setDateSlotError("");
                                          return next;
                                        });
                                      }}
                                      className={`rounded-sm border px-4 py-2 text-xs font-semibold ${
                                        (Array.isArray(skiDateSlots[dateKey])
                                          ? skiDateSlots[dateKey].includes(slot.id)
                                          : skiDateSlots[dateKey] === slot.id)
                                          ? "border-[#2b5f8f] bg-[#e9eef3] text-[#1f2937]"
                                          : "border-[#d4dbe4] bg-white text-[#64748b] hover:border-[#2b5f8f]"
                                      }`}
                                    >
                                      {slot.label}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            ))}
                            {dateSlotError && (
                              <p className="text-xs text-[#ef4444]">
                                {dateSlotError}
                              </p>
                            )}
                          </div>
                        )}
                        <div className="mt-4 rounded-sm border border-[#e2e8f0] bg-white px-4 py-4 text-sm">
                          <div className="flex items-center justify-between text-[#1f2937]">
                            <button
                              type="button"
                              onClick={() =>
                                setCalendarMonth(
                                  new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() - 1, 1)
                                )
                              }
                              className="text-lg font-semibold"
                              aria-label="Previous month"
                            >
                              &lt;
                            </button>
                            <div className="text-base font-semibold">
                              {monthLabel(calendarMonth)}
                            </div>
                            <button
                              type="button"
                              onClick={() =>
                                setCalendarMonth(
                                  new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 1)
                                )
                              }
                              className="text-lg font-semibold"
                              aria-label="Next month"
                            >
                              &gt;
                            </button>
                          </div>
                          <div className="mt-3 grid grid-cols-7 gap-2 text-center text-xs text-[#64748b]">
                            {weekdays.map((day, index) => (
                              <div key={`${day}-${index}`}>{day}</div>
                            ))}
                          </div>
                          <div className="mt-2 grid grid-cols-7 gap-2 text-center">
                            {getMonthGrid(calendarMonth).map(({ date, inMonth }) => {
                              const dateKey = toDateKey(date);
                              const isSelected = formState.skiDates.includes(dateKey);
                              const isPromoSelected = isSelected && isPromoDate(date);
                              return (
                                <button
                                  key={dateKey}
                                  type="button"
                                  onClick={() => {
                                    if (!inMonth) return;
                                    if (isSelected) {
                                      if (formState.skiAddCourseChoice === "add-date") {
                                        updateActiveSkiDate(formState.skiDates, null, dateKey);
                                        setDateSlotError("");
                                        setErrors((prev) => ({ ...prev, skiDates: "", skiTimeSlot: "" }));
                                        return;
                                      }
                                      const nextDates = formState.skiDates.filter((item) => item !== dateKey);
                                      setField("skiDates", nextDates);
                                      setSkiDateSlots((prev) => {
                                        const next = { ...prev };
                                        delete next[dateKey];
                                        return next;
                                      });
                                      setFormState((prev) => {
                                        const nextProfiles = { ...(prev.skiDateProfiles || {}) };
                                        delete nextProfiles[dateKey];
                                        return {
                                          ...prev,
                                          skiDates: nextDates,
                                          skiDateProfiles: nextProfiles,
                                        };
                                      });
                                      updateActiveSkiDate(nextDates, dateKey);
                                      setDateSlotError("");
                                      return;
                                    }
                                    if (formState.serviceType === "photo") {
                                      if (photoPlanSelectionCount === 1) {
                                        setField("skiDates", [dateKey]);
                                      } else if (
                                        photoPlanSelectionCount > 1 &&
                                        formState.skiDates.length < photoPlanSelectionCount
                                      ) {
                                        setField("skiDates", [...formState.skiDates, dateKey]);
                                      }
                                    } else if (
                                      formState.skiAddCourseChoice === "add-date"
                                    ) {
                                      const draftProfile = getActiveSkiDraftProfile();
                                      const nextDates = [...formState.skiDates, dateKey];
                                      setFormState((prev) => ({
                                        ...prev,
                                        skiDates: nextDates,
                                        skiSessionDurations: {
                                          ...(prev.skiSessionDurations || {}),
                                          [dateKey]: draftProfile.skiDuration,
                                        },
                                        skiDateProfiles: {
                                          ...(prev.skiDateProfiles || {}),
                                          [dateKey]: {
                                            skiType: draftProfile.skiType,
                                            skiPeople: draftProfile.skiPeople,
                                            skiDuration: draftProfile.skiDuration,
                                          },
                                        },
                                      }));
                                      updateActiveSkiDate(nextDates, null, dateKey);
                                      setErrors((prev) => ({ ...prev, skiDates: "", skiTimeSlot: "" }));
                                    } else {
                                      setSingleSkiDate(dateKey);
                                    }
                                    setDateSlotError("");
                                  }}
                                  className={`h-9 w-9 rounded-full text-sm font-semibold ${
                                    isPromoSelected
                                      ? "bg-brand-orange text-white"
                                      : isSelected
                                        ? "bg-[#2b5f8f] text-white"
                                        : inMonth
                                          ? "text-[#1f2937] hover:bg-[#e9eef3]"
                                          : "text-[#cbd5e1]"
                                  }`}
                                  disabled={!inMonth}
                                >
                                  {date.getDate()}
                                </button>
                              );
                            })}
                          </div>
                          <div className="mt-4 flex items-center justify-between text-sm text-[#2b5f8f]">
                            <button
                              type="button"
                              onClick={() => {
                                setFormState((prev) => ({
                                  ...prev,
                                  skiDates: [],
                                  skiSessionDurations: {},
                                  skiDateProfiles: {},
                                }));
                                setSkiDateSlots({});
                                setActiveSkiDateKey("");
                                setDateSlotError("");
                                setErrors((prev) => ({ ...prev, skiDates: "", skiTimeSlot: "" }));
                              }}
                              className="font-semibold"
                            >
                              清除
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                const today = new Date();
                                setCalendarMonth(new Date(today.getFullYear(), today.getMonth(), 1));
                                const todayKey = toDateKey(today);
                                if (formState.serviceType === "photo") {
                                  if (photoPlanSelectionCount === 1) {
                                    setField("skiDates", [todayKey]);
                                  } else if (
                                    photoPlanSelectionCount > 1 &&
                                    formState.skiDates.length < photoPlanSelectionCount
                                  ) {
                                    setField("skiDates", [...formState.skiDates, todayKey]);
                                  }
                                } else if (formState.skiAddCourseChoice === "add-date") {
                                  if (!formState.skiDates.includes(todayKey)) {
                                    const draftProfile = getActiveSkiDraftProfile();
                                    const nextDates = [...formState.skiDates, todayKey];
                                    setFormState((prev) => ({
                                      ...prev,
                                      skiDates: nextDates,
                                      skiSessionDurations: {
                                        ...(prev.skiSessionDurations || {}),
                                        [todayKey]: draftProfile.skiDuration,
                                      },
                                      skiDateProfiles: {
                                        ...(prev.skiDateProfiles || {}),
                                        [todayKey]: {
                                          skiType: draftProfile.skiType,
                                          skiPeople: draftProfile.skiPeople,
                                          skiDuration: draftProfile.skiDuration,
                                        },
                                      },
                                    }));
                                    updateActiveSkiDate(nextDates, null, todayKey);
                                    setErrors((prev) => ({ ...prev, skiDates: "", skiTimeSlot: "" }));
                                  }
                                } else {
                                  setSingleSkiDate(todayKey);
                                }
                              }}
                              className="font-semibold"
                            >
                              今日
                            </button>
                          </div>
                        </div>
                        {renderError("skiDates")}
                      </div>
                    )}

                    {step2Fields[step2Index] === "skiTimeSlot" && (
                      <div>
                        <p className="text-sm font-semibold text-[#1f2937]">
                          請選擇您想要的上課時間<span className="text-[#ef4444]">*</span>
                        </p>
                        {selectedSkiDateKey && (
                          <div className="mt-6 grid gap-4 md:grid-cols-2">
                            {skiTimeSlotOptions.map((slot) => (
                              <button
                                key={slot.id}
                                type="button"
                                onClick={() => {
                                  setSkiDateSlots((prev) => ({
                                    ...prev,
                                    [selectedSkiDateKey]: slot.id,
                                  }));
                                  setErrors((prev) => ({ ...prev, skiTimeSlot: "" }));
                                  setDateSlotError("");
                                }}
                                className={`rounded-sm border px-6 py-5 text-left text-sm font-semibold transition-all ${
                                  skiDateSlots[selectedSkiDateKey] === slot.id
                                    ? "border-[#2b5f8f] bg-[#e9eef3] text-[#1f2937]"
                                    : "border-[#d4dbe4] bg-white text-[#64748b] hover:border-[#2b5f8f]"
                                }`}
                              >
                                <p className="text-base text-[#1f2937]">{slot.label}</p>
                                {skiDateSlots[selectedSkiDateKey] === slot.id && (
                                  <div className="mt-2 flex items-center gap-2 text-xs font-semibold text-[#2b5f8f]">
                                    <span aria-hidden="true">✓</span>
                                    <span>已選擇此時段</span>
                                  </div>
                                )}
                              </button>
                            ))}
                          </div>
                        )}
                        {dateSlotError && (
                          <p className="mt-3 text-xs text-[#ef4444]">
                            {dateSlotError}
                          </p>
                        )}
                        {renderError("skiTimeSlot")}
                      </div>
                    )}

                    {formState.serviceType === "ski" && step2Fields[step2Index] === "skiAddCourse" && (
                      <div className="space-y-8">
                        <p className="text-sm text-[#64748b]">
                          請選擇您想要繼續新增的課程方式
                        </p>

                        <div className="grid gap-4 md:grid-cols-2">
                          {[
                            {
                              id: "add-date",
                              title: "新增其他天數預約",
                              body: "為同一組學員再新增不同日期的課程",
                            },
                            {
                              id: "add-group",
                              title: "新增其他組數預約",
                              body: "為另一組學員建立新的課程預約",
                            },
                          ].map((item) => {
                            const isSelected = formState.skiAddCourseChoice === item.id;
                            return (
                              <button
                                key={item.id}
                                type="button"
                                onClick={() => {
                                  if (item.id === "add-date") {
                                    setSkiAddCourseMode(true);
                                    setField("skiAddCourseChoice", "add-date");
                                    const activeSource =
                                      (skiAddDateSourceItemId &&
                                        skiCartItems.find((item) => item.id === skiAddDateSourceItemId)) ||
                                      skiCartItems[0] ||
                                      currentSkiCartItem ||
                                      buildSkiCartItem();
                                    if (skiCartItems.length === 1) {
                                      restoreSkiDraftForAddDate(
                                        activeSource,
                                        skiAddDateSourceItemId || activeSource.id
                                      );
                                      setStep2Index(step2Fields.indexOf("skiDuration"));
                                      return;
                                    }
                                    if (skiCartItems.length === 0) {
                                      restoreSkiDraftForAddDate(buildSkiCartItem(), "");
                                      setStep2Index(step2Fields.indexOf("skiDuration"));
                                      return;
                                    }
                                    if (skiAddDateSourceItemId) {
                                      restoreSkiDraftForAddDate(
                                        activeSource,
                                        skiAddDateSourceItemId
                                      );
                                      setStep2Index(step2Fields.indexOf("skiDuration"));
                                      return;
                                    }
                                    setSkiAddDateSourceItemId("");
                                    setDateSlotError("");
                                    setErrors((prev) => ({
                                      ...prev,
                                      skiDates: "",
                                      skiTimeSlot: "",
                                    }));
                                    setStep2Index(step2Fields.indexOf("skiAddCourse"));
                                    return;
                                  }
                                  setSkiAddCourseMode(true);
                                  setField("skiAddCourseChoice", item.id);
                                  if (item.id === "add-group") {
                                    setSkiAddDateSourceItemId("");
                                  }
                                  setStep2Index(
                                    item.id === "add-date"
                                      ? step2Fields.indexOf("skiDuration")
                                      : step2Fields.indexOf("skiType")
                                  );
                                }}
                                className={`rounded-sm border px-6 py-5 text-left text-sm font-semibold transition-all ${
                                  isSelected
                                    ? "border-[#2b5f8f] bg-[#e9eef3]"
                                    : "border-[#d4dbe4] bg-[#f8fafc] hover:border-[#2b5f8f]"
                                }`}
                              >
                                <p className="text-base text-[#1f2937]">{item.title}</p>
                                <p className="mt-3 text-sm text-[#64748b]">{item.body}</p>
                              </button>
                            );
                          })}
                        </div>
                        <div className="space-y-4">
                          <div className="flex items-center gap-2 text-sm font-semibold text-[#1f2937]">
                            <svg
                              width="18"
                              height="18"
                              viewBox="0 0 24 24"
                              fill="none"
                              aria-hidden="true"
                            >
                              <path
                                d="M3 5h2l1.2 7.2A2 2 0 0 0 8.17 14H18a2 2 0 0 0 1.95-1.55l1.05-4.95H6.1"
                                stroke="currentColor"
                                strokeWidth="1.6"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                              />
                              <circle cx="9" cy="19" r="1.5" fill="currentColor" />
                              <circle cx="18" cy="19" r="1.5" fill="currentColor" />
                            </svg>
                            <p>購物車</p>
                          </div>
                          <div className="space-y-4">
                            {formState.skiAddCourseChoice === "add-date" &&
                              skiCartItems.length > 1 &&
                              !skiAddDateSourceItemId && (
                                <p className="px-1 py-1 text-xs text-[#64748b]">
                                  請直接點選下方購物車中的預約，作為新增天數的來源。
                                </p>
                              )}
                            <AnimatePresence initial={false} mode="popLayout">
                              {skiCartPreviewItems.length > 0 ? (
                                skiCartPreviewItems.map((item, index) =>
                                  renderSkiCartItemCard(item, index, {
                                    onRemove: () => removeSkiCartItem(index),
                                    onSelect:
                                      formState.skiAddCourseChoice === "add-date" &&
                                      skiCartItems.length > 1 &&
                                      !skiAddDateSourceItemId
                                        ? () => startAddDateFlow(item)
                                        : undefined,
                                  })
                                )
                            ) : (
                              <motion.p
                                layout
                                initial={{ opacity: 0, y: 8 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -8 }}
                                className="rounded-sm border border-dashed border-[#d4dbe4] bg-[#f8fafc] px-4 py-6 text-sm text-[#94a3b8]"
                              >
                                目前尚未加入任何預約
                              </motion.p>
                            )}
                            </AnimatePresence>
                          </div>
                        </div>
                      </div>
                    )}

                    {formState.serviceType === "ski" && step2Fields[step2Index] === "skiEquipment" && (
                      <div>
                        <p className="text-sm font-semibold text-[#1f2937]">
                          請選擇您的裝備需求<span className="text-[#ef4444]">*</span>
                        </p>
                        <p className="mt-3 text-sm text-[#64748b]">
                          您是否需要教練協助裝備租借？
                        </p>
                        <div className="mt-6 grid gap-4 md:grid-cols-2">
                          {[
                            {
                              id: "rent-self",
                              title: "自行租借不須協助",
                              body: "我會自行到雪場租借裝備",
                              color: "border-[#d4dbe4] bg-[#f8fafc] hover:border-[#2b5f8f]",
                            },
                            {
                              id: "own-gear",
                              title: "自備裝備不須協助",
                              body: "我已準備好自己的裝備",
                              color: "border-[#d4dbe4] bg-[#f8fafc] hover:border-[#2b5f8f]",
                            },
                            {
                              id: "in-class-help",
                              title: "課程時間內協助",
                              body: "需要教練在課程時間內協助租借",
                              note: "不需額外加價，租借時間約30分鐘",
                              color: "border-[#d4dbe4] bg-[#eae7da] hover:border-[#2b5f8f]",
                            },
                            {
                              id: "extra-help",
                              title: "加購協助時間",
                              body: "需要教練額外時間協助租借",
                              note: "1~3人 1,000元, 4~6人 2,000元",
                              color: "border-[#d4dbe4] bg-[#eae7da] hover:border-[#2b5f8f]",
                            },
                          ].map((item) => {
                            const isSelected = formState.skiEquipment === item.id;
                            const isAssistMode =
                              item.id === "in-class-help" || item.id === "extra-help";
                            const isCurrentAssistMode = skiEquipmentHelpMode;
                            return (
                              <button
                                key={item.id}
                                type="button"
                                onClick={() => {
                                  setField("skiEquipment", item.id);
                                  if (isAssistMode) {
                                    if (!isCurrentAssistMode) {
                                      clearSkiEquipmentAssistState();
                                    }
                                    return;
                                  }
                                  clearSkiEquipmentAssistState();
                                  setStep2Index((prev) =>
                                    Math.min(prev + 1, step2Fields.length - 1)
                                  );
                                }}
                                className={`rounded-sm border px-6 py-5 text-left text-sm font-semibold transition-all ${
                                  isSelected ? "border-[#2b5f8f] bg-[#e9eef3]" : item.color
                                }`}
                              >
                                <p className="text-base text-[#1f2937]">{item.title}</p>
                                <p className="mt-3 text-sm text-[#6b7280]">
                                  {item.body.split("\n").map((line, index, lines) => (
                                    <span key={`${item.id}-body-${line}`}>
                                      {line}
                                      {index < lines.length - 1 && <br />}
                                    </span>
                                  ))}
                                </p>
                                {item.note && (
                                  <p className="mt-3 text-sm font-semibold text-[#475569]">
                                    {item.note}
                                  </p>
                                )}
                              </button>
                            );
                          })}
                        </div>
                        {renderError("skiEquipment")}
                        {skiEquipmentHelpMode && (
                          <div className="mt-4">
                            <p className="text-sm font-semibold text-[#1f2937]">
                              請問需要教練協助裝備租借有幾組?
                            </p>
                            <p className="mt-2 text-xs text-[#64748b]">
                              同一預約為一組，如連上三天課程僅需第一天租借裝備。
                            </p>
                            <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-6">
                              {Array.from({ length: skiEquipmentAssistMaxGroups }, (_, index) => {
                                const count = index + 1;
                                const isSelected =
                                  Number.parseInt(
                                    formState.skiEquipmentAssistGroupCount,
                                    10
                                  ) === count;
                                return (
                                  <button
                                    key={count}
                                    type="button"
                                    onClick={() =>
                                      updateSkiEquipmentAssistGroupCount(String(count))
                                    }
                                    className={`rounded-sm border px-6 py-4 text-left text-sm font-semibold transition-all ${
                                      isSelected
                                        ? "border-[#2b5f8f] bg-[#e9eef3]"
                                        : "border-[#d4dbe4] bg-[#f8fafc] hover:border-[#2b5f8f]"
                                    }`}
                                  >
                                    {count}
                                  </button>
                                );
                              })}
                            </div>
                            {renderError("skiEquipmentAssistGroupCount")}

                            {Number.parseInt(formState.skiEquipmentAssistGroupCount, 10) > 0 && (
                              <div className="mt-6 space-y-4">
                                <div>
                                  <p className="text-sm font-semibold text-[#1f2937]">
                                    請選擇是哪幾組預約要協助
                                  </p>
                                  <p className="mt-2 text-xs text-[#64748b]">
                                    點選預約卡片後，輸入這一組有幾人需要協助。
                                  </p>
                                </div>
                                <div className="space-y-4">
                                  {skiEquipmentBookingItems.map((item, index) => {
                                    const selected =
                                      formState.skiEquipmentAssistBookingIds.includes(item.id);
                                    const countValue =
                                      formState.skiEquipmentAssistPeopleCounts[item.id] || "";
                                    return (
                                      <div
                                        key={item.id}
                                        className={`rounded-sm border px-4 py-4 transition-all ${
                                          selected
                                            ? "border-[#2b5f8f] bg-[#e9eef3]"
                                            : "border-[#d4dbe4] bg-white"
                                        }`}
                                      >
                                        <button
                                          type="button"
                                          onClick={() => toggleSkiEquipmentAssistBooking(item.id)}
                                          className="flex w-full items-start justify-between gap-4 text-left"
                                        >
                                          <div>
                                            <p className="text-xs font-semibold text-[#94a3b8] font-display">
                                              預約{index + 1}
                                            </p>
                                            <div className="mt-2 space-y-1 text-sm text-[#475569]">
                                              <p>雪場：{item.skiResortLabel}</p>
                                              <p>能力等級：{item.skiLevelLabel}</p>
                                              <p>教練：{item.skiCoach === "any" ? "不指定教練" : coaches.find((coach) => coach.slug === item.skiCoach)?.name || "—"}</p>
                                              <p>課程時長：{item.skiDurationLabel}</p>
                                              {Array.isArray(item.skiSessions) && item.skiSessions.length > 1 ? (
                                                <div className="mt-2 space-y-2 border-t border-[#eef2f7] pt-2">
                                                  {item.skiSessions.map((session, sessionIndex) => (
                                                    <div key={`${item.id}-assist-${session.dateKey}-${sessionIndex}`} className="space-y-1">
                                                      <p className="text-xs font-semibold text-[#94a3b8]">
                                                        第 {sessionIndex + 1} 天
                                                      </p>
                                                      <p>板類：{session.skiTypeLabel || "—"}</p>
                                                      <p>人數：{session.skiPeopleLabel || "—"}</p>
                                                      <p>日期：{session.dateKey}</p>
                                                      <p>時段：{formatSkiSessionSlotLabel(session)}</p>
                                                    </div>
                                                  ))}
                                                </div>
                                              ) : (
                                                <>
                                                  <p>板類：{item.skiSessions?.[0]?.skiTypeLabel || item.skiTypeLabel}</p>
                                                  <p>人數：{item.skiSessions?.[0]?.skiPeopleLabel || item.skiPeopleLabel}</p>
                                                  <p>日期：{item.dateLabel}</p>
                                                  <p>時段：{formatSkiSessionSlotLabel(item.skiSessions?.[0])}</p>
                                                </>
                                              )}
                                            </div>
                                          </div>
                                          <span className="text-sm font-semibold text-[#2b5f8f]">
                                            {selected ? "已選擇" : "選擇此組"}
                                          </span>
                                        </button>
                                        {selected && (
                                          <label className="mt-4 block text-sm font-semibold text-[#1f2937]">
                                            這一組有幾人需要協助
                                            <span className="text-[#ef4444]">*</span>
                                            <input
                                              type="number"
                                              min="1"
                                              max={item.skiPeopleCount || undefined}
                                              value={countValue}
                                              onChange={(event) =>
                                                updateSkiEquipmentAssistPeopleCount(
                                                  item.id,
                                                  event.target.value
                                                )
                                              }
                                              className="mt-3 w-full rounded-sm border border-[#e2e8f0] bg-white px-4 py-3 text-sm"
                                              placeholder="請輸入人數"
                                            />
                                            {renderError(`skiEquipmentAssistPeopleCounts:${item.id}`)}
                                          </label>
                                        )}
                                      </div>
                                    );
                                  })}
                                </div>
                                {renderError("skiEquipmentAssistSelection")}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {formState.serviceType === "ski" && step2Fields[step2Index] === "addPhoto" && (
                      <div>
                        <p className="text-sm font-semibold text-[#1f2937]">
                          是否加購攝影服務<span className="text-[#ef4444]">*</span>
                        </p>
                        <p className="mt-3 text-sm text-[#64748b]">
                          加購攝影服務每小時折扣 3,000 元
                        </p>
                        <div className="mt-4 grid gap-3 md:grid-cols-2">
                          {[
                            { id: "yes", label: "是" },
                            { id: "no", label: "否" },
                          ].map((item) => (
                            <button
                              key={item.id}
                              type="button"
                              onClick={() => {
                                setField("addPhotoChoice", item.id);
                                if (item.id === "no") {
                                  setField("addPhotoQuantities", {
                                    "photo-1h": 0,
                                    "photo-2h": 0,
                                    "photo-3h": 0,
                                  });
                                  setStep2Index((prev) =>
                                    Math.min(prev + 1, step2Fields.length - 1)
                                  );
                                }
                              }}
                              className={`rounded-sm border px-6 py-4 text-left text-sm font-semibold transition-all ${
                                formState.addPhotoChoice === item.id
                                  ? "border-[#2b5f8f] bg-[#e9eef3]"
                                  : "border-[#d4dbe4] bg-[#f8fafc] hover:border-[#2b5f8f]"
                              }`}
                            >
                              {item.label}
                            </button>
                          ))}
                        </div>
                        {renderError("addPhotoChoice")}

                        {formState.addPhotoChoice === "yes" && (
                          <div className="mt-6 grid gap-4 md:grid-cols-3">
                            {[
                              {
                                id: "photo-1h",
                                title: "1 小時快閃旅行",
                                price: "NT$15,000",
                                image: "/photography-gallery/250115_攝影_Mita-100-scaled.jpg",
                                bullets: ["毛片全給", "保證至少 30 張照片", "適合單一地點拍攝"],
                              },
                              {
                                id: "photo-2h",
                                title: "2 小時經典旅行",
                                price: "NT$24,000",
                                image: "/photography-gallery/250224_Dylan_星野_攝影_Jie-Lin-112-scaled.jpg",
                                bullets: ["毛片全給", "保證至少 60 張", "適合家庭、情侶或多場景拍攝"],
                              },
                              {
                                id: "photo-3h",
                                title: "3 小時半日樂活",
                                price: "NT$32,000",
                                image: "/photography-gallery/250103_攝影_YaYa-260.jpg",
                                bullets: ["毛片全給", "保證至少 90 張", "適合滑雪側拍 + 外景寫真"],
                              },
                            ].map((card) => {
                              const isSelected = formState.addPhotoQuantities[card.id] > 0;
                              return (
                              <div
                                key={card.id}
                                role="button"
                                tabIndex={0}
                                onClick={() => {
                                  if (!isSelected) {
                                    setField("addPhotoQuantities", {
                                      ...formState.addPhotoQuantities,
                                      [card.id]: 1,
                                    });
                                  }
                                }}
                                onKeyDown={(event) => {
                                  if (event.key === "Enter" || event.key === " ") {
                                    event.preventDefault();
                                    if (!isSelected) {
                                      setField("addPhotoQuantities", {
                                        ...formState.addPhotoQuantities,
                                        [card.id]: 1,
                                      });
                                    }
                                  }
                                }}
                                className={`overflow-hidden rounded-sm border bg-white text-left transition-all ${
                                  isSelected
                                    ? "border-[#2b5f8f] shadow-[0_10px_30px_rgba(43,95,143,0.15)]"
                                    : "border-[#e5e9f2] shadow-[0_10px_30px_rgba(15,23,42,0.08)] hover:-translate-y-1"
                                }`}
                              >
                              <div className="h-40 w-full bg-[#e2e8f0]">
                                <img loading="lazy" decoding="async"
                                  src={card.image}
                                  alt={card.title}
                                  className={`h-full w-full object-cover ${
                                      card.id === "photo-3h"
                                        ? "photo-image-3h"
                                        : card.id === "photo-1h"
                                          ? "photo-image-1h"
                                          : ""
                                    }`}
                                  />
                                </div>
                                <div className="px-5 py-5 space-y-2">
                                  <p className="text-sm font-semibold text-[#1f2937]">
                                    {card.title}
                                  </p>
                                  <p className="text-sm font-semibold text-[#1f2937]">
                                    {card.price}
                                  </p>
                                  <div className="text-xs text-[#475569] space-y-1">
                                    {card.bullets.map((line) => (
                                      <p key={`${card.id}-${line}`}>・{line}</p>
                                    ))}
                                  </div>
                                  <div className="mt-4 flex items-center justify-between">
                                    <span className="text-xs font-semibold text-[#64748b]">
                                      選擇數量
                                    </span>
                                    <div className="flex items-center gap-2">
                                      <button
                                        type="button"
                                        onClick={(event) => {
                                          event.stopPropagation();
                                          setField("addPhotoQuantities", {
                                            ...formState.addPhotoQuantities,
                                            [card.id]: Math.max(
                                              0,
                                              formState.addPhotoQuantities[card.id] - 1
                                            ),
                                          });
                                        }}
                                        className="h-7 w-7 rounded-sm border border-[#d4dbe4] text-sm font-semibold text-[#1f2937]"
                                      >
                                        -
                                      </button>
                                      <span className="min-w-[1.5rem] text-center text-sm font-semibold text-[#1f2937]">
                                        {formState.addPhotoQuantities[card.id]}
                                      </span>
                                      <button
                                        type="button"
                                        onClick={(event) => {
                                          event.stopPropagation();
                                          setField("addPhotoQuantities", {
                                            ...formState.addPhotoQuantities,
                                            [card.id]: formState.addPhotoQuantities[card.id] + 1,
                                          });
                                        }}
                                        className="h-7 w-7 rounded-sm border border-[#d4dbe4] text-sm font-semibold text-[#1f2937]"
                                      >
                                        +
                                      </button>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            );
                            })}
                          </div>
                        )}
                        {renderError("addPhotoQuantities")}
                      </div>
                    )}

                    {formState.serviceType === "photo" && step2Fields[step2Index] === "photoSeason" && (
                      <div>
                        <p className="text-sm font-semibold text-[#1f2937]">
                          選擇攝影服務<span className="text-[#ef4444]">*</span>
                        </p>
                        <div className="mt-4 grid gap-3 md:grid-cols-2">
                          {[
                            { id: "winter", label: "冬季雪地攝影" },
                            { id: "summer", label: "夏季旅拍攝影" },
                          ].map((item) => (
                            <button
                              key={item.id}
                              type="button"
                              onClick={() => {
                                setField("photoSeason", item.id);
                                setField("photoPlanCategory", "");
                                setField("photoPlanSelections", {});
                                setField("photoAddOnSelections", {});
                                setField("photoSkiBundleChoice", "");
                                setField("photoSkiOrderId", "");
                                const nextPlans = photoServicePlans[item.id] || [];
                                setPhotoPlanExpanded(nextPlans[0]?.id || "");
                                setStep2Index((prev) => Math.min(prev + 1, step2Fields.length - 1));
                              }}
                              className={`rounded-sm border px-6 py-4 text-left text-sm font-semibold transition-all ${
                                formState.photoSeason === item.id
                                  ? item.id === "winter"
                                    ? "border-[#ABD1F0] bg-[#ABD1F0] text-[#1f2937]"
                                    : "border-[#4B6659] bg-[#4B6659] text-white"
                                  : "border-[#d4dbe4] bg-[#f8fafc] text-[#1f2937] hover:border-[#2b5f8f]"
                              }`}
                            >
                              {item.label}
                            </button>
                          ))}
                        </div>
                        {renderError("photoSeason")}
                      </div>
                    )}

                    {formState.serviceType === "photo" && step2Fields[step2Index] === "photoPlan" && (
                      <div>
                        <p className="text-sm font-semibold text-[#1f2937]">
                          選擇方案<span className="text-[#ef4444]">*</span>
                        </p>
                        {formState.photoSeason === "winter" ? (
                          <div className="mt-4 space-y-6">
                            <div className="grid gap-6 md:grid-cols-3">
                              {photoPlanCategories[0]?.options.map((option) => {
                              const optionCount =
                                formState.photoPlanSelections[option.id] || 0;
                              const isSelected = optionCount > 0;
                              return (
                                <div
                                  key={option.id}
                                  className={`overflow-hidden rounded-sm border border-[#e2e8f0] bg-white text-left shadow-[0_12px_30px_rgba(15,23,42,0.08)] transition-all ${
                                    isSelected
                                      ? "ring-2 ring-[#2b5f8f]"
                                      : "hover:shadow-[0_16px_36px_rgba(15,23,42,0.12)]"
                                  }`}
                                >
                                  <button
                                    type="button"
                                    onClick={() => {
                                      if (optionCount > 0) return;
                                      setField("photoPlanSelections", {
                                        [option.id]: 1,
                                      });
                                      if (typeof window !== "undefined" && window.innerWidth < 768) {
                                        setTimeout(() => {
                                          winterAddOnRef.current?.scrollIntoView({
                                            behavior: "smooth",
                                            block: "start",
                                          });
                                        }, 150);
                                      }
                                    }}
                                    className="w-full text-left"
                                  >
                                    <div className="group aspect-square w-full overflow-hidden bg-[#e2e8f0]">
                                      <img
                                        src={option.image}
                                        alt={option.label}
                                        className={`h-full w-full object-cover transition-transform duration-700 group-hover:scale-105 ${
                                          option.id === "winter-1h" ? "object-[50%_80%]" : ""
                                        }`}
                                        loading="lazy"
                                      />
                                    </div>
                                    <div className="flex gap-5 px-6 py-8">
                                      <div className="flex flex-col items-center gap-4">
                                        <span className="h-10 w-10 opacity-0" aria-hidden="true" />
                                        <span
                                          className="w-px flex-1 bg-[#e2e8f0]"
                                          aria-hidden="true"
                                        />
                                      </div>
                                      <div className="space-y-3">
                                        <h3 className="text-lg font-semibold text-[#1f2937] font-display">
                                          {option.label}
                                        </h3>
                                        <p className="text-lg font-semibold text-[#1f2937] font-display">
                                          NT${option.price.toLocaleString("en-US")}
                                        </p>
                                        <div className="space-y-2 text-sm text-[#475569] max-w-[16rem]">
                                          {option.details.map((line) => (
                                            <p key={`${option.id}-${line}`}>・{line}</p>
                                          ))}
                                        </div>
                                      </div>
                                    </div>
                                  </button>
                                  <div className="border-t border-[#eef2f7] px-6 py-4">
                                    <div className="flex items-center justify-between">
                                      <span className="text-sm font-semibold text-[#64748b]">
                                        數量
                                      </span>
                                      <div className="flex items-center gap-2">
                                        <button
                                          type="button"
                                          onClick={() => {
                                            const nextCount = Math.max(0, optionCount - 1);
                                            setField(
                                              "photoPlanSelections",
                                              nextCount === 0 ? {} : { [option.id]: nextCount }
                                            );
                                          }}
                                          className="h-7 w-7 rounded-sm border border-[#d4dbe4] text-sm font-semibold text-[#1f2937]"
                                        >
                                          -
                                        </button>
                                        <span className="min-w-[1.5rem] text-center text-sm font-semibold text-[#1f2937]">
                                          {optionCount}
                                        </span>
                                        <button
                                          type="button"
                                          onClick={() => {
                                            const nextCount = optionCount + 1;
                                            setField("photoPlanSelections", {
                                              [option.id]: nextCount,
                                            });
                                          }}
                                          className="h-7 w-7 rounded-sm border border-[#d4dbe4] text-sm font-semibold text-[#1f2937]"
                                        >
                                          +
                                        </button>
                                      </div>
                                    </div>
                                  </div>
                                </div>
                              );
                            })}
                            </div>
                            {photoPlanSelectionCount > 0 && winterPhotoPlan && (
                              <div
                                ref={winterAddOnRef}
                                className="rounded-sm border border-[#e2e8f0] bg-white px-6 py-6 space-y-6"
                              >
                                <div>
                                  <p className="text-sm font-semibold text-[#1f2937]">加購服務</p>
                                </div>
                                {winterAddOnLine && (
                                  <div className="space-y-3">
                                    <div className="flex items-start justify-between gap-3">
                                      <span className="text-sm text-[#475569]">
                                        ▸ {winterAddOnLabel}
                                      </span>
                                      {winterAddOnPrice && (
                                        <span className="text-sm font-semibold text-[#1f2937]">
                                          {winterAddOnPrice}
                                        </span>
                                      )}
                                    </div>
                                    <div className="flex items-center justify-between">
                                      <span className="text-xs font-semibold text-[#64748b]">
                                        數量
                                      </span>
                                      <div className="flex items-center gap-2">
                                        <button
                                          type="button"
                                          onClick={() =>
                                            setPhotoAddOnSelection(
                                              winterPhotoPlan.id,
                                              0,
                                              winterAddOnCount - 1
                                            )
                                          }
                                          className="h-7 w-7 rounded-sm border border-[#d4dbe4] text-sm font-semibold text-[#1f2937]"
                                        >
                                          -
                                        </button>
                                        <span className="min-w-[1.5rem] text-center text-sm font-semibold text-[#1f2937]">
                                          {winterAddOnCount}
                                        </span>
                                        <button
                                          type="button"
                                          onClick={() =>
                                            setPhotoAddOnSelection(
                                              winterPhotoPlan.id,
                                              0,
                                              winterAddOnCount + 1
                                            )
                                          }
                                          className="h-7 w-7 rounded-sm border border-[#d4dbe4] text-sm font-semibold text-[#1f2937]"
                                        >
                                          +
                                        </button>
                                      </div>
                                    </div>
                                  </div>
                                )}
                                <div className="space-y-4">
                                  <div>
                                    <p className="text-sm font-semibold text-[#1f2937]">
                                      ▸ 滑雪課程加購優惠
                                    </p>
                                    <p className="mt-2 text-xs text-[#64748b]">
                                      當您同時預約滑雪課程及攝影服務，每小時攝影服務折扣 NT$ 3,000，您是否已預約滑雪課程？
                                    </p>
                                  </div>
                                  <div className="grid gap-3 md:grid-cols-2">
                                    {[
                                      { id: "yes", label: "是" },
                                      { id: "no", label: "否，本次不預約滑雪課程" },
                                    ].map((item) => (
                                      <button
                                        key={item.id}
                                        type="button"
                                        onClick={() => {
                                          setField("photoSkiBundleChoice", item.id);
                                          if (item.id === "no") {
                                            setField("photoSkiOrderId", "");
                                          }
                                        }}
                                        className={`rounded-sm border px-4 py-3 text-left text-sm font-semibold transition-all ${
                                          formState.photoSkiBundleChoice === item.id
                                            ? "border-[#2b5f8f] bg-[#e9eef3]"
                                            : "border-[#d4dbe4] bg-[#f8fafc] hover:border-[#2b5f8f]"
                                        }`}
                                      >
                                        {item.label}
                                      </button>
                                    ))}
                                  </div>
                                  {renderError("photoSkiBundleChoice")}
                                  {formState.photoSkiBundleChoice === "yes" && (
                                    <div className="space-y-2">
                                      <label className="block text-xs font-semibold text-[#64748b]">
                                        訂單編號
                                      </label>
                                      <input
                                        type="text"
                                        value={formState.photoSkiOrderId}
                                        onChange={(event) =>
                                          setField("photoSkiOrderId", event.target.value)
                                        }
                                        className="w-full rounded-sm border border-[#e2e8f0] bg-white px-3 py-2 text-sm text-[#1f2937]"
                                        placeholder="請輸入滑雪課程訂單編號"
                                      />
                                      {renderError("photoSkiOrderId")}
                                    </div>
                                  )}
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setField("serviceType", "ski");
                                      setStep2Index(0);
                                      setHasUnderSix("");
                                      setUnderSixCanRide("");
                                      setUnderSixOneOnOneConfirmed(false);
                                      setSkiAddCourseMode(false);
                                      setField("skiAddCourseChoice", "");
                                      setSkiDateSlots({});
                                      setDateSlotError("");
                                      setCurrentStep(2);
                                      if (typeof window !== "undefined") {
                                        window.scrollTo({ top: 0, behavior: "smooth" });
                                      }
                                    }}
                                    className="w-full rounded-sm border border-[#2b5f8f] px-4 py-3 text-sm font-semibold text-[#2b5f8f] hover:bg-[#e9eef3]"
                                  >
                                    前往預約滑雪課程
                                  </button>
                                </div>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="mt-4 grid gap-4 md:grid-cols-3">
                            {photoPlanCategories.map((plan) => {
                              const isExpanded = photoPlanExpanded === plan.id;
                              const isSelected = formState.photoPlanCategory === plan.id;
                              return (
                                <div
                                  key={plan.id}
                                  className={`overflow-hidden rounded-sm border bg-white ${
                                    isSelected
                                      ? "border-[#2b5f8f] shadow-[0_10px_30px_rgba(43,95,143,0.12)]"
                                      : "border-[#e5e9f2] shadow-[0_10px_30px_rgba(15,23,42,0.08)]"
                                  }`}
                                >
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setField("photoPlanCategory", plan.id);
                                      setPhotoPlanExpanded((prev) =>
                                        prev === plan.id ? "" : plan.id
                                      );
                                    }}
                                  className="flex w-full flex-col items-start gap-3 px-4 py-4 text-left"
                                >
                                  {plan.image && (
                                    <div className="-mx-4 -mt-4 w-[calc(100%+2rem)]">
                                      <img
                                        src={plan.image}
                                        alt={`${plan.title} 方案照片`}
                                        className={`w-full aspect-square rounded-t-sm object-cover ${
                                          plan.id === "summer-light-wedding"
                                            ? "object-[75%_25%]"
                                            : plan.id === "summer-travel" ||
                                                plan.id === "summer-wedding"
                                              ? "object-[80%_20%]"
                                              : ""
                                        }`}
                                        loading="lazy"
                                      />
                                    </div>
                                  )}
                                    <div className="w-full">
                                      {plan.subtitle && (
                                        <p className="text-xs font-semibold text-[#64748b]">
                                          {plan.subtitle}
                                        </p>
                                      )}
                                      <p className="text-base font-semibold text-[#1f2937]">
                                        {plan.title}
                                      </p>
                                    </div>
                                    <span className="ml-auto text-base font-semibold text-[#64748b]">
                                      {isExpanded ? "−" : "+"}
                                    </span>
                                  </button>
                                  {isExpanded && (
                                    <div className="border-t border-[#eef2f7] px-4 py-4 space-y-4">
                                      <div className="space-y-3">
                                        {plan.options.map((option) => {
                                          const optionCount =
                                            formState.photoPlanSelections[option.id] || 0;
                                          const isSelected = optionCount > 0;
                                          return (
                                            <div
                                              key={option.id}
                                              role="button"
                                              tabIndex={0}
                                              onClick={() => {
                                                if (optionCount > 0) return;
                                                setPhotoPlanSelection(option.id, 1);
                                                if (
                                                  plan.id === "summer-light-wedding" ||
                                                  plan.id === "summer-wedding"
                                                ) {
                                                  setField("photoPeople", "2");
                                                }
                                              }}
                                              onKeyDown={(event) => {
                                                if (event.key === "Enter" || event.key === " ") {
                                                  event.preventDefault();
                                                  if (optionCount > 0) return;
                                                  setPhotoPlanSelection(option.id, 1);
                                                  if (
                                                    plan.id === "summer-light-wedding" ||
                                                    plan.id === "summer-wedding"
                                                  ) {
                                                    setField("photoPeople", "2");
                                                  }
                                                }
                                              }}
                                              className={`rounded-sm border px-4 py-3 text-left text-sm font-semibold transition-all ${
                                                isSelected
                                                  ? "border-[#2b5f8f] bg-[#e9eef3] text-[#1f2937]"
                                                  : "border-[#d4dbe4] bg-[#f8fafc] text-[#1f2937] hover:border-[#2b5f8f]"
                                              }`}
                                            >
                                              <div className="flex items-center justify-between gap-2">
                                                <span>{option.label}</span>
                                                <span>
                                                  NT${option.price.toLocaleString("en-US")}
                                                </span>
                                              </div>
                                              <div className="mt-2 space-y-1 text-xs text-[#64748b]">
                                                {option.details.map((line) => (
                                                  <p key={`${option.id}-${line}`}>・{line}</p>
                                                ))}
                                              </div>
                                              <div className="mt-3 flex items-center justify-between">
                                                <span className="text-xs font-semibold text-[#64748b]">
                                                  數量
                                                </span>
                                                <div className="flex items-center gap-2">
                                                  <button
                                                    type="button"
                                                    onClick={(event) => {
                                                      event.stopPropagation();
                                                      setPhotoPlanSelection(
                                                        option.id,
                                                        optionCount - 1
                                                      );
                                                    }}
                                                    className="h-7 w-7 rounded-sm border border-[#d4dbe4] text-sm font-semibold text-[#1f2937]"
                                                  >
                                                    -
                                                  </button>
                                                  <span className="min-w-[1.5rem] text-center text-sm font-semibold text-[#1f2937]">
                                                    {optionCount}
                                                  </span>
                                                  <button
                                                    type="button"
                                                    onClick={(event) => {
                                                      event.stopPropagation();
                                                      setPhotoPlanSelection(
                                                        option.id,
                                                        optionCount + 1
                                                      );
                                                    }}
                                                    className="h-7 w-7 rounded-sm border border-[#d4dbe4] text-sm font-semibold text-[#1f2937]"
                                                  >
                                                    +
                                                  </button>
                                                </div>
                                              </div>
                                            </div>
                                          );
                                        })}
                                      </div>
                                      <div className="space-y-3 text-xs text-[#475569]">
                                        {plan.includes?.length > 0 && (
                                          <details className="px-3 py-2">
                                            <summary className="flex cursor-pointer list-none items-center justify-between font-semibold text-[#1f2937]">
                                              <span>方案內容</span>
                                              <span aria-hidden="true" className="text-base">
                                                +
                                              </span>
                                            </summary>
                                            <div className="mt-2 space-y-1">
                                              {plan.id === "summer-light-wedding" ||
                                              plan.id === "summer-wedding"
                                                ? plan.includes.map((line) => (
                                                    <p
                                                      key={`${plan.id}-include-${line}`}
                                                      className="whitespace-nowrap"
                                                    >
                                                      ・{line}
                                                    </p>
                                                  ))
                                                : plan.includes.map((line) => (
                                                    <p key={`${plan.id}-include-${line}`}>
                                                      ・{line}
                                                    </p>
                                                  ))}
                                            </div>
                                          </details>
                                        )}
                                      </div>
                                      {plan.addOns?.length > 0 && (
                                        <div className="space-y-2 px-3">
                                          <p className="text-xs font-semibold text-[#1f2937]">
                                            加購內容
                                          </p>
                                          <div className="space-y-2 text-xs text-[#475569]">
                                            {plan.addOns.map((line, index) => {
                                              const addOnKey = `${plan.id}:${index}`;
                                              const addOnCount =
                                                formState.photoAddOnSelections[addOnKey] || 0;
                                              const addOnMatch = line.match(
                                                /^(.*?)(\d[\d,]*\s*元\/\S+)$/
                                              );
                                              const addOnLabel = addOnMatch
                                                ? addOnMatch[1].trim()
                                                : line;
                                              const addOnPrice = addOnMatch
                                                ? `NT$ ${addOnMatch[2]
                                                    .trim()
                                                    .replace(/\s*元\//, "/")}`
                                                : "";
                                              return (
                                                <div
                                                  key={addOnKey}
                                                  className="flex flex-col gap-2"
                                                >
                                                  <div className="flex items-start justify-between gap-3">
                                                    <span className="flex-1">・{addOnLabel}</span>
                                                    {addOnPrice && (
                                                      <span className="text-sm font-semibold text-[#1f2937]">
                                                        {addOnPrice}
                                                      </span>
                                                    )}
                                                  </div>
                                                  <div className="flex items-center justify-between gap-3">
                                                    <span className="text-xs font-semibold text-[#64748b]">
                                                      數量
                                                    </span>
                                                    <div className="flex items-center gap-2">
                                                      <button
                                                        type="button"
                                                        onClick={() =>
                                                          setPhotoAddOnSelection(
                                                            plan.id,
                                                            index,
                                                            addOnCount - 1
                                                          )
                                                        }
                                                        className="h-7 w-7 rounded-sm border border-[#d4dbe4] text-sm font-semibold text-[#1f2937]"
                                                      >
                                                        -
                                                      </button>
                                                      <span className="min-w-[1.5rem] text-center text-sm font-semibold text-[#1f2937]">
                                                        {addOnCount}
                                                      </span>
                                                      <button
                                                        type="button"
                                                        onClick={() =>
                                                          setPhotoAddOnSelection(
                                                            plan.id,
                                                            index,
                                                            addOnCount + 1
                                                          )
                                                        }
                                                        className="h-7 w-7 rounded-sm border border-[#d4dbe4] text-sm font-semibold text-[#1f2937]"
                                                      >
                                                        +
                                                      </button>
                                                    </div>
                                                  </div>
                                                </div>
                                              );
                                            })}
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                        {renderError("photoPlan")}
                        {renderError("photoPlanOption")}
                      </div>
                    )}

                    {formState.serviceType === "photo" && step2Fields[step2Index] === "photoLocation" && (
                      <div>
                        <p className="text-sm font-semibold text-[#1f2937]">
                          選擇地點<span className="text-[#ef4444]">*</span>
                        </p>
                        <div className="mt-4 grid gap-3 md:grid-cols-2">
                          {[
                            { id: "tomamu", label: "星野" },
                            { id: "furano", label: "富良野" },
                          ].map((item) => (
                            <button
                              key={item.id}
                              type="button"
                              onClick={() => {
                                setField("photoLocation", item.id);
                                setStep2Index((prev) => Math.min(prev + 1, step2Fields.length - 1));
                              }}
                              className={`rounded-sm border px-6 py-4 text-left text-sm font-semibold transition-all ${
                                formState.photoLocation === item.id
                                  ? "border-[#2b5f8f] bg-[#e9eef3]"
                                  : "border-[#d4dbe4] bg-[#f8fafc] hover:border-[#2b5f8f]"
                              }`}
                            >
                              {item.label}
                            </button>
                          ))}
                        </div>
                        {renderError("photoLocation")}
                      </div>
                    )}

                    {formState.serviceType === "photo" && step2Fields[step2Index] === "photoPeople" && (
                      <div>
                        <p className="text-sm font-semibold text-[#1f2937]">
                          選擇人數<span className="text-[#ef4444]">*</span>
                        </p>
                        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3">
                          {["1", "2", "3", "4", "5", "6"].map((count) => {
                            const isDisabled = photoPeopleRestrictedToTwo && count !== "2";
                            return (
                              <button
                                key={count}
                                type="button"
                                onClick={() => {
                                  if (isDisabled) return;
                                  setField("photoPeople", count);
                                  setStep2Index((prev) =>
                                    Math.min(prev + 1, step2Fields.length - 1)
                                  );
                                }}
                                className={`rounded-sm border px-6 py-4 text-left text-sm font-semibold transition-all ${
                                  formState.photoPeople === count
                                    ? "border-[#2b5f8f] bg-[#e9eef3]"
                                    : "border-[#d4dbe4] bg-[#f8fafc]"
                                } ${
                                  isDisabled
                                    ? "cursor-not-allowed text-[#94a3b8]"
                                    : "hover:border-[#2b5f8f]"
                                }`}
                                disabled={isDisabled}
                              >
                                {count}
                              </button>
                            );
                          })}
                        </div>
                        {renderError("photoPeople")}
                      </div>
                    )}
                  </div>

                  <div className="mt-8 flex justify-between">
                    <button
                      type="button"
                      onClick={() => {
                        if (formState.serviceType === "photo") {
                          if (step2Index === 0) {
                            setStep2Index(0);
                            setCurrentStep(1);
                            return;
                          }
                          setStep2Index((prev) => Math.max(prev - 1, 0));
                          return;
                        }
                        if (step2Fields[step2Index] === "skiEquipment") {
                          setStep2Index(
                            skiAddCourseMode
                              ? step2Fields.indexOf("skiAddCourse")
                              : step2Fields.indexOf("skiTimeSlot")
                          );
                          return;
                        }
                        if (step2Fields[step2Index] === "skiAddCourse") {
                          setStep2Index(step2Fields.indexOf("skiTimeSlot"));
                          return;
                        }
                        if (step2Index === 0) {
                          setStep2Index(0);
                          setCurrentStep(1);
                          return;
                        }
                        setStep2Index((prev) => Math.max(prev - 1, 0));
                      }}
                      className="rounded-full border border-[#d4dbe4] px-8 py-3 text-sm font-semibold text-[#1f2937]"
                    >
                      上一步
                    </button>
                    {step2Fields[step2Index] === "skiPeople" && canAdvanceFromPeople && (
                      <button
                        type="button"
                        onClick={() =>
                          setStep2Index((prev) =>
                            Math.min(prev + 1, step2Fields.length - 1)
                          )
                        }
                        className="rounded-full bg-[#2b5f8f] px-8 py-3 text-sm font-semibold text-white"
                      >
                        下一步
                      </button>
                    )}
                    {step2Fields[step2Index] === "skiCoach" && (
                      <button
                        type="button"
                        onClick={() => {
                          if (coachSelectionMode === "specified" && !formState.skiCoach) {
                            setErrors((prev) => ({ ...prev, skiCoach: "請選擇教練" }));
                            return;
                          }
                          setStep2Index((prev) =>
                            Math.min(prev + 1, step2Fields.length - 1)
                          );
                        }}
                        className="rounded-full bg-[#2b5f8f] px-8 py-3 text-sm font-semibold text-white"
                      >
                        下一步
                      </button>
                    )}
                    {step2Fields[step2Index] === "skiDate" && formState.skiDates.length > 0 && (
                      <button
                        type="button"
                        onClick={() => {
                          if (!canAdvanceFromDates) {
                            if (photoPlanSelectionCount > 0) {
                              setDateSlotError(
                                `請選擇 ${photoPlanSelectionCount} 個時段`
                              );
                            }
                            return;
                          }
                          setStep2Index((prev) =>
                            Math.min(prev + 1, step2Fields.length - 1)
                          );
                        }}
                        className="rounded-full bg-[#2b5f8f] px-8 py-3 text-sm font-semibold text-white"
                      >
                        下一步
                      </button>
                    )}
                    {step2Fields[step2Index] === "skiTimeSlot" && formState.skiDates.length > 0 && (
                      <>
                        {skiDateSlots[selectedSkiDateKey] && (
                              <button
                                type="button"
                                onClick={() => {
                                  if (formState.skiAddCourseChoice === "add-date") {
                                    setSkiAddCourseMode(true);
                                    setStep2Index(step2Fields.indexOf("skiAddCourse"));
                                    return;
                                  }
                                  commitCurrentSkiCartItem();
                                  resetCurrentSkiDraft();
                                  setField("serviceType", "ski");
                                  setSkiAddCourseMode(true);
                                  setStep2Index(step2Fields.indexOf("skiAddCourse"));
                                  setCurrentStep(2);
                                  if (typeof window !== "undefined") {
                                    window.scrollTo({ top: 0, behavior: "smooth" });
                                  }
                                }}
                            className="rounded-full border border-[#2b5f8f] px-8 py-3 text-sm font-semibold text-[#2b5f8f]"
                          >
                            繼續新增課程
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => {
                            if (!hasAllDateSlots) {
                              setDateSlotError("請選擇上課時段");
                              return;
                            }
                            setSkiAddCourseMode(false);
                            setDateSlotError("");
                            setStep2Index(step2Fields.indexOf("skiEquipment"));
                          }}
                          className="rounded-full bg-[#2b5f8f] px-8 py-3 text-sm font-semibold text-white"
                        >
                          下一步
                        </button>
                      </>
                    )}
                    {step2Fields[step2Index] === "skiAddCourse" && (
                      <button
                        type="button"
                        onClick={() =>
                          setStep2Index(step2Fields.indexOf("skiEquipment"))
                        }
                        className="rounded-full bg-[#2b5f8f] px-8 py-3 text-sm font-semibold text-white"
                        >
                          下一步
                        </button>
                    )}
                    {step2Fields[step2Index] === "skiEquipment" && skiEquipmentHelpMode && (
                      <button
                        type="button"
                        onClick={() => {
                          if (!validateSkiEquipmentAssistStep()) return;
                          setStep2Index(step2Fields.indexOf("addPhoto"));
                        }}
                        className="rounded-full bg-[#2b5f8f] px-8 py-3 text-sm font-semibold text-white"
                      >
                        下一步
                      </button>
                    )}
                    {step2Fields[step2Index] === "addPhoto" && (
                      <button
                        type="button"
                        onClick={() => {
                          const nextErrors = {};
                          if (!formState.addPhotoChoice) {
                            nextErrors.addPhotoChoice = "請選擇是否加購";
                          }
                          if (formState.addPhotoChoice === "yes") {
                            const totalCount = Object.values(formState.addPhotoQuantities).reduce(
                              (sum, count) => sum + count,
                              0
                            );
                            if (totalCount === 0) {
                              nextErrors.addPhotoQuantities = "請選擇加購方案數量";
                            }
                          }
                          setErrors((prev) => ({ ...prev, ...nextErrors }));
                          if (Object.keys(nextErrors).length === 0) {
                            setCurrentStep(3);
                          }
                        }}
                        className="rounded-full bg-[#2b5f8f] px-8 py-3 text-sm font-semibold text-white"
                      >
                        下一步
                      </button>
                    )}
                    {step2Fields[step2Index] === "photoPlan" && (
                      <button
                        type="button"
                        onClick={() => {
                          if (photoPlanSelectionCount === 0) {
                            setErrors((prev) => ({
                              ...prev,
                              photoPlanOption: "請選擇拍攝時數",
                            }));
                            return;
                          }
                          if (
                            formState.photoSeason === "winter" &&
                            !formState.photoSkiBundleChoice
                          ) {
                            setErrors((prev) => ({
                              ...prev,
                              photoSkiBundleChoice: "請選擇是否已預約滑雪課程",
                            }));
                            return;
                          }
                          if (
                            formState.photoSeason === "winter" &&
                            formState.photoSkiBundleChoice === "yes" &&
                            !formState.photoSkiOrderId.trim()
                          ) {
                            setErrors((prev) => ({
                              ...prev,
                              photoSkiOrderId: "請填寫滑雪課程訂單編號",
                            }));
                            return;
                          }
                          setStep2Index((prev) =>
                            Math.min(prev + 1, step2Fields.length - 1)
                          );
                        }}
                        className="rounded-full bg-[#2b5f8f] px-8 py-3 text-sm font-semibold text-white"
                      >
                        下一步
                      </button>
                    )}
                    {step2Fields[step2Index] === "photoPeople" && (
                      <button
                        type="button"
                        onClick={() => {
                          if (!formState.photoPeople) return;
                          setCurrentStep(3);
                        }}
                        className="rounded-full bg-[#2b5f8f] px-8 py-3 text-sm font-semibold text-white"
                      >
                        下一步
                      </button>
                    )}
                  </div>
                </div>
              )}

              {currentStep === 3 && (
                <div className="rounded-sm bg-white px-6 py-8 md:px-10 md:py-10">
                  <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                    Step 3
                  </p>
                  <h2 className="mt-3 text-2xl font-semibold text-[#1f2937] font-display">
                    資料確認
                  </h2>
                  <p className="mt-3 text-sm text-[#64748b]">
                    請注意，點擊送出後才算完成報名。
                  </p>
                    <div
                    className={`mt-6 grid gap-6 ${
                      isDesign2 ? "" : "md:grid-cols-[1fr_1.2fr]"
                    }`}
                  >
                    <div className="space-y-6">
                      <div className="px-6 py-6 text-sm text-[#475569] space-y-3">
                        <p className="text-base font-semibold text-[#1f2937] font-display">
                          訂單編號
                        </p>
                        <p>—</p>
                      </div>
                      <div className="h-px bg-[#e2e8f0]" />
                      <div className="px-6 py-6 text-sm text-[#475569] space-y-3">
                        <p className="text-base font-semibold text-[#1f2937] font-display">
                          聯絡資訊
                        </p>
                        <div className="space-y-4">
                          <div className="rounded-sm border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3">
                            <p className="text-xs font-semibold text-[#94a3b8]">聯繫人</p>
                            <p className="mt-2 text-sm font-semibold text-[#1f2937]">
                              {contactDisplayName}
                            </p>
                          </div>
                          <div className="rounded-sm border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3">
                            <p className="text-xs font-semibold text-[#94a3b8]">Email</p>
                            <p className="mt-2 text-sm font-semibold text-[#1f2937]">
                              {contactDisplayEmail}
                            </p>
                          </div>
                          <label className="block text-sm font-semibold text-[#1f2937]">
                            聯絡電話<span className="text-[#ef4444]">*</span>
                            <input
                              type="text"
                              value={formState.contactPhone}
                              onChange={(event) => setField("contactPhone", event.target.value)}
                              className="mt-3 w-full rounded-sm border border-[#e2e8f0] bg-white px-4 py-3 text-sm"
                              placeholder="請輸入聯絡電話"
                            />
                            {renderError("contactPhone")}
                          </label>
                          <p className="text-xs text-[#64748b]">
                            登入後姓名與 Email 會自動帶入，請補充電話方便客服聯繫。
                          </p>
                        </div>
                      </div>
                      {!isDesign2 && (
                        <>
                          <div className="h-px bg-[#e2e8f0]" />
                          <div className="px-6 py-6 text-sm text-[#475569] space-y-3">
                            <p className="text-base font-semibold text-[#1f2937] font-display">
                              訂購內容
                            </p>
                            <div className="space-y-3">
                              {formState.serviceType === "ski" ? (
                                <AnimatePresence initial={false} mode="popLayout">
                                  {skiCartConfirmationItems.map((item, index) =>
                                    renderSkiCartItemCard(item, index, {
                                      showTotal: true,
                                      onRemove: () => removeSkiCartItem(index),
                                    })
                                  )}
                                </AnimatePresence>
                              ) : (
                                <>
                                  <p>報名服務：攝影服務</p>
                                  <p>攝影服務：{photoSeasonLabels[formState.photoSeason] || "—"}</p>
                                  <p>地點：{photoLocationLabels[formState.photoLocation] || "—"}</p>
                                  <p>方案：{selectedPhotoPlanLabel}</p>
                                  <p>加購內容：{selectedPhotoAddOnLabel}</p>
                                  <p>
                                    滑雪課程加購優惠：
                                    {formState.photoSkiBundleChoice === "yes"
                                      ? "是"
                                      : formState.photoSkiBundleChoice === "no"
                                        ? "否"
                                        : "—"}
                                  </p>
                                  {formState.photoSkiBundleChoice === "yes" && (
                                    <p>訂單編號：{formState.photoSkiOrderId || "—"}</p>
                                  )}
                                  <p>人數：{formState.photoPeople || "—"}</p>
                                  <p>日期：{selectedDatesLabel}</p>
                                  {requiresDateSlot && formState.skiDates.length > 0 && (
                                    <p>時段：{selectedDateSlotsLabel}</p>
                                  )}
                                </>
                              )}
                            </div>
                          </div>
                        </>
                      )}
                      {isDesign2 && (
                        <div className="px-6 py-6 text-sm text-[#475569] space-y-4">
                          <div className="space-y-3">
                            <div className="grid grid-cols-[1fr_4rem_6rem] text-xs font-semibold text-[#94a3b8]">
                              <span>服務</span>
                              <span className="text-right">數量</span>
                              <span className="text-right">金額</span>
                            </div>
                            <div className="space-y-2">
                              {orderLineItems.length > 0 ? (
                                orderLineItems.map((item) => (
                                  <div
                                    key={item.key}
                                    className={`grid grid-cols-[1fr_4rem_6rem] gap-3 ${
                                      item.isSubtotal
                                        ? "border-t border-[#e2e8f0] pt-3 mt-2 font-semibold text-[#1f2937]"
                                        : ""
                                    }`}
                                  >
                                    <span>{item.label}</span>
                                    <span className="text-right text-xs font-semibold text-[#64748b]">
                                      {formatQty(item.qty)}
                                    </span>
                                    <span className="text-right font-semibold text-[#1f2937]">
                                      {item.amount}
                                    </span>
                                  </div>
                                ))
                              ) : (
                                <div className="grid grid-cols-[1fr_4rem_6rem] gap-3">
                                  <span>攝影服務</span>
                                  <span className="text-right text-xs font-semibold text-[#64748b]">—</span>
                                  <span className="text-right font-semibold text-[#1f2937]">—</span>
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="space-y-2">
                            <label className="block text-sm font-semibold text-[#1f2937] font-display">
                              折扣優惠碼
                              <input
                                type="text"
                                value={formState.discountCode}
                                onChange={(event) => setField("discountCode", event.target.value)}
                                className="mt-2 w-full rounded-sm border border-[#e2e8f0] bg-white px-3 py-2 text-sm text-[#1f2937]"
                              />
                            </label>
                            {isEarlyBirdDiscount && (
                              <p className="text-xs font-semibold text-[#2b5f8f]">
                                早鳥限定優惠：每人全天課折扣 300 元 / 半天課折扣 200 元
                              </p>
                            )}
                            <label className="block text-sm font-semibold text-[#1f2937] font-display">
                              推薦人
                              <input
                                type="text"
                                value={formState.referrerName}
                                onChange={(event) => setField("referrerName", event.target.value)}
                                className="mt-2 w-full rounded-sm border border-[#e2e8f0] bg-white px-3 py-2 text-sm text-[#1f2937]"
                              />
                            </label>
                            <p className="text-xs text-[#64748b]">
                              收到訂單後，如推薦人經確認為舊生，雙方再享滑雪課程 NT$ 500 折扣
                            </p>
                          </div>
                          <div className="pt-2 text-2xl font-bold text-[#2b5f8f] font-display text-right">
                            訂單總額：{formatMoney(orderTotal)}
                          </div>
                        </div>
                      )}
                    </div>
                    {!isDesign2 && (
                      <div className="px-6 py-6 text-sm text-[#475569] space-y-4">
                        <div className="space-y-3">
                          <div className="grid grid-cols-[1fr_4rem_6rem] text-xs font-semibold text-[#94a3b8]">
                            <span>服務</span>
                            <span className="text-right">數量</span>
                            <span className="text-right">金額</span>
                          </div>
                          <div className="space-y-2">
                            {orderLineItems.length > 0 ? (
                              orderLineItems.map((item) => (
                                <div
                                  key={item.key}
                                  className={`grid grid-cols-[1fr_4rem_6rem] gap-3 ${
                                    item.isSubtotal
                                      ? "border-t border-[#e2e8f0] pt-3 mt-2 font-semibold text-[#1f2937]"
                                      : ""
                                  }`}
                                >
                                  <span>{item.label}</span>
                                  <span className="text-right text-xs font-semibold text-[#64748b]">
                                    {formatQty(item.qty)}
                                  </span>
                                  <span className="text-right font-semibold text-[#1f2937]">
                                    {item.amount}
                                  </span>
                                </div>
                              ))
                            ) : (
                              <div className="grid grid-cols-[1fr_4rem_6rem] gap-3">
                                <span>攝影服務</span>
                                <span className="text-right text-xs font-semibold text-[#64748b]">—</span>
                                <span className="text-right font-semibold text-[#1f2937]">—</span>
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="space-y-2">
                          <label className="block text-sm font-semibold text-[#1f2937] font-display">
                            折扣優惠碼
                            <input
                              type="text"
                              value={formState.discountCode}
                              onChange={(event) => setField("discountCode", event.target.value)}
                              className="mt-2 w-full rounded-sm border border-[#e2e8f0] bg-white px-3 py-2 text-sm text-[#1f2937]"
                            />
                          </label>
                          {isEarlyBirdDiscount && (
                            <p className="text-xs font-semibold text-[#2b5f8f]">
                              早鳥限定優惠：每人全天課折扣 300 元 / 半天課折扣 200 元
                            </p>
                          )}
                          <label className="block text-sm font-semibold text-[#1f2937] font-display">
                            推薦人
                            <input
                              type="text"
                              value={formState.referrerName}
                              onChange={(event) => setField("referrerName", event.target.value)}
                              className="mt-2 w-full rounded-sm border border-[#e2e8f0] bg-white px-3 py-2 text-sm text-[#1f2937]"
                            />
                          </label>
                          <p className="text-xs text-[#64748b]">
                            收到訂單後，如推薦人經確認為舊生，雙方再享滑雪課程 NT$ 500 折扣
                          </p>
                        </div>
                        <div className="pt-2 text-2xl font-bold text-[#2b5f8f] font-display text-right">
                          訂單總額：{formatMoney(orderTotal)}
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="mt-6 px-6 py-6 text-sm text-[#475569] space-y-4">
                    <p className="text-base font-semibold text-[#1f2937] font-display">付款方式</p>
                    <p className="text-xs text-[#64748b]">請擇一選擇</p>
                    <div className="grid gap-3 md:grid-cols-2">
                      {[
                        { id: "tw-bank", label: "台灣地區－銀行轉帳" },
                        { id: "intl-card", label: "其他地區－信用卡支付" },
                      ].map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => setField("paymentMethod", item.id)}
                          className={`rounded-sm border px-4 py-3 text-left text-sm font-semibold transition-all ${
                            formState.paymentMethod === item.id
                              ? "border-[#2b5f8f] bg-[#e9eef3]"
                              : "border-[#d4dbe4] bg-[#f8fafc] hover:border-[#2b5f8f]"
                          }`}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                    {renderError("paymentMethod")}
                  </div>
                  <div className="mt-6 rounded-2xl bg-[#f8fafc] px-6 py-6 text-sm text-[#475569]">
                    <p className="text-base font-semibold text-[#1f2937] font-display mb-3">
                      注意事項
                    </p>
                    <div
                      className="policy-content"
                      dangerouslySetInnerHTML={{
                        __html: footerPagesContent.cancellationPolicy?.html || "",
                      }}
                    />
                  </div>
                  <label className="mt-4 flex items-start justify-center gap-3 text-sm text-[#1f2937]">
                    <input
                      type="checkbox"
                      checked={formState.cancellationPolicyAccepted}
                      onChange={(event) => setField("cancellationPolicyAccepted", event.target.checked)}
                      className="mt-1 h-4 w-4 accent-[#2b5f8f]"
                    />
                    <span>我已閱讀並同意取消及更改政策</span>
                  </label>
                  {errors.cancellationPolicyAccepted && (
                    <p className="mt-2 text-xs text-[#ef4444] text-center">
                      {errors.cancellationPolicyAccepted}
                    </p>
                  )}
                  <div className="mt-6 flex flex-wrap justify-center gap-3">
                    <button
                      type="button"
                      onClick={() => {
                        if (formState.serviceType === "photo") {
                          setStep2Index(step2Fields.indexOf("photoPeople"));
                        } else {
                          setStep2Index(step2Fields.indexOf("addPhoto"));
                        }
                        setCurrentStep(2);
                      }}
                      className="rounded-full border border-[#d4dbe4] px-6 py-2 text-sm font-semibold text-[#1f2937]"
                    >
                      修改資料
                    </button>
                    <button
                      type="button"
                      onClick={() => goNext(3)}
                      className="rounded-full bg-[#2b5f8f] px-6 py-2 text-sm font-semibold text-white"
                    >
                      完成送出
                    </button>
                  </div>
                </div>
              )}

              {currentStep === 4 && (
                <div className="rounded-sm bg-white px-6 py-8 md:px-10 md:py-10">
                  <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                    Step 4
                  </p>
                  <h2 className="mt-3 text-2xl font-semibold text-[#1f2937] font-display">
                    報名完成
                  </h2>
                  <p className="mt-3 text-sm text-[#64748b]">
                    感謝您選擇 SnowLand 滑雪學校，系統已收到您的訂單。
                    請留意預約確認信；若選擇銀行轉帳，請依畫面或信件說明完成匯款資訊填寫。
                    客服確認訂單與付款後，會再與您確認後續安排。如有任何問題，歡迎加入官方客服聯繫。
                  </p>
                </div>
              )}
            </div>
          </div>
          </section>
        ) : (
          <section className="mt-12">
            <div className="mx-auto max-w-5xl px-6 md:px-12 text-center">
              <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                Design Selection
              </p>
              <h2 className="mt-3 text-2xl font-semibold text-[#1f2937] font-display">
                請選擇介面版本
              </h2>
              <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
                {[
                  { id: "design1", label: "Design 1" },
                  { id: "design2", label: "Design 2" },
                ].map((design) => (
                  <button
                    key={design.id}
                    type="button"
                    onClick={() => {
                      setSelectedDesign(design.id);
                      setCurrentStep(1);
                    }}
                    className={`rounded-sm px-6 py-2 text-sm font-semibold transition-all ${
                      selectedDesign === design.id
                        ? "bg-[#2b5f8f] text-white"
                        : "bg-white text-[#2b5f8f] border border-[#d4dbe4] hover:border-[#2b5f8f]"
                    }`}
                  >
                    {design.label}
                  </button>
                ))}
              </div>
            </div>
          </section>
        )}
      </main>
      <SiteFooter />
    </div>
  );
}

export default BookingPage;
