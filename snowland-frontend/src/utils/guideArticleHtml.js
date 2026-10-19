const decodeEntities = html => html.replace(/&(#x[0-9a-f]+|#\d+|amp|lt|gt|quot|apos|nbsp);/gi, (match,key) => {
  const named = {amp:'&',lt:'<',gt:'>',quot:'"',apos:"'",nbsp:' '};
  if (key[0] !== '#') return named[key.toLowerCase()] ?? match;
  const code = key[1].toLowerCase() === 'x' ? parseInt(key.slice(2),16) : parseInt(key.slice(1),10);
  return code > 0 && code <= 0x10ffff && !(code>=0xd800 && code<=0xdfff) ? String.fromCodePoint(code) : '\ufffd';
});
const plainText = html => decodeEntities(html.replace(/<[^>]*>/g,'')).trim();

/** Add navigation without changing editor data, original heading markup or anchors. */
export function prepareGuideArticleHtml(original = '') {
  const toc = [], ids = new Set([...original.matchAll(/\bid\s*=\s*["']([^"']+)["']/gi)].map(match=>decodeEntities(match[1])));
  const used = new Set();
  let counter = 0;
  const html = original
    .replace(/<iframe\b[^>]*>/gi, tag=>tag.replace(/loading="lazy"/gi,'loading="eager"'))
    .replace(/<table\b/gi,'<table tabindex="0"')
    .replace(/<h([234])\b((?:[^>"']|"[^"]*"|'[^']*')*)>([\s\S]*?)<\/h\1\s*>/gi,(match,level,attributes,content)=>{
      const label = plainText(content);
      if (!label) return match;
      const existing = [...attributes.matchAll(/([^\s=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s]+)))?/g)].find(attribute=>attribute[1].toLowerCase()==='id');
      let id = existing ? decodeEntities(existing[2] ?? existing[3] ?? existing[4] ?? '') : '';
      if (!id || used.has(id)) {
        do { id = `guide-section-${++counter}`; } while(ids.has(id));
        if (existing) attributes = attributes.slice(0,existing.index)+attributes.slice(existing.index+existing[0].length);
        attributes += ` id="${id}"`;
        ids.add(id);
      }
      used.add(id);
      toc.push({id,label,level:Number(level)});
      return `<h${level}${attributes}>${content}</h${level}>`;
    });
  return {html,toc};
}
