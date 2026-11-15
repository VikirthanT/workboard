# team

A team's people: the people from the directory (name, email, Slack ID) a manager assigns work to. They never sign in. One person is on at most one team. The manager's own page (`/team`) and the admin's Teams portal share the same grouped list, filters and dialogs; the admin's version adds role and admin controls.

## Endpoints used (all real, see `server/identity/README.md`)

| Method and path | Where it is called | What it does |
|---|---|---|
| `GET /api/teams/{id}/members` | `services/teams.ts` `getTeamMembers`, `hooks/useTeam.ts` `useTeamMembers` | The team's people, manager first |
| `GET /api/people?unassigned=true&q=&limit=50` | `searchUnassignedPeople`, `useUnassignedPeople`, `AddMemberDialog.tsx` | Active directory people on no team, searched on the server |
| `POST /api/teams/{id}/members` | `addMember`, `useAddMember` | Add a person (reason optional, audited) |
| `GET /api/teams/{id}/channel-members` | `getChannelMembers`, `useChannelMembers`, `PullFromSlackDialog.tsx` | Who is in the team's Slack channel and in the directory, with what adding each would do |
| `POST /api/teams/{id}/members/bulk` | `addMembers`, `useAddMembers` | Add the ticked people together, all or none (reason optional, one audit row each) |
| `DELETE /api/teams/{id}/members/{personId}` | `removeMember`, `RemoveMemberDialog.tsx` | Take them off the team (reason optional for a manager, audited); their open tasks stay and show as needing a new owner. The dialog says how many, from `openTaskCount` on the person (`GET /teams/{id}/members` sends `open_task_count`; unknown elsewhere, then it uses the general sentence) |

There is no Active / Inactive switch on a person any more: a person is added or removed.

**Pull from Slack** (button on a team's header, `TeamSection`'s `onPullFromSlack`): opens a review of everyone in the team's standup channel who is in the directory. People who can join are ticked; the rest say why not (already here, on another team, inactive or a manager). Nothing is added until the person confirms. The button is shown to an admin on any team and to a manager on their own, and disabled with a hint until the team has a standup channel; the server enforces the same rule (`can_manage_team`). If the channel cannot be found, or the bot is not in it, the dialog shows the server's words and cannot add.

## Folder map

```
team/
├── TeamView.tsx           Manager page (/team), reached from the avatar menu
├── TeamMembersPanel.tsx   The manager's list: filters, one TeamSection, add and remove
├── TeamSection.tsx        One collapsible team group; rows with optional role and admin controls
├── PeopleFilters.tsx      Search box + role dropdown
├── memberFilter.ts        filterMembers (search + role), ROLE_FILTER_LABEL
├── AddMemberDialog.tsx    Searchable "Name (email)" picker (also used by the admin)
├── RemoveMemberDialog.tsx The dustbin's dialog
├── PullFromSlackDialog.tsx The review before adding people from the team's Slack channel
├── ReasonFormDialog.tsx   Reason dialog shell (shared with admin)
├── NoTeamPage.tsx         "You are not on any team yet"
├── memberFilter.test.ts
├── hooks/                 useTeamMembers, useUnassignedPeople, useAddMember, useRemoveMember, useRefreshTeams
└── index.ts
```

**Error boundary.** My team's people list is wrapped in `ErrorBoundary` (`TeamView.tsx:19`, label "The team list"). All boundaries: `client/ARCHITECTURE.md`, "Error boundaries".
