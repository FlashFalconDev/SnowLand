import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import SiteLink from '../../components/site/SiteLink';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import faqSections from '../../data/site/faqContent';

function FaqPage() {
  const { category } = useParams();
  const navigate = useNavigate();
  const [openItem, setOpenItem] = useState(null);
  const categoryLabels = ["關於課程", "行前準備", "雪場選擇", "親子相關"];
  const categorySlugMap = {
    "關於課程": "course",
    行前準備: "preparation",
    雪場選擇: "skiresort",
    親子相關: "familyski",
  };
  const slugCategoryMap = {
    course: "關於課程",
    preparation: "行前準備",
    skiresort: "雪場選擇",
    familyski: "親子相關",
  };
  const categoryToSectionTitle = {
    關於課程: "預訂課程時",
    行前準備: "行前準備",
    雪場選擇: "雪場選擇",
    親子相關: "親子課程",
  };
  const sectionTitleToCategory = {
    "預訂課程時": "關於課程",
    行前準備: "行前準備",
    雪場選擇: "雪場選擇",
    上課期間: "親子相關",
    親子課程: "親子相關",
  };
  const [activeCategory, setActiveCategory] = useState(categoryLabels[0]);

  useEffect(() => {
    if (!category) return;
    const matchedCategory = slugCategoryMap[category];
    if (matchedCategory && matchedCategory !== activeCategory) {
      setActiveCategory(matchedCategory);
      setOpenItem(null);
    }
  }, [category, activeCategory]);
  const activeSectionTitle = categoryToSectionTitle[activeCategory] ?? activeCategory;
  const filteredSections = faqSections.filter((section) => {
    if (activeCategory === "關於課程") {
      return section.title === "預訂課程時" || section.title === "上課期間";
    }
    return section.title === activeSectionTitle;
  });

  const toggleItem = (id) => {
    setOpenItem((prev) => (prev === id ? null : id));
  };

  return (
    <div className="min-h-screen bg-white text-[#1f2937] flex flex-col">
      <SiteHeader forceTransparent />
      <main className="flex-1 pb-24">
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
              FAQ
            </p>
            <h1 className="mt-4 text-3xl md:text-4xl font-semibold tracking-wide font-display">
              常見問題
            </h1>
          </div>
        </section>

        <section className="max-w-5xl mx-auto px-6 mt-12 space-y-12">
          <div className="border-b border-[#e2e8f0]">
            <div className="flex flex-wrap items-center justify-center gap-12 md:gap-16 text-base md:text-lg font-semibold text-[#6b7280] font-display">
              {categoryLabels.map((label, index) => {
                const isActive = label === activeCategory;
                return (
                  <button
                    key={label}
                    type="button"
                    onClick={() => {
                      setActiveCategory(label);
                      setOpenItem(null);
                      const slug = categorySlugMap[label];
                      if (slug) {
                        navigate(`/faq/${slug}`);
                      }
                    }}
                    className={`relative pb-4 transition-colors duration-200 group ${
                      isActive ? "text-[#111827]" : "hover:text-[#2b5f8f]"
                    }`}
                    aria-current={isActive ? "page" : undefined}
                  >
                    {label}
                    <span
                      className={`absolute left-0 -bottom-[1px] h-0.5 transition-all duration-300 ${
                        isActive ? "w-full bg-[#111827]" : "w-0 bg-[#2b5f8f] group-hover:w-full"
                      }`}
                    />
                  </button>
                );
              })}
            </div>
          </div>
          {filteredSections.map((section) => {
            const sectionIndex = faqSections.findIndex((entry) => entry.title === section.title);
            const sectionNumber =
              filteredSections.length > 1
                ? filteredSections.findIndex((entry) => entry.title === section.title) + 1
                : 1;
            const categoryLabel = sectionTitleToCategory[section.title] ?? section.title;
            return (
            <div key={section.title} className="space-y-6">
              {section.title !== "預訂課程時" &&
                section.title !== "上課期間" &&
                section.title !== "行前準備" &&
                section.title !== "雪場選擇" &&
                section.title !== "親子課程" && (
                <p className="text-base md:text-lg font-semibold text-[#6b7280] font-display">
                  {categoryLabel}
                </p>
              )}
              <h2 className="text-2xl font-semibold text-[#1f2937] font-display">
                {section.title}
              </h2>
              <div className="flex items-center gap-3">
                <span className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                  Section {String(sectionNumber).padStart(2, "0")}
                </span>
                <div className="h-px flex-1 bg-[#e2e8f0]" />
              </div>

              <div className="space-y-4">
                {section.items.map((item, itemIndex) => {
                  const id = `faq-${sectionIndex}-${itemIndex}`;
                  const isOpen = openItem === id;
                  return (
                    <div
                      key={item.q}
                      className="border-b border-[#e2e8f0]"
                    >
                      <button
                        type="button"
                        onClick={() => toggleItem(id)}
                        className="w-full px-6 py-5 md:px-7 md:py-6 flex items-start justify-between gap-4 text-left"
                        aria-expanded={isOpen}
                        aria-controls={`${id}-panel`}
                      >
                        <span className="text-base md:text-lg font-semibold text-[#1f2937]">
                          {item.q}
                        </span>
                        <span
                          className="mt-1 text-[#94a3b8] text-lg"
                          aria-hidden="true"
                        >
                          {isOpen ? "−" : "＋"}
                        </span>
                      </button>
                      <div
                        id={`${id}-panel`}
                        className={`grid transition-all duration-300 ease-out ${
                          isOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
                        }`}
                      >
                        <div className="overflow-hidden px-6 md:px-7 pb-6">
                          <div
                            className="faq-content text-sm md:text-base text-[#475569] leading-relaxed"
                            dangerouslySetInnerHTML={{ __html: item.a }}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

export default FaqPage;
