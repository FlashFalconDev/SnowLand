import React from 'react';
import { Link as RouterLink } from 'react-router-dom';
import SiteLink from '../../components/site/SiteLink';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import legacyPages from '../../data/site/legacyPages.json';
import coachesData from '../../data/site/coaches';
import { useWebsiteCoachCards } from '../../api/websiteCoaches';

function CoachTeamPage() {
  const legacyImageByName = React.useMemo(() => {
    const imageByName = new Map();
    const blocks = legacyPages["coach-team"]?.blocks ?? [];

    for (let index = 0; index < blocks.length; index += 1) {
      const block = blocks[index];
      const nextBlock = blocks[index + 1];
      if (block?.type === "image" && nextBlock?.type === "heading") {
        imageByName.set(nextBlock.text, block.src);
        index += 1;
      }
    }

    return imageByName;
  }, []);
  const coaches = useWebsiteCoachCards(coachesData, legacyImageByName);

  return (
    <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937] flex flex-col">
      <SiteHeader forceTransparent forceDarkText forceLogoColor />
      <main className="flex-1 w-full">
        <section className="bg-[#f6f8fb]">
          <div className="max-w-6xl mx-auto px-6 md:px-10 py-16 md:py-24">
            <div className="text-center mb-12 md:mb-16">
              <p className="text-xs md:text-sm tracking-[0.3em] uppercase text-[#6b7280] font-medium font-display">
                COACH
              </p>
              <h2 className="text-2xl font-semibold text-[#1f2937] mt-4 font-display">
                教練團隊
              </h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 md:gap-10">
              {coaches.map((coach, index) => {
                const specialtyText = coach.certificationText || coach.coachType;
                const specialtyClassName = coach.certificationText
                  ? "mt-4 text-xs font-semibold leading-relaxed text-[#c2410c]"
                  : "mt-4 text-sm font-semibold text-[#4b5563]";
                const cardContent = (
                  <>
                    <div className="w-full aspect-[5/4] bg-[#f8fafc]">
                      {coach.image ? (
                        <img
                          src={coach.image}
                          alt={coach.alt}
                          className="w-full h-full object-cover object-top"
                          loading="lazy"
                        />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center bg-[#eef3f8] text-3xl font-semibold text-[#94a3b8] font-display">
                          {coach.name?.slice(0, 1)}
                        </div>
                      )}
                    </div>

                    <div className="px-8 py-10">
                      <h3 className="text-lg font-semibold text-[#1f2937] font-lora">
                        {coach.name}
                      </h3>
                      {specialtyText && (
                        <p className={specialtyClassName}>
                          {specialtyText}
                        </p>
                      )}
                      {coach.cardBio && (
                        <p className="mt-4 text-sm text-[#6b7280] leading-relaxed">
                          {coach.cardBio}
                        </p>
                      )}
                      {coach.languages && (
                        <p className="mt-4 text-sm font-semibold text-[#64748b]">
                          {coach.languages}
                        </p>
                      )}
                    </div>
                  </>
                );

                if (coach.slug) {
                  return (
                    <SiteLink
                      key={`${coach.name}-${index}`}
                      to={`/coach/${coach.slug}`}
                      className="bg-white border border-[#e5e9f2] rounded-sm overflow-hidden text-center shadow-[0_20px_40px_rgba(15,23,42,0.08)] transition-transform duration-300 hover:-translate-y-1"
                    >
                      {cardContent}
                    </SiteLink>
                  );
                }

                return (
                  <article
                    key={`${coach.name}-${index}`}
                    className="bg-white border border-[#e5e9f2] rounded-sm overflow-hidden text-center shadow-[0_20px_40px_rgba(15,23,42,0.08)]"
                  >
                    {cardContent}
                  </article>
                );
              })}
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

export default CoachTeamPage;
