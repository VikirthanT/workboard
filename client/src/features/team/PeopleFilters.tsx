import { MagnifyingGlass } from '@phosphor-icons/react';
import { Input } from '../../app/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../app/components/ui/select';
import { ROLE_FILTER_LABEL, type RoleFilter } from './memberFilter';

/** The search box and role dropdown above a grouped people list. */
export function PeopleFilters({ search, onSearch, role, onRole }: { search: string; onSearch: (v: string) => void; role: RoleFilter; onRole: (v: RoleFilter) => void }) {
  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
      <div className="relative min-w-[220px] flex-1 max-w-[420px]">
        <MagnifyingGlass size={16} aria-hidden className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-subtle" />
        <Input
          type="search"
          aria-label="Search people"
          placeholder="Search by name or email…"
          className="py-2 pl-10 text-base"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
        />
      </div>
      <Select value={role} onValueChange={(v) => onRole(v as RoleFilter)}>
        <SelectTrigger aria-label="Filter by role" className="w-[170px] py-2 text-base"><SelectValue>{ROLE_FILTER_LABEL[role]}</SelectValue></SelectTrigger>
        <SelectContent>
          {(Object.keys(ROLE_FILTER_LABEL) as RoleFilter[]).map((r) => <SelectItem key={r} value={r}>{ROLE_FILTER_LABEL[r]}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
  );
}
