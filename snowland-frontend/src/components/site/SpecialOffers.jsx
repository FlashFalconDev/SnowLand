import React from 'react';
import { motion } from 'framer-motion';
import SiteLink from './SiteLink';
import { homepageAssetBase } from '../../data/site/assetPaths';
import { fetchSiteContent } from '../../api/booking';

const SpecialOffers = () => {
    const [cmsOffers, setCmsOffers] = React.useState([]);

    React.useEffect(() => {
        let mounted = true;
        fetchSiteContent({ content_type: 'offer', location_key: 'homepage.offers', limit: 6, include_ended: true })
            .then((items) => {
                if (mounted) setCmsOffers(Array.isArray(items) ? items : []);
            })
            .catch(() => {
                if (mounted) setCmsOffers([]);
            });
        return () => {
            mounted = false;
        };
    }, []);

    const fallbackOffers = [
        {
            title: '25-26雪季早鳥優惠',
            subtitle: '7.01 - 9.30日止',
            image_url: `${homepageAssetBase}/Special offers-early bird.jpg`,
            link_url: '/specialoffers/earlybird',
            badge: '已結束',
            badgeClassName: 'bg-white/90 text-[#1f2937]',
            delay: 0,
        },
        {
            title: '舊生帶新生優惠',
            subtitle: '優惠內容整理中。',
            image_url: `${homepageAssetBase}/Special offers-referal.jpg`,
            link_url: '/specialoffers/referral',
            badge: '進行中',
            badgeClassName: 'bg-brand-orange text-white',
            delay: 0.2,
        },
    ];

    const offers = cmsOffers.length > 0
        ? cmsOffers.map((item, index) => ({
            title: item.title || '限定優惠',
            subtitle: item.subtitle || item.summary || item.body || '',
            image_url: item.image_url || `${homepageAssetBase}/Special offers-referal.jpg`,
            link_url: item.link_url || '/specialoffers',
            badge: item.metadata?.badge || (item.status === 'ended' ? '已結束' : '進行中'),
            badgeClassName: item.status === 'ended' ? 'bg-white/90 text-[#1f2937]' : 'bg-brand-orange text-white',
            delay: index * 0.12,
        }))
        : fallbackOffers;

    return (
        <section id="homepage-offers" className="bg-[#f6f8fb] py-16 md:py-24 scroll-mt-24">
            <div className="max-w-7xl mx-auto px-4 md:px-8">

                {/* Section Header */}
                <div className="text-center mb-12 md:mb-16">
                    <p className="text-xs md:text-sm tracking-[0.3em] uppercase text-[#6b7280] font-medium font-display">
                        Special Offers
                    </p>
                    <h2 className="text-2xl md:text-3xl font-bold text-[#1f2937] mt-4 font-display">
                        限定優惠
                    </h2>
                </div>

                {/* Cards Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8 max-w-[680px] mx-auto">
                    {offers.map((offer) => (
                        <SiteLink key={`${offer.title}-${offer.link_url}`} to={offer.link_url} aria-label={offer.title} className="block">
                            <motion.div
                                initial={{ opacity: 0, y: 30 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true, margin: "-50px" }}
                                transition={{ duration: 0.6, delay: offer.delay, ease: "easeOut" }}
                                className="group relative w-full max-w-[320px] mx-auto aspect-square overflow-hidden shadow-lg cursor-pointer"
                            >
                                <div className={`absolute top-6 right-6 text-xs font-bold px-3 py-1 rounded-xl shadow-lg ${offer.badgeClassName}`}>
                                    {offer.badge}
                                </div>
                                <img
                                    loading="lazy"
                                    decoding="async"
                                    src={offer.image_url}
                                    alt={offer.title}
                                    className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                                />
                                <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent opacity-80 transition-opacity duration-300 group-hover:opacity-90"></div>
                                <div className="absolute bottom-0 left-0 p-8 w-full">
                                    <div className="text-brand-orange text-xs md:text-sm font-bold mb-2 uppercase tracking-wider">
                                        期間限定
                                    </div>
                                    <h3 className="text-white text-xl md:text-2xl font-bold mb-3 drop-shadow-lg leading-tight">
                                        {offer.title}
                                    </h3>
                                    <p className="text-white/90 text-xs md:text-sm font-medium opacity-0 transform translate-y-4 transition-all duration-300 group-hover:opacity-100 group-hover:translate-y-0">
                                        {offer.subtitle}
                                    </p>
                                </div>
                            </motion.div>
                        </SiteLink>
                    ))}
                </div>
            </div>
        </section>
    );
};

export default SpecialOffers;
