import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

function ScrollToTop() {
  const { pathname, hash } = useLocation();
  const previousPathRef = useRef(null);

  const getCourseBase = (path) => {
    const match = path.match(/^\/course\/[^/]+/);
    return match ? match[0] : null;
  };

  useEffect(() => {
    const previousPath = previousPathRef.current;
    const currentBase = getCourseBase(pathname);
    const previousBase = previousPath ? getCourseBase(previousPath) : null;
    let retryTimer = null;

    if (hash) {
      const targetId = decodeURIComponent(hash.slice(1));
      const scrollToHashTarget = () => {
        const target = document.getElementById(targetId);
        if (!target) return false;
        target.scrollIntoView({ block: 'start' });
        return true;
      };

      requestAnimationFrame(() => {
        if (!scrollToHashTarget()) {
          retryTimer = window.setTimeout(scrollToHashTarget, 250);
        }
      });

      previousPathRef.current = pathname;
      return () => {
        if (retryTimer) window.clearTimeout(retryTimer);
      };
    }

    if (previousBase && currentBase && previousBase === currentBase) {
      previousPathRef.current = pathname;
      return;
    }

    window.scrollTo(0, 0);
    previousPathRef.current = pathname;
  }, [pathname, hash]);

  return null;
}

export default ScrollToTop;
