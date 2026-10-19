import React, { createContext, useContext } from 'react';
import { Link } from 'react-router-dom';
import { siteTracking, trackingButton } from '../../utils/siteTracking';

// Context to hold the client code base path
export const SiteBasePathContext = createContext('');

/**
 * A wrapper around React Router's Link that automatically prepends
 * the current clientCode to the path.
 *
 * Usage: <SiteLink to="/course/tomamu">星野課程</SiteLink>
 * Renders: <Link to="/snowland/course/tomamu">星野課程</Link>
 */
const SiteLink = React.forwardRef(function SiteLink({ to, children, onClick, ...props }, ref) {
  const basePath = useContext(SiteBasePathContext);

  let resolvedTo = to;
  if (typeof to === 'string' && to.startsWith('/') && basePath) {
    resolvedTo = `${basePath}${to}`;
  }

  return (
    <Link ref={ref} to={resolvedTo} {...props} onClick={event => {
      onClick?.(event);
      if (!event.defaultPrevented && event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
        siteTracking?.button(trackingButton(to));
      }
    }}>
      {children}
    </Link>
  );
});

export default SiteLink;
