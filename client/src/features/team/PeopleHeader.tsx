/** Column titles for the people rows, drawn once above the groups so no row has to repeat a label. Widths match `TeamSection`. */
export function PeopleHeader({ adminControls }: { adminControls: boolean }) {
  return (
    <div className="flex items-center gap-4 border-b border-line px-5 py-2 text-sm text-ink-subtle" aria-hidden>
      <span className="flex-1 pl-12">Person</span>
      {adminControls && <span className="w-16 text-center">Admin</span>}
      <span className="w-[130px]">Role</span>
      <span className="size-9" />
    </div>
  );
}
