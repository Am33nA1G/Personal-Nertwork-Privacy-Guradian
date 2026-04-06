export function countryFlag(code: string | null | undefined): string {
  if (!code || code.length !== 2) return '\u2014';
  const offset = 127397;
  return String.fromCodePoint(
    code.toUpperCase().charCodeAt(0) + offset,
    code.toUpperCase().charCodeAt(1) + offset,
  );
}
