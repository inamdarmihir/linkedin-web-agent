/**
 * Splits a topics textarea value into a clean string[]: entries may be
 * separated by newlines and/or commas, are trimmed, and empty entries are
 * dropped along with exact duplicates (order-preserving).
 */
export function parseTopics(raw: string): string[] {
  const seen = new Set<string>();
  const topics: string[] = [];

  for (const chunk of raw.split(/[\n,]/)) {
    const topic = chunk.trim();
    if (topic.length === 0 || seen.has(topic)) continue;
    seen.add(topic);
    topics.push(topic);
  }

  return topics;
}
