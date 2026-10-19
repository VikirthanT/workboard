/** "NPI Team!" -> "npi-team". shortcut: two names can collapse to one slug ("A B" / "A-B"); the first team wins, add a server slug if that ever happens. */
export const slugify = (s: string) =>
  s.toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
