import React, { createContext, useContext } from 'react';
import { Link } from 'react-router-dom';

// Context to hold the client code base path
export const SiteBasePathContext = createContext('');

/**
 * A wrapper around React Router's Link that automatically prepends
 * the current clientCode to the path.
 *
 * Usage: <SiteLink to="/course/tomamu">星野課程</SiteLink>
 * Renders: <Link to="/snowland/course/tomamu">星野課程</Link>
 */
const SiteLink = React.forwardRef(function SiteLink({ to, children, ...props }, ref) {
  const basePath = useContext(SiteBasePathContext);

  let resolvedTo = to;
  if (typeof to === 'string' && to.startsWith('/') && basePath) {
    resolvedTo = `${basePath}${to}`;
  }

  return (
    <Link ref={ref} to={resolvedTo} {...props}>
      {children}
    </Link>
  );
});

export default SiteLink;
