# Server tests

605 tests (100% line and branch coverage of the app code, measured with `make server-cov`): Google sign-in (`auth`), the identity feature (teams, members, admin access, sign-in rules, audit log, search and paging, the dev account list), the tasks feature (permission rules, commands, calculated facts, endpoints, access matrix, input limits, side effects, the team report), database rules, the app shell, the migrations and the seed loader.

Every area is tested from both sides: what must work (positive), what must be refused (negative: wrong person, bad input, a move the rules do not allow), the edges of each limit (the largest value accepted and the first one refused), and that nothing unintended happens (a refused request leaves the database exactly as it was, a read writes nothing, an action on one task or team never touches another).

Run everything, frontend and server, with `make test` from the repo root: each test prints its name, PASSED or FAILED and its progress percentage, and a table at the end gives the percentage that passed per suite and overall (`scripts/test_all.py`).

## How they run

```bash
cd server
.venv/bin/pytest -q          # also works from the repo root: server/.venv/bin/pytest -q server
```

- Needs the dev database up: `make db-up` from the repo root. Run the tests with `make server-test`, which loads `.env` (the password is `POSTGRES_PASSWORD`).
- Each run creates its own database, `workboard_test_<pid>` (the process id), builds it by running the real Alembic migrations, and drops it at the end. So a green run also shows the migrations produce a working schema, two runs at once cannot disturb each other, and the development database is never touched. A run that was killed leaves its database behind; remove strays with `docker exec <db container> psql -U <user> -d postgres -c "DROP DATABASE workboard_test_<pid>"` (list them with `\l`).
- `DEV_AUTH=true` is set by `conftest.py`, so tests act as a person by sending the `X-Dev-User-Email` header.
- People in tests are synthetic (`asha@atimotors.com`, ...). No row from the real directory is used.

## What each file covers

| File | Tests | Area |
| --- | --- | --- |
| `test_auth.py` | 7 | Who can sign in |
| `test_teams.py` | 10 | Creating teams, changing the manager, the audit log's names (`actor_name`, `person_name`, `team_name`) |
| `test_members.py` | 11 | People on a team, the "Add person" picker, the open-task count on the members list (Done and other teams' tasks not counted; null elsewhere) |
| `test_team_delete.py` | 7 | Deleting a team |
| `test_admin_access.py` | 10 | Make / Revoke admin, append-only audit log |
| `test_seed_loader.py` | 13 | `seed/load_db.py`: directory load, people who left, bootstrap admins |
| `test_access_matrix.py` | 55 | Every endpoint against every kind of caller |
| `test_validation.py` | 22 | Malformed input (422), ids that do not exist (404), reasons |
| `test_team_rules.py` | 8 | Create-team and change-manager edge cases, refusals change nothing |
| `test_member_rules.py` | 8 | Add / remove edge cases |
| `test_directory_search.py` | 12 | The picker's search and filters, the `admins=true` list, adding and removing an admin who is on no team, only an admin may |
| `test_pagination.py` | 18 | Server-side paging of `/people` and `/audit-log` |
| `test_database_rules.py` | 23 | What Postgres itself enforces, written to directly (identity and tasks) |
| `test_app.py` | 13 | Health, settings (no database default, a plain `postgresql://` URL gets the driver), unexpected errors, unknown routes, and that the server's "today" is the Indian date (`conftest.py` runs the suite in `Asia/Kolkata`, as production does) |
| `test_text_edge_cases.py` | 5 | Non-ASCII, emoji and combining characters stored and returned exactly (tasks, comments, team names, reasons, search); length limits count characters, not bytes; a NUL character in any text field or in the search is a 422 `invalid_input`, never a 500, and changes nothing |
| `test_concurrency.py` | 18 | Races, each run 6 times with threads and a barrier: one person added to two teams at once lands on one; one person made manager of two teams manages one; two admins revoking each other leave exactly one (the loser gets `last_admin`) |
| `test_admin_manager.py` | 4 | A person who is admin and manager: full rights on their own team; on another team's board only read and comment, nothing changed; a new task lands on their own team only; as an admin they manage people on any team and need a reason |
| `test_audit_trail.py` | 3 | The side effect of every identity change: one audit row each (team create, member add and remove, manager change, admin grant and revoke, team delete) with the right actor, person, team and trimmed reason, read back through `GET /audit-log`; seven refused changes write nothing; only an admin reads the log and it has no write route |
| `test_google_auth.py` | 80 | Google sign-in with Google's answers faked: start, callback, exchange, every refusal (state, nonce, audience, issuer, expiry, unverified or foreign email, unknown or plain member), single-use and expiring codes, and the session token as the API sees it (altered, expired, wrong kind, wrong key, lost role, a signed payload that is not an object, an unusable `exp`) |
| `test_google_exchange_code.py` | 9 | `google.exchange_code`, the call to Google's token endpoint, with `httpx.post` faked: what is sent, a refusal (logged without the secret), no or non-text `id_token`, a non-JSON answer, Google unreachable or slow |
| `test_demo_seed.py` | 16 | `seed/demo_db.py`, the dev demo world: the three accounts sign in, teams and people, 14 tasks in every state, back-dated timelines, a realistic board, loading twice, clashes with real data, reset and remove touch only the demo (the audit log keeps its entries), the directory load never deactivates it, refuses outside development |
| `test_dev_accounts.py` | 4 | `GET /dev/accounts`: who the dev login lists, refused examples, inactive people, 404 when `DEV_AUTH` is off |
| `test_task_rules.py` | 12 | Who may act on a board, the moves each status allows, which need a reason (pure functions) |
| `test_task_calculated.py` | 4 | Overdue, due soon, needs a new owner, needs attention (pure functions) |
| `test_task_commands.py` | 29 | Create, edit, delete, move and comment: what each writes, refuses and leaves on the timeline; a deleted task's snapshot in the audit log, reassignment audit rows, the audit rows cannot be changed, admins may comment |
| `test_task_api.py` | 21 | The task and board endpoints end to end: read access, filters, orphans, Done cards, an admin's read-only board with comments, a Done task cannot be edited until reopened, errors; plus three branches the API cannot reach, tested in the query functions (no team and not an admin, a missing timeline entry, a missing person) |
| `test_task_report_all_teams.py` | 10 | `/reports/all-teams` (admin only): per-team rows, totals, edges |
| `test_task_access.py` | 29 | Every task endpoint against every kind of caller (nobody, a person who cannot sign in, another team's manager, the owner, an admin) |
| `test_task_validation.py` | 84 | Bad and borderline input: each limit on both sides, dates (a past due date is refused on create and on edit; today and later are fine; an old date may be kept or cleared), priorities, malformed and unknown ids, fields the client may not set, nulls, an unchangeable timeline |
| `test_task_side_effects.py` | 36 | Before-and-after database snapshots: 24 refused requests change nothing, reads write nothing, one task or team never touches another, counters and close times move only when they should |
| `test_task_report.py` | 16 | The report numbers, `/reports/team`, and its edges (empty team, both end days of a period, unowned tasks, people who left) |
| `test_migrations.py` | 7 | Upgrade, downgrade, drift and a single head, on a scratch database |

`conftest.py` holds the shared setup: the test database, table clean-up between tests, and the `directory` helper that creates people and calls the API as one of them.

## `test_auth.py`: who can get in

| Test | Verifies |
| --- | --- |
| `no_header_is_unauthenticated` | A request with no identity gets 401. |
| `plain_member_cannot_sign_in` | A member who is neither manager nor admin gets 403 `not_onboarded`. |
| `unknown_and_foreign_accounts_are_refused` | An unknown `@atimotors.com` email gets `not_onboarded`; a `@gmail.com` one gets `domain_not_allowed`. |
| `manager_and_admin_can_sign_in` | Both can call `/me`; the manager's reply shows their team name. |
| `manager_cannot_create_teams_or_read_the_audit_log` | Admin-only routes return 403 for a manager. |
| `deactivated_manager_cannot_sign_in` | An inactive manager gets 403 straight away. |
| `without_dev_auth_every_protected_route_is_closed` | With `DEV_AUTH` off the stub is unreachable and the answer is 501 `auth_not_configured`. |

## `test_teams.py`: creating teams and managers

| Test | Verifies |
| --- | --- |
| `create_team_promotes_initial_person` | The first person becomes manager, is on the team, and the team has 1 member. |
| `create_team_needs_a_reason` | A blank reason is refused with 422 `reason_required`. |
| `team_name_is_unique_ignoring_case` | "npi" can't be created when "NPI" exists (409 `team_name_taken`). |
| `person_on_another_team_cannot_start_a_team` | Someone who already manages a team is refused as a new team's manager. |
| `changing_manager_demotes_the_old_one_and_keeps_them_on_the_team` | The new person is promoted; the old manager becomes a plain member and stays on the team. |
| `cannot_make_someone_from_another_team_the_manager` | A manager of QA can't be made manager of NPI (409). |
| `every_team_change_is_audited` | Create, add member and manager change each leave an audit row, with old and new manager and the reason in the details. |
| `manager_sees_only_their_own_team` | A manager's team list holds only their team; the admin sees all. |

## `test_members.py`: people on a team

| Test | Verifies |
| --- | --- |
| `manager_adds_a_person_from_the_directory` | The picker lists people on no team; an add succeeds; the person then leaves the picker. |
| `manager_cannot_touch_another_team` | Adding to, or listing, another team's members gets 403. |
| `a_person_is_on_at_most_one_team` | Adding someone already on a team is refused (`already_on_team`). |
| `admin_must_give_a_reason_but_a_manager_need_not` | An admin without a reason gets 422; a manager without one succeeds. |
| `members_list_puts_the_manager_first` | The manager is listed first even when their name sorts last. |
| `removed_person_goes_back_to_the_picker` | The dustbin delete takes someone off the team; they reappear in the picker. |
| `the_manager_cannot_be_removed` | Removing the manager is refused (`is_manager`). |
| `the_activate_route_is_gone` | The old activate/deactivate route answers 405, so it can't return unnoticed. |
| `an_admin_on_no_team_can_be_added_as_a_member_and_a_manager_cannot` | An admin can join a team as a member and keeps `is_admin`; someone who already runs another team is refused. |
| `a_manager_can_be_listed_as_a_team_member_to_assign_to` | The manager appears in their own team's member list, which will be the assignee list. |

## `test_team_delete.py`: deleting a team

| Test | Verifies |
| --- | --- |
| `deleting_a_team_releases_everyone_and_revokes_the_managers_access` | The team is gone, members are on no team, the manager is demoted and can't sign in. |
| `an_admin_who_ran_the_team_keeps_admin_access` | A manager who is also an admin can still sign in after the team is deleted. |
| `only_an_admin_can_delete_a_team` | A manager gets 403 and the team is untouched. |
| `a_wrong_name_or_missing_reason_stops_the_delete` | A mismatched confirmation name or blank reason is refused and nothing is deleted. |
| `the_name_check_ignores_case_and_spaces` | Typing " npi " confirms deleting "NPI". |
| `the_audit_log_keeps_a_record_of_the_deletion` | One `team.delete` row holds the name, manager id, member ids and reason; the earlier history remains. |
| `deleting_an_unknown_team_is_a_404` | A team id that doesn't exist returns 404. |

## `test_admin_access.py`: the admin toggle and the audit log

| Test | Verifies |
| --- | --- |
| `a_team_member_made_admin_can_sign_in_and_keeps_their_team` | The flag lets a plain member sign in; their role and team don't change. |
| `a_manager_made_admin_keeps_running_the_team` | The manager's role stays `manager`, they still lead NPI, and they now see every team. |
| `revoking_admin_from_a_plain_member_closes_the_door` | After revoke, a non-manager can no longer sign in. |
| `only_an_admin_can_change_admin_rights` | A manager trying to grant admin gets 403. |
| `a_reason_is_required` | A blank reason is refused. |
| `setting_the_state_a_person_already_has_is_refused` | Granting to an admin or revoking from a non-admin returns `admin_unchanged`. |
| `the_last_admin_cannot_be_revoked_but_one_of_two_can` | The sole admin can't be revoked; one of two can; the guard applies again afterwards. |
| `an_inactive_person_cannot_be_made_admin` | An inactive person is refused (`person_inactive`). |
| `grant_and_revoke_are_audited` | Both actions create rows with the actor, reason and action name. |
| `the_audit_log_cannot_be_changed_even_with_raw_sql` | A direct `UPDATE` or `DELETE` fails in the database with "append-only". |

## `test_seed_loader.py`: the directory loader (`seed/load_db.py`)

| Test | Verifies |
| --- | --- |
| `read_directory_keeps_good_rows_and_says_why_it_skipped_the_rest` | Emails are trimmed and lowercased; rows with a blank name, a wrong domain, or a duplicate email or Slack id are skipped, each with a reason. |
| `a_missing_directory_file_stops_with_a_clear_message` | A missing directory file exits with an "is missing" message. |
| `loading_twice_adds_nobody_new` | Running the load again does not duplicate anyone. |
| `a_reload_refreshes_name_and_email_but_never_role_team_or_admin` | A reload updates a person's name and email but leaves a manager's role and team alone. |
| `people_missing_from_the_file_are_deactivated_not_deleted` | Slack is the source of truth: someone absent from the file is marked inactive, and the row is kept. |
| `an_admin_missing_from_the_file_is_never_deactivated` | An admin can't be locked out by a file that leaves them out. |
| `someone_who_comes_back_in_the_file_is_active_again` | A person who reappears in the file is reactivated. |
| `a_deactivated_person_is_not_offered_in_the_picker_and_cannot_sign_in` | After deactivation they vanish from the "Add person" picker and are refused at sign-in. |
| `a_file_that_would_remove_too_many_people_is_refused_unless_forced` | Deactivating more than the larger of 20 people or 10% needs `--allow-large-removal`; nothing changes without it. |
| `a_deactivated_person_still_on_a_team_is_reported` | The loader reports a deactivated person who is still on a team, so an admin can deal with them. |
| `bootstrap_admins_are_granted_once_and_audited` | The first run grants admin and writes one `admin.grant` audit row; a second run grants nothing. |
| `a_bootstrap_admin_who_is_not_in_the_directory_stops_the_load` | An address not in the directory aborts with a clear message. |

## `test_access_matrix.py`: who may call what

One parametrised test: 11 endpoints times 5 callers (nobody, a plain member, a manager of another team, the team's own manager, an admin) is 55 cases, each in a fresh set of data. Each case checks the exact status and, for a refusal, the exact error code (`not_authenticated`, `not_onboarded` or `forbidden`). A new endpoint gets a row in the `CASES` table.

## `test_validation.py`: bad input

| Test | Verifies |
| --- | --- |
| `create_team_rejects_malformed_bodies` (9 cases) | Empty body, missing fields, bad UUID, empty or over-long name, over-long reason, wrong type: all 422. |
| `create_team_without_any_body_is_422` | No body at all is 422. |
| `a_blank_name_made_of_spaces_is_refused_by_the_service` | Spaces only passes the request model, then `name_required`. |
| `a_malformed_id_in_the_path_is_422` (5 paths) | A non-UUID team or person id is 422 on every method the path has. |
| `the_admin_toggle_needs_a_real_boolean` | Missing or non-boolean `is_admin` is 422. |
| `delete_team_needs_a_confirmation_name_and_reason` | Each missing or empty field is 422. |
| `unknown_fields_in_a_body_are_ignored_not_applied` | Extra `role`, `is_admin`, `team_id` in a request do not change the person (mass assignment). |
| `unknown_team_is_404_everywhere` | `team_not_found` on five routes. |
| `unknown_person_is_404_everywhere` | `person_not_found` on five routes. |
| `clean_reason_trims_and_enforces_the_rules` | Trimming, blank-is-nothing, `reason_required`, `reason_too_long` (the last cannot be reached over HTTP, so it is tested directly). |

## `test_team_rules.py`: team edge cases

| Test | Verifies |
| --- | --- |
| `making_the_current_manager_the_manager_again_is_refused` | `same_manager`. |
| `an_inactive_person_cannot_start_a_team_or_become_a_manager` | `person_inactive` on create and on change. |
| `a_member_of_another_team_cannot_become_this_teams_manager` | `already_on_team` on change. |
| `a_refused_manager_change_leaves_everything_as_it_was` | Old manager keeps role and `manager_id`; no audit row is written. |
| `a_refused_create_does_not_promote_the_person` | A taken name leaves the person a plain member, unaudited. |
| `an_admin_on_no_team_can_start_a_team_and_stays_admin` | Manager role gained, `is_admin` kept. |
| `a_team_with_no_manager_can_be_given_one` | Works, and the audit details record `old_manager_id: null`. |
| `the_member_count_follows_adds_and_removes` | `member_count` is 1, 3, then 2. |

## `test_member_rules.py`: member edge cases

| Test | Verifies |
| --- | --- |
| `an_inactive_person_cannot_be_added` | `person_inactive`. |
| `a_manager_role_person_cannot_be_added_as_a_member` | `person_unavailable` (a manager on no team is built directly; the API cannot produce one). |
| `adding_someone_twice_is_refused_the_second_time` | `already_on_team`. |
| `removing_someone_who_is_not_on_the_team_is_a_404` | `not_on_team`, for a stranger and for someone on another team. |
| `an_admin_must_give_a_reason_to_remove_someone` | Blank reason is 422; a real one is 204. |
| `an_admin_can_list_the_members_of_any_team` | Positive path for the admin. |
| `someone_removed_from_one_team_can_join_another` | Remove then add elsewhere works. |
| `get_member_refuses_someone_on_another_team` | The query raises `not_on_team`. |

## `test_directory_search.py`: the picker's search

| Test | Verifies |
| --- | --- |
| `search_matches_part_of_a_name_ignoring_case` | Case-insensitive, partial. |
| `search_matches_part_of_an_email_even_when_the_name_differs` | Searches email as well as name. |
| `a_blank_search_returns_everyone_and_spaces_are_trimmed` | Blank means no filter; spaces are trimmed. |
| `a_search_with_no_match_is_an_empty_list` | `[]`, not an error. |
| `quotes_and_sql_look_alikes_are_treated_as_plain_text` | `O'Brien` matches; `'; DROP TABLE people; --` matches nothing and the table is intact. |
| `percent_and_underscore_are_matched_literally_not_as_wildcards` | `%` and `_` search for themselves (this caught a real bug). |
| `results_are_ordered_by_name` | Alphabetical. |
| `the_default_list_includes_people_on_teams_but_not_inactive_ones` | Shows each person's team name; inactive people are hidden. |
| `unassigned_hides_people_on_teams_and_inactive_ones_but_shows_admins` | The picker rules. |

## `test_pagination.py`: server-side paging

| Test | Verifies |
| --- | --- |
| `walking_every_page_returns_each_person_exactly_once` | 131 people in pages of 50: no repeats, no gaps, name order. |
| `the_last_page_is_the_remainder_and_past_the_end_is_empty` | Last page has 31; an offset past the end is `[]` with the same `total`. |
| `an_exact_multiple_of_the_page_size_has_no_extra_page` | 100 people: pages of 50, 50, then empty. |
| `people_with_the_same_name_come_in_a_fixed_order_...` | 60 equal names are ordered by `(name, id)`; fails if the tiebreaker is removed. |
| `total_counts_every_match_not_just_the_page` | `total` follows the search filter; the page holds only `limit` rows. |
| `unassigned_pages_leave_out_people_on_teams` | Totals and pages agree with the filter. |
| `default_and_maximum_page_sizes` | Default 50; `limit=200` returns 200 of 251. |
| `out_of_range_paging_values_are_refused_not_silently_changed` (7 cases) | `limit` 0, -1, 201, text; `offset` -1, 1.5, text: all 422 on both endpoints. |
| `the_audit_log_pages_newest_first_without_gaps_or_repeats` | 120 entries, newest first across three pages. |
| `audit_rows_with_the_same_timestamp_keep_a_stable_order_across_pages` | 40 entries sharing a timestamp page identically twice; fails if the tiebreaker is removed. |
| `the_audit_log_total_and_past_the_end` | `total` correct; offset past the end is empty. |
| `a_non_admin_cannot_page_the_audit_log` | 403. |

## `test_database_rules.py`: what the database enforces

These write to the database directly, bypassing the API, and assert each refusal by constraint name so an unrelated error cannot make a test pass.

| Test | Verifies |
| --- | --- |
| `two_people_cannot_share_an_email_or_a_slack_id` | `people_email_key`, `people_slack_user_id_key`. |
| `team_names_are_unique_ignoring_case` | `uq_teams_name_lower`. |
| `a_person_cannot_manage_two_teams` | `teams_manager_id_key`. |
| `a_team_cannot_have_two_manager_role_people` | `uq_people_one_manager_per_team`; plain members are unlimited. |
| `email_must_be_lowercase` | `ck_people_email_lower`. |
| `role_must_be_member_or_manager` | `ck_people_role` (`admin` and `boss` are refused: admin is a flag). |
| `required_person_columns_cannot_be_null` (6 columns) | NOT NULL on `slack_user_id`, `email`, `name`, `role`, `is_admin`, `active`, sent by raw SQL (the ORM would swap an explicit `None` for the default). |
| `a_team_must_have_a_name` | NOT NULL on `teams.name`. |
| `a_team_must_point_at_a_real_person_and_a_person_at_a_real_team` | Both foreign keys. |
| `the_database_fills_in_the_defaults` | UUID ids, role `member`, `is_admin` false, `active` true, no team, timestamps set. |
| `updated_at_moves_when_the_app_changes_a_person` | The ORM bumps `updated_at` (raw SQL edits do not; there is no trigger, by decision). |
| `deleting_a_team_releases_its_people_but_keeps_them` | `ON DELETE SET NULL` on `people.team_id`. |
| `deleting_a_manager_leaves_the_team_without_one` | `ON DELETE SET NULL` on `teams.manager_id`. |
| `audit_rows_outlive_the_people_and_teams_they_mention` | No foreign keys on the audit log, so history survives deletes. |

## `test_app.py`: the application shell

| Test | Verifies |
| --- | --- |
| `health_needs_no_sign_in`, `health_stays_open_even_when_sign_in_is_not_configured` | `/api/health` answers 200 without an identity, even with `DEV_AUTH` off. |
| `bootstrap_admin_emails_are_split_trimmed_and_lowercased` | Spaces, empty items and case in `BOOTSTRAP_ADMIN_EMAILS`. |
| `dev_auth_is_off_unless_explicitly_turned_on` | Unset is false; `true`/`1` on; `false`/`0` off. |
| `the_database_url_has_no_default_so_no_credentials_live_in_the_code` | `Settings()` without `DATABASE_URL` is refused. |
| `the_other_settings_default_to_the_company_domain_and_no_bootstrap_admins` | The allowed domain defaults to `atimotors.com`; no bootstrap admins. |
| `the_allowed_domain_comes_from_settings_not_from_the_code` | Changing `allowed_email_domain` makes sign-in refuse the old domain. |
| `an_unexpected_error_is_a_plain_500_that_leaks_nothing` | A crash inside a service gives 500 with no message, exception name or secret in the body. |
| `unknown_routes_are_a_404` (3 paths) | Unknown paths are 404. |

## `test_migrations.py`: the migrations on a scratch database

| Test | Verifies |
| --- | --- |
| `there_is_exactly_one_migration_head` | No forked history. |
| `upgrade_creates_every_table_and_the_audit_trigger` | Three tables plus `alembic_version`, and the append-only trigger function. |
| `downgrade_removes_everything_it_created` | Only `alembic_version` is left; the trigger function is gone. |
| `upgrade_downgrade_upgrade_ends_where_it_started` | The cycle works and the partial unique index is back. |
| `upgrading_twice_is_a_harmless_no_op` | A second `upgrade head` changes nothing. |
| `the_models_and_the_migrations_agree` | `alembic check` finds no drift. |
| `the_drift_check_really_does_catch_a_difference` | A hand-added column makes the check fail, so the test above can go red. |

## Not covered yet

- Two admins acting at the same moment (the row locks are in the code but untested).
- Real Google sign-in (built last).
- Two moves of one card at the same moment (the row lock is in the code but untested).
- The report in a server time zone far from UTC (the tests use midday UTC so the day cannot shift).
- The loader's command line (`main()`): the missing-`BOOTSTRAP_ADMIN_EMAILS` exit was checked by hand, not by a test.
- The weekly Slack API pull (a TODO, not built).
