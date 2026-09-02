import React from 'react';
import ResortCard from './ResortCard';

function ResortGrid({ resorts }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
      {resorts.map((resort) => (
        <ResortCard key={resort.slug} resort={resort} />
      ))}
    </div>
  );
}

export default ResortGrid;
